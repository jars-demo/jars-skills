---
name: input-validation
description: Validating and sanitising all external input at the boundary before it reaches business logic: schema validation with Pydantic/Zod/Joi, type coercion traps, allow-lists over block-lists, rejecting unexpected fields, URL and file upload validation, preventing injection through input shape, and returning precise error messages that help callers fix their request without leaking internals. Use when you want to add input validation, validate a request body, sanitise user input, prevent injection, validate file uploads, validate query params, return proper validation errors, or ensure bad data fails at the boundary.
---

## input-validation

Validate everything that comes from outside the process. Fail loudly at the boundary —
never let bad data reach business logic silently.

### 1. The boundary rule

External input includes: HTTP request bodies, query params, path params, headers, file
uploads, environment variables, CLI args, message queue payloads, webhook bodies, and
data read from files the user provides.

```
External input
    ↓
Validate at the boundary (route / consumer / CLI entrypoint)
    ↓  reject with clear error if invalid
Business logic receives only clean, typed data
    ↓
Database / external service
```

Never pass `request.body` or `event.data` directly into a service or repository.
The service layer must receive already-validated, typed objects.

---

### 2. Python — Pydantic

```python
# schemas/order_schema.py
"""
schemas/order_schema.py
-----------------------
Request/response schemas for order endpoints.
Validated by Pydantic before reaching the service layer.

Depends on: pydantic
Used by:    routes/order_routes.py
"""

from decimal import Decimal
from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Annotated


class CreateOrderRequest(BaseModel):
    # Reject unknown fields entirely — never silently ignore them
    model_config = {"extra": "forbid"}

    product_id: int = Field(gt=0, description="Must be a positive integer")
    quantity:   int = Field(ge=1, le=100, description="1–100 units per order")
    note:       str | None = Field(
        default=None,
        max_length=500,
        description="Optional buyer note, max 500 chars",
    )

    @field_validator("note")
    @classmethod
    def note_no_html(cls, v: str | None) -> str | None:
        """Reject notes containing HTML tags — we do not sanitise, we reject."""
        if v and "<" in v:
            raise ValueError("Note must not contain HTML")
        return v


class OrderLineItem(BaseModel):
    model_config = {"extra": "forbid"}

    product_id: int = Field(gt=0)
    quantity:   int = Field(ge=1, le=100)
    unit_price: Annotated[Decimal, Field(gt=0, decimal_places=2)]


class CreateBulkOrderRequest(BaseModel):
    model_config = {"extra": "forbid"}

    items: list[OrderLineItem] = Field(min_length=1, max_length=50)

    @model_validator(mode="after")
    def no_duplicate_products(self) -> "CreateBulkOrderRequest":
        ids = [i.product_id for i in self.items]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate product_id in items")
        return self
```

```python
# routes/order_routes.py
from fastapi import APIRouter
from schemas.order_schema import CreateOrderRequest
from services.order_service import OrderService

router = APIRouter(prefix="/orders")

@router.post("/", status_code=201)
async def create_order(body: CreateOrderRequest):
    # FastAPI calls Pydantic validation before this handler runs.
    # body is already a typed, validated CreateOrderRequest — not raw JSON.
    return await OrderService().create(body)
```

FastAPI returns a `422 Unprocessable Entity` with field-level errors automatically when
Pydantic validation fails — no extra code needed.

---

### 3. TypeScript — Zod

```ts
// schemas/orderSchema.ts
/**
 * schemas/orderSchema.ts
 * ----------------------
 * Zod schemas for order request validation.
 * Parse at the route boundary; pass typed objects to services.
 *
 * Depends on: zod
 * Used by:    routes/orderRoutes.ts
 */

import { z } from 'zod';

export const createOrderSchema = z.object({
  product_id: z.number().int().positive(),
  quantity:   z.number().int().min(1).max(100),
  note:       z.string().max(500).refine(
    (v) => !v.includes('<'),
    { message: 'Note must not contain HTML' }
  ).optional(),
}).strict();   // .strict() = reject unknown fields, equivalent to Pydantic's extra='forbid'

export type CreateOrderInput = z.infer<typeof createOrderSchema>;

export const bulkOrderSchema = z.object({
  items: z.array(z.object({
    product_id: z.number().int().positive(),
    quantity:   z.number().int().min(1).max(100),
    unit_price: z.number().positive().multipleOf(0.01),
  })).min(1).max(50),
}).strict().refine(
  (data) => new Set(data.items.map(i => i.product_id)).size === data.items.length,
  { message: 'Duplicate product_id in items' }
);
```

```ts
// routes/orderRoutes.ts
import { Router, Request, Response } from 'express';
import { createOrderSchema } from '../schemas/orderSchema';
import { OrderService } from '../services/orderService';

const router = Router();

router.post('/', async (req: Request, res: Response) => {
  const result = createOrderSchema.safeParse(req.body);

  if (!result.success) {
    // Return field-level errors — helpful to callers, leaks nothing internal
    return res.status(422).json({
      error: 'Validation failed',
      details: result.error.flatten().fieldErrors,
    });
  }

  // result.data is fully typed CreateOrderInput — not raw req.body
  const order = await OrderService.create(result.data);
  return res.status(201).json(order);
});
```

---

### 4. Validate query params and path params too

Request bodies are not the only attack surface.

```python
# FastAPI — path and query params validated with type annotations + Field
from fastapi import APIRouter, Query, Path

router = APIRouter()

@router.get("/orders/{order_id}")
async def get_order(
    order_id: int = Path(gt=0),                           # must be positive int
    status:   str | None = Query(
        default=None,
        pattern="^(pending|confirmed|cancelled)$",        # allow-list, not block-list
    ),
    page:     int = Query(default=1, ge=1),
    limit:    int = Query(default=20, ge=1, le=100),
):
    ...
```

