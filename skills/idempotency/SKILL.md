---
name: idempotency
description: Designing operations that are safe to retry without side effects: idempotency keys on API endpoints and background jobs, database upserts, at-least-once vs exactly-once delivery semantics, deduplication strategies, and HTTP method idempotency rules. Use when you want to make an operation idempotent, handle duplicate requests, design a retry-safe API, prevent double charges, use idempotency keys, implement upsert logic, handle at-least-once delivery, or avoid duplicate side effects on retry.
---

## idempotency

Design every operation that crosses a process or network boundary to be safe to call more
than once. Retries, replays, and duplicate deliveries are not edge cases — they are guarantees
in distributed systems.

### 1. HTTP method idempotency — know the rules

| Method | Idempotent | Safe | Notes |
|--------|-----------|------|-------|
| GET | ✅ | ✅ | No side effects |
| HEAD | ✅ | ✅ | Same as GET, no body |
| PUT | ✅ | ❌ | Replace the whole resource; same result every time |
| DELETE | ✅ | ❌ | First call deletes; subsequent calls return 404 or 200 |
| OPTIONS | ✅ | ✅ | |
| POST | ❌ | ❌ | Creates a new resource by default — needs explicit idempotency key |
| PATCH | ❌ | ❌ | Partial update — result depends on current state |

**POST and PATCH need explicit idempotency keys** when the caller may retry (mobile clients,
background jobs, webhooks, payment flows).

---

### 2. Idempotency keys on POST endpoints

The caller generates a unique key per logical operation and sends it in the request.
The server stores the key and the result. On retry, the server returns the stored result
without re-executing the operation.

```python
# routes/payment_routes.py
"""
routes/payment_routes.py
------------------------
Payment initiation endpoint with idempotency key support.

Depends on: services/payment_service.py, lib/idempotency_store.py
Used by:    external callers (mobile app, checkout frontend)
"""

from fastapi import APIRouter, Header, HTTPException
from schemas.payment_schema import ChargeRequest, ChargeResponse
from services.payment_service import PaymentService
from lib.idempotency_store import IdempotencyStore
from lib.logger import get_logger

router = APIRouter(prefix="/payments")
logger = get_logger(__name__)


@router.post("/charge", response_model=ChargeResponse)
async def charge(
    body: ChargeRequest,
    idempotency_key: str = Header(..., min_length=16, max_length=128),
):
    store = IdempotencyStore()

    # 1. Check if we have already processed this key
    cached = await store.get(idempotency_key)
    if cached:
        logger.info(
            "Returning cached result for idempotency key. key=%s", idempotency_key
        )
        return ChargeResponse(**cached)

    # 2. Lock the key so concurrent duplicate requests don't both execute
    acquired = await store.lock(idempotency_key, ttl_seconds=30)
    if not acquired:
        raise HTTPException(status_code=409, detail="Duplicate request in progress")

    try:
        result = await PaymentService().charge(body)

        # 3. Store result before returning — so retries get the same response
        await store.save(idempotency_key, result.dict(), ttl_seconds=86400)
        logger.info(
            "Charge processed and cached. key=%s charge_id=%s",
            idempotency_key, result.charge_id,
        )
        return result

    except Exception:
        # On failure, release the lock so the caller can retry with the same key
        await store.delete(idempotency_key)
        raise
```

```python
# lib/idempotency_store.py
"""
lib/idempotency_store.py
------------------------
Redis-backed idempotency key store.
Keys expire after TTL so storage does not grow unboundedly.

Depends on: lib/redis.py, lib/logger.py
Used by:    routes that require idempotent POST/PATCH
"""

import json
from lib.redis import redis_client
from lib.logger import get_logger

logger = get_logger(__name__)

LOCK_PREFIX   = "idempotency:lock:"
RESULT_PREFIX = "idempotency:result:"


class IdempotencyStore:
    async def get(self, key: str) -> dict | None:
        raw = await redis_client.get(f"{RESULT_PREFIX}{key}")
        return json.loads(raw) if raw else None

    async def lock(self, key: str, ttl_seconds: int = 30) -> bool:
        """Acquire a lock. Returns False if already locked (duplicate in-flight)."""
        result = await redis_client.set(
            f"{LOCK_PREFIX}{key}", "1", nx=True, ex=ttl_seconds
        )
        return result is not None

    async def save(self, key: str, data: dict, ttl_seconds: int = 86400) -> None:
        await redis_client.set(
            f"{RESULT_PREFIX}{key}", json.dumps(data), ex=ttl_seconds
        )
        await redis_client.delete(f"{LOCK_PREFIX}{key}")

    async def delete(self, key: str) -> None:
        await redis_client.delete(f"{LOCK_PREFIX}{key}")
        await redis_client.delete(f"{RESULT_PREFIX}{key}")
```

