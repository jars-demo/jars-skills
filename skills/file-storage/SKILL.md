---
name: file-storage
description: Designing and implementing file upload, storage, and delivery: generates presigned URLs for direct client-to-S3 uploads, validates files by magic bytes before accepting them, stores metadata in the database, serves files through a CDN, scans for malware asynchronously, manages lifecycle policies to control costs, and never stores user-uploaded files on the application server. Use when you want to add file upload, store files in S3, generate presigned URLs, serve files via CDN, validate uploaded files, scan uploads for malware, manage file storage costs, or implement file download.
---

## file-storage

Never store files on the application server. Use object storage (S3, GCS, R2) and a CDN.
The server orchestrates — it never holds the bytes.

### 1. The right upload architecture

```
❌ Wrong:
Client → POST /upload (multipart) → App Server → S3
         (file transits through your server — doubles bandwidth cost,
          limits file size to server memory, single point of failure)

✅ Right:
Client → POST /upload/presign → App Server → returns presigned URL
Client → PUT <presigned URL>  → S3 directly (app server not in the path)
Client → POST /upload/confirm → App Server → validates + saves metadata to DB
```

Presigned URLs offload the bytes entirely to S3. The app server handles only metadata.

---

### 2. Presigned upload — full implementation

```python
# services/file_service.py
"""
services/file_service.py
-------------------------
File upload orchestration: presigned URL generation, metadata persistence,
post-upload validation, and CDN URL generation.

Depends on: lib/s3_client.py, repositories/file_repository.py, lib/logger.py
Used by:    routes/file_routes.py
"""

import hashlib
import uuid
from lib.s3_client import s3
from lib.logger import get_logger
from lib.tenant_context import get_tenant
from repositories.file_repository import FileRepository
from config.settings import settings

logger = get_logger(__name__)

ALLOWED_CONTENT_TYPES = {
    "image/jpeg":      ".jpg",
    "image/png":       ".png",
    "image/webp":      ".webp",
    "application/pdf": ".pdf",
}
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024   # 10 MB


async def generate_presigned_upload(
    filename: str,
    content_type: str,
    size_bytes: int,
) -> dict:
    """
    Generate a presigned S3 PUT URL and persist a pending file record.
    Returns the presigned URL and the file_id to confirm after upload.
    """
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise ValueError(f"Unsupported content type: {content_type}")

    if size_bytes > MAX_FILE_SIZE_BYTES:
        raise ValueError(f"File exceeds maximum size of {MAX_FILE_SIZE_BYTES // 1024 // 1024} MB")

    tenant_id = get_tenant()
    file_id   = str(uuid.uuid4())
    ext       = ALLOWED_CONTENT_TYPES[content_type]
    # Store under tenant prefix — isolates tenant data in the bucket
    s3_key    = f"{tenant_id}/uploads/{file_id}{ext}"

    presigned_url = await s3.generate_presigned_url(
        "put_object",
        Params={
            "Bucket":      settings.s3_bucket,
            "Key":         s3_key,
            "ContentType": content_type,
            # Enforce size limit at S3 level too — client cannot bypass
            "ContentLength": size_bytes,
        },
        ExpiresIn=300,   # 5 minutes — must upload within this window
    )

    # Persist pending record — confirmed after client completes upload
    await FileRepository().create_pending(
        file_id=file_id,
        tenant_id=tenant_id,
        original_name=filename,
        s3_key=s3_key,
        content_type=content_type,
        size_bytes=size_bytes,
    )

    logger.info(
        "Presigned upload URL generated. file_id=%s tenant_id=%s size_bytes=%d",
        file_id, tenant_id, size_bytes,
    )
    return {"file_id": file_id, "upload_url": presigned_url, "expires_in": 300}


async def confirm_upload(file_id: str) -> dict:
    """
    Called after client completes the S3 upload.
    Verifies the object exists in S3 and marks the file as ready.
    """
    file_repo = FileRepository()
    record    = await file_repo.find_pending(file_id, get_tenant())
    if not record:
        raise FileNotFoundError(f"Pending upload not found: {file_id}")

    # Verify the object actually landed in S3
    try:
        head = await s3.head_object(Bucket=settings.s3_bucket, Key=record["s3_key"])
        actual_size = head["ContentLength"]
    except Exception as exc:
        logger.error(
            "S3 object not found after upload confirmation. file_id=%s key=%s error=%s",
            file_id, record["s3_key"], exc,
        )
        raise FileNotFoundError("Upload not found in storage — did the upload complete?")

    await file_repo.mark_ready(file_id, actual_size)

    # Enqueue async virus scan — never block the response on this
    await enqueue_scan_job(file_id, record["s3_key"])

    cdn_url = f"{settings.cdn_base_url}/{record['s3_key']}"
    logger.info("Upload confirmed. file_id=%s size_bytes=%d", file_id, actual_size)
    return {"file_id": file_id, "url": cdn_url, "status": "processing"}
```

---

### 3. Routes — thin handlers