```ts
// Zod — validate query params explicitly, never trust req.query types
const listOrdersQuery = z.object({
  status: z.enum(['pending', 'confirmed', 'cancelled']).optional(),
  page:   z.coerce.number().int().min(1).default(1),    // coerce: query params arrive as strings
  limit:  z.coerce.number().int().min(1).max(100).default(20),
});

router.get('/', (req, res) => {
  const result = listOrdersQuery.safeParse(req.query);
  if (!result.success) return res.status(422).json({ error: result.error.flatten() });
  const { status, page, limit } = result.data;   // typed, coerced
  ...
});
```

---

### 5. File upload validation

Never trust file MIME type from the client — it is set by the browser and trivially spoofed.
Validate the actual file content (magic bytes).

```python
import imghdr
from fastapi import UploadFile, HTTPException

ALLOWED_IMAGE_TYPES = {"jpeg", "png", "webp"}
MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024   # 5 MB

async def validate_image_upload(file: UploadFile) -> bytes:
    content = await file.read()

    # Size check
    if len(content) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds 5 MB limit")

    # Magic bytes check — not the Content-Type header
    detected = imghdr.what(None, h=content)
    if detected not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type. Allowed: {', '.join(ALLOWED_IMAGE_TYPES)}",
        )

    return content
```

```ts
import fileType from 'file-type';   // npm install file-type

const ALLOWED_MIME_TYPES = new Set(['image/jpeg', 'image/png', 'image/webp']);
const MAX_BYTES = 5 * 1024 * 1024;

async function validateImageUpload(buffer: Buffer): Promise<void> {
  if (buffer.length > MAX_BYTES) {
    throw new ValidationError('File exceeds 5 MB limit');
  }
  const type = await fileType.fromBuffer(buffer);
  if (!type || !ALLOWED_MIME_TYPES.has(type.mime)) {
    throw new ValidationError('Unsupported file type');
  }
}
```

---

### 6. Allow-lists over block-lists

Block-lists enumerate the bad — attackers just find what is not on the list.
Allow-lists enumerate the good — anything not explicitly allowed is rejected.

```python
# ❌ Block-list — blocks known bad values, misses everything else
BLOCKED_STATUSES = {"hack", "drop", "delete"}
if status in BLOCKED_STATUSES:
    raise ValueError("Invalid status")

# ✅ Allow-list — only accepts known good values
VALID_STATUSES = {"pending", "confirmed", "cancelled", "refunded"}
if status not in VALID_STATUSES:
    raise ValueError(f"Invalid status. Must be one of: {', '.join(sorted(VALID_STATUSES))}")

# ❌ Block-list file extension check
BLOCKED_EXTENSIONS = {".exe", ".sh", ".bat"}
if ext in BLOCKED_EXTENSIONS:
    raise ValueError("File type not allowed")

# ✅ Allow-list
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".pdf"}
if ext not in ALLOWED_EXTENSIONS:
    raise ValueError(f"File type not allowed. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}")
```

---

### 7. Return precise errors — helpful to callers, silent on internals

Validation errors must tell the caller exactly what is wrong and how to fix it.
They must never reveal stack traces, database errors, or internal field names.

```python
# ❌ Vague — caller cannot fix this
{"error": "Bad request"}

# ❌ Leaks internals — reveals DB column name and constraint
{"error": "violates check constraint orders_quantity_check"}

# ✅ Precise and actionable — field-level, fixable
{
  "error": "Validation failed",
  "details": {
    "quantity": ["Must be between 1 and 100"],
    "note":     ["Must not contain HTML"]
  }
}
```

```python
# FastAPI + Pydantic — override the default 422 handler to control the format
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

app = FastAPI()

@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    errors = {}
    for error in exc.errors():
        field = ".".join(str(loc) for loc in error["loc"] if loc != "body")
        errors.setdefault(field, []).append(error["msg"])
    return JSONResponse(status_code=422, content={"error": "Validation failed", "details": errors})
```

---

### 8. Type coercion traps to avoid

```python
# ❌ int() silently truncates floats and accepts strings
quantity = int(request.json.get("quantity"))   # "1.9" → 1, "abc" → ValueError uncaught

# ✅ Pydantic Field(ge=1) with type annotation int rejects "1.9" and "abc" with clear errors

# ❌ Truthy check passes 0, empty string, and None inconsistently
if request.json.get("product_id"):   # 0 fails silently
    ...

# ✅ Explicit None check with schema validation
product_id: int = Field(gt=0)   # 0 rejected with "Input should be greater than 0"
```

```ts
// ❌ Number() coerces silently — "" → 0, "abc" → NaN, null → 0
const quantity = Number(req.body.quantity);

// ✅ Zod coerce + validation — rejects NaN, enforces range
quantity: z.coerce.number().int().min(1).max(100)
```

### Rules

- Validate at the boundary — the route handler or queue consumer. Never deeper.
- Reject unknown fields (`extra="forbid"` / `.strict()`). Mass-assignment vulnerabilities
  come from accepting fields the code did not expect.
- Use allow-lists for enumerated values. Never block-lists.
- Validate file content by magic bytes, not by the client-supplied Content-Type header.
- Return field-level errors that tell the caller exactly what to fix. Return nothing that
  reveals internal structure, stack traces, or database error messages.
- Never sanitise HTML in free-text fields — reject it. Sanitisation libraries have edge cases;
  rejection has none.
- Coercion must be explicit and bounded. A string that cannot cleanly coerce to the expected
  type should fail validation, not silently become 0 or NaN.