---

### 3. Database upserts — idempotent writes

```sql
-- PostgreSQL — INSERT ... ON CONFLICT DO NOTHING (ignore duplicates)
INSERT INTO email_logs (idempotency_key, user_id, template_id, sent_at)
VALUES ($1, $2, $3, now())
ON CONFLICT (idempotency_key) DO NOTHING;

-- INSERT ... ON CONFLICT DO UPDATE (upsert — last write wins)
INSERT INTO user_preferences (user_id, theme, updated_at)
VALUES ($1, $2, now())
ON CONFLICT (user_id)
DO UPDATE SET theme = EXCLUDED.theme, updated_at = EXCLUDED.updated_at;
```

```python
# SQLAlchemy — upsert with on_conflict_do_nothing
from sqlalchemy.dialects.postgresql import insert

stmt = insert(EmailLog).values(
    idempotency_key=key,
    user_id=user_id,
    template_id=template_id,
)
stmt = stmt.on_conflict_do_nothing(index_elements=["idempotency_key"])
await db.execute(stmt)
```

```ts
// Prisma — upsert
await prisma.emailLog.upsert({
  where:  { idempotency_key: key },
  update: {},                           // on duplicate: do nothing
  create: { idempotency_key: key, user_id, template_id },
});
```

---

### 4. Background jobs — idempotent handlers

Every job handler must be safe to run more than once. See the `background-jobs` skill for
queue setup — this section covers the handler contract.

```python
# workers/email_worker.py
async def handle_send_email(job_data: dict) -> None:
    idempotency_key = job_data["idempotency_key"]

    # Check: already sent?
    already_sent = await db.email_logs.find_one({"idempotency_key": idempotency_key})
    if already_sent:
        logger.info(
            "Email already sent, skipping. key=%s sent_at=%s",
            idempotency_key, already_sent["sent_at"],
        )
        return   # safe to return — job succeeded on a previous attempt

    # Do the work
    await email_provider.send(
        to=job_data["to"],
        template_id=job_data["template_id"],
    )

    # Record completion atomically
    await db.email_logs.insert_one({
        "idempotency_key": idempotency_key,
        "sent_at": datetime.utcnow(),
    })
```

---

### 5. At-least-once vs exactly-once

| Delivery | Guarantee | What it means for your code |
|----------|----------|----------------------------|
| **At-most-once** | May be lost | Simple but lossy; use only when loss is acceptable |
| **At-least-once** | Will be delivered, may be duplicated | Handler must be idempotent |
| **Exactly-once** | Delivered once and only once | Requires distributed transaction or idempotency key + dedup at consumer |

Most queues (SQS, Kafka, BullMQ, RabbitMQ) guarantee **at-least-once** by default.
Design all consumers as if duplicates will arrive — because they will.

**Exactly-once in practice (Kafka transactions + consumer dedup):**
```python
# Consumer — deduplicate using the message offset or a business key
async def consume(message):
    dedup_key = f"kafka:{message.topic}:{message.partition}:{message.offset}"

    inserted = await db.execute(
        "INSERT INTO processed_messages (dedup_key) VALUES ($1) ON CONFLICT DO NOTHING",
        dedup_key,
    )
    if inserted.rowcount == 0:
        logger.info("Duplicate message skipped. key=%s", dedup_key)
        return

    await process(message.value)
```

---

### 6. Idempotency key generation — client side

```ts
// Generate a stable key per logical operation, not per retry
// Use UUID v4 — random, collision probability negligible
import { randomUUID } from 'crypto';

// ✅ Generated once per user action, stored client-side, reused on retry
async function submitOrder(cart: Cart): Promise<Order> {
  const idempotencyKey = randomUUID();   // generate once, store in state

  return fetchWithRetry('/api/orders', {
    method: 'POST',
    headers: { 'Idempotency-Key': idempotencyKey },
    body: JSON.stringify(cart),
  });
}

// ✅ For background jobs — derive the key from the business event, not random
// This makes keys stable across process restarts
const idempotencyKey = `order-confirmation:${orderId}:${version}`;
```

### Rules

- Every POST and PATCH endpoint that creates a resource or triggers a side effect must
  support an idempotency key header.
- Store results before returning them — if the process crashes after executing but before
  responding, the next retry must get the same result.
- Use `ON CONFLICT DO NOTHING` for deduplication at the database level — it is atomic and
  does not require application-level locking.
- Release the lock on failure so the caller can retry with the same key.
- Idempotency keys must expire. Storage that never expires grows without bound.
- Never reuse a key for a different operation. The key is tied to the exact logical operation,
  not just the endpoint.