```python
# routes/file_routes.py
"""
routes/file_routes.py
----------------------
File upload and retrieval endpoints.

Depends on: services/file_service.py
Used by:    main.py
"""

from fastapi import APIRouter
from pydantic import BaseModel, Field
from services.file_service import generate_presigned_upload, confirm_upload, get_file_url

router = APIRouter(prefix="/files")


class PresignRequest(BaseModel):
    filename:     str = Field(max_length=255)
    content_type: str
    size_bytes:   int = Field(gt=0, le=10 * 1024 * 1024)


@router.post("/upload/presign", status_code=201)
async def presign_upload(body: PresignRequest):
    return await generate_presigned_upload(
        filename=body.filename,
        content_type=body.content_type,
        size_bytes=body.size_bytes,
    )


@router.post("/upload/confirm/{file_id}")
async def confirm(file_id: str):
    return await confirm_upload(file_id)


@router.get("/{file_id}")
async def get_file(file_id: str):
    return await get_file_url(file_id, get_tenant())
```

---

### 4. Database schema

```sql
CREATE TABLE files (
    id            TEXT        PRIMARY KEY,
    tenant_id     TEXT        NOT NULL,
    original_name TEXT        NOT NULL,
    s3_key        TEXT        NOT NULL UNIQUE,
    content_type  TEXT        NOT NULL,
    size_bytes    BIGINT      NOT NULL,
    status        TEXT        NOT NULL DEFAULT 'pending',
                              -- pending | ready | quarantined | deleted
    scan_result   TEXT,       -- clean | infected | pending
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    confirmed_at  TIMESTAMPTZ,
    deleted_at    TIMESTAMPTZ
);

CREATE INDEX idx_files_tenant_status ON files (tenant_id, status, created_at DESC);
```

---

### 5. Async virus scanning

Never block the upload response on a virus scan. Scan asynchronously and quarantine
infected files before they are served.

```python
# workers/scan_worker.py
"""
workers/scan_worker.py
-----------------------
Scans uploaded files for malware using ClamAV or a cloud scanning service.
Quarantines infected files immediately.

Depends on: lib/s3_client.py, repositories/file_repository.py
Used by:    queue consumer
"""

from lib.logger import get_logger

logger = get_logger(__name__)


async def scan_file(file_id: str, s3_key: str) -> None:
    logger.info("Starting virus scan. file_id=%s", file_id)

    # Download file for scanning
    obj = await s3.get_object(Bucket=settings.s3_bucket, Key=s3_key)
    content = await obj["Body"].read()

    # Send to scanning service (e.g. ClamAV REST, AWS Macie, VirusTotal)
    result = await scan_service.scan(content)

    if result.infected:
        # Move to quarantine prefix and mark in DB
        quarantine_key = s3_key.replace("/uploads/", "/quarantine/")
        await s3.copy_object(
            Bucket=settings.s3_bucket,
            CopySource={"Bucket": settings.s3_bucket, "Key": s3_key},
            Key=quarantine_key,
        )
        await s3.delete_object(Bucket=settings.s3_bucket, Key=s3_key)
        await FileRepository().mark_quarantined(file_id)
        logger.error(
            "File quarantined — malware detected. file_id=%s threat=%s "
            "action=notify_security_team",
            file_id, result.threat_name,
        )
    else:
        await FileRepository().mark_scan_clean(file_id)
        logger.info("File scan clean. file_id=%s", file_id)
```

---

### 6. Presigned download URLs — never expose S3 keys directly

```python
async def get_file_url(file_id: str, tenant_id: str) -> dict:
    record = await FileRepository().find_ready(file_id, tenant_id)
    if not record:
        raise FileNotFoundError(file_id)

    if record["status"] == "quarantined":
        raise PermissionError("File is unavailable")

    # Option A — CDN URL (public bucket or CDN with signed cookies)
    if settings.cdn_base_url:
        return {"url": f"{settings.cdn_base_url}/{record['s3_key']}", "expires_in": None}

    # Option B — presigned download URL (private bucket)
    url = await s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.s3_bucket, "Key": record["s3_key"]},
        ExpiresIn=3600,   # 1 hour
    )
    return {"url": url, "expires_in": 3600}
```

---

### 7. S3 lifecycle policy — control costs

```json
{
  "Rules": [
    {
      "Id": "delete-pending-uploads",
      "Status": "Enabled",
      "Filter": { "Prefix": "uploads/" },
      "Expiration": { "Days": 1 }
    },
    {
      "Id": "archive-old-files",
      "Status": "Enabled",
      "Filter": { "Prefix": "files/" },
      "Transitions": [
        { "Days": 90,  "StorageClass": "STANDARD_IA" },
        { "Days": 365, "StorageClass": "GLACIER"     }
      ]
    },
    {
      "Id": "delete-quarantined",
      "Status": "Enabled",
      "Filter": { "Prefix": "quarantine/" },
      "Expiration": { "Days": 30 }
    }
  ]
}
```

### Rules

- Never proxy file bytes through the application server. Presigned URLs only.
- Validate content type by magic bytes on the server after upload — not by the
  client-supplied Content-Type header.
- Store files under a tenant prefix: `{tenant_id}/uploads/{file_id}.ext` — never
  in a flat namespace.
- Scan asynchronously. Serve files with `status=processing` immediately; quarantine
  after scan if infected.
- Never expose raw S3 keys or bucket names in API responses. Return file_id and let
  the server generate presigned URLs on demand.
- Set S3 lifecycle policies from day one. Pending uploads and quarantined files
  accumulate quietly and cost money if never cleaned up.
- Block public access on the S3 bucket. Serve all files through presigned URLs or
  a CDN with signed cookies.
