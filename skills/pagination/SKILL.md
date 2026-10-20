---
name: pagination
description: Designing and implementing pagination that stays fast at scale: chooses cursor/keyset pagination over OFFSET for large datasets, encodes opaque cursors, returns consistent page metadata, handles the total-count tradeoff, and avoids the common bugs that cause duplicate or missing records when data changes between pages. Use when you want to add pagination, implement cursor pagination, fix slow OFFSET queries, paginate an API response, design a paginated list endpoint, return next page token, or handle large dataset pagination.
---

## pagination

Pick the right strategy first. Implement it once, correctly, so it never needs to be
rewritten when the table hits a million rows.

### 1. Choose the strategy

| Strategy | How it works | Use when |
|----------|-------------|---------|
| **Offset** (`LIMIT n OFFSET k`) | Skip k rows, return n | Small datasets (< 50k rows), admin UIs where users jump to page N |
| **Keyset / cursor** | `WHERE (created_at, id) < (last_seen_at, last_seen_id)` | Large datasets, infinite scroll, APIs consumed by mobile or external callers |
| **Seek with encoded cursor** | Same as keyset but cursor is opaque base64/JWT | Public APIs where callers must not construct cursors manually |

**Never use OFFSET on large tables.** `OFFSET 10000` scans and discards 10,000 rows on
every request. At page 500 of a 100-row page it scans 50,000 rows just to throw them away.
Performance degrades linearly with page depth.

---

### 2. Offset pagination — when it is acceptable

```python
# repositories/product_repository.py

async def list_products_offset(
    page: int,       # 1-indexed
    limit: int = 20,
) -> dict:
    offset = (page - 1) * limit

    rows = await db.fetch_all(
        "SELECT id, name, price FROM products ORDER BY id LIMIT :limit OFFSET :offset",
        {"limit": limit, "offset": offset},
    )

    # Total count is expensive on large tables — only include when necessary
    total = await db.fetch_val("SELECT COUNT(*) FROM products")

    return {
        "items":       [dict(r) for r in rows],
        "page":        page,
        "limit":       limit,
        "total":       total,
        "total_pages": -(-total // limit),   # ceiling division
        "has_next":    offset + limit < total,
        "has_prev":    page > 1,
    }
```

**The total count problem:** `SELECT COUNT(*)` on a large table takes a full sequential
scan. On a 10M-row table it can take seconds. Options:
- Skip it — return `has_next` only, no total
- Use `pg_class.reltuples` for an approximate count (fast, ~1% error)
- Cache it with a short TTL

```sql
-- Approximate count — fast, acceptable for UI display
SELECT reltuples::bigint AS estimate FROM pg_class WHERE relname = 'products';
```

---

### 3. Cursor / keyset pagination — the correct default for APIs

The cursor encodes the last item seen. The next query picks up exactly where the previous
one left off — no skipping, no duplicates, O(1) regardless of depth.

```python
# repositories/order_repository.py
"""
repositories/order_repository.py
---------------------------------
Keyset pagination for orders. Cursors are stable even when new rows are inserted.

Depends on: lib/cursor.py
Used by:    services/order_service.py
"""

import base64, json
from lib.logger import get_logger

logger = get_logger(__name__)


def encode_cursor(created_at: str, id: int) -> str:
    """Encode pagination position as an opaque base64 string."""
    payload = json.dumps({"created_at": created_at, "id": id})
    return base64.urlsafe_b64encode(payload.encode()).decode()


def decode_cursor(cursor: str) -> tuple[str, int] | None:
    """Decode cursor. Returns None if invalid — caller treats as first page."""
    try:
        payload = json.loads(base64.urlsafe_b64decode(cursor.encode()))
        return payload["created_at"], payload["id"]
    except Exception:
        logger.warning("Invalid pagination cursor received. cursor=%s", cursor[:32])
        return None


async def list_orders(
    cursor: str | None = None,
    limit: int = 20,
    status: str | None = None,
) -> dict:
    limit = min(max(limit, 1), 100)   # clamp: 1–100
    params: dict = {"limit": limit + 1}   # fetch one extra to determine has_next

    # Build WHERE clause
    filters = []
    if status:
        filters.append("status = :status")
        params["status"] = status

    if cursor:
        position = decode_cursor(cursor)
        if position:
            created_at, last_id = position
            # Keyset condition — stable sort on (created_at DESC, id DESC)
            filters.append(
                "(created_at < :cur_created_at OR "
                "(created_at = :cur_created_at AND id < :cur_id))"
            )
            params["cur_created_at"] = created_at
            params["cur_id"]         = last_id

    where = ("WHERE " + " AND ".join(filters)) if filters else ""
    query = f"""
        SELECT id, status, total, created_at
        FROM orders
        {where}
        ORDER BY created_at DESC, id DESC
        LIMIT :limit
    """

    rows = await db.fetch_all(query, params)
    items = [dict(r) for r in rows]

    # Determine if there is a next page using the extra row
    has_next = len(items) > limit
    if has_next:
        items = items[:limit]   # drop the extra row from the response

    # Encode cursor from the last item in this page
    next_cursor = None
    if has_next and items:
        last = items[-1]
        next_cursor = encode_cursor(str(last["created_at"]), last["id"])

    logger.info("Orders listed. count=%d has_next=%s", len(items), has_next)

    return {
        "items":       items,
        "next_cursor": next_cursor,   # null when on the last page
        "has_next":    has_next,
        "limit":       limit,
    }
```

---

### 4. TypeScript — Zod-validated cursor endpoint

```ts
// schemas/paginationSchema.ts
import { z } from 'zod';

export const cursorPageSchema = z.object({
  cursor: z.string().optional(),
  limit:  z.coerce.number().int().min(1).max(100).default(20),
});

export type CursorPageInput = z.infer<typeof cursorPageSchema>;
```

```ts
// lib/cursor.ts
/**
 * lib/cursor.ts
 * -------------
 * Encode and decode opaque pagination cursors.
 * Callers must not construct cursors manually — always use encode/decode.
 *
 * Depends on: nothing (stdlib only)
 * Used by:    repositories that implement cursor pagination
 */

export function encodeCursor(fields: Record<string, unknown>): string {
  return Buffer.from(JSON.stringify(fields)).toString('base64url');
}

export function decodeCursor(cursor: string): Record<string, unknown> | null {
  try {
    return JSON.parse(Buffer.from(cursor, 'base64url').toString('utf8'));
  } catch {
    return null;
  }
}
```

```ts
// routes/orderRoutes.ts
router.get('/', async (req, res) => {
  const result = cursorPageSchema.safeParse(req.query);
  if (!result.success) return res.status(422).json({ error: result.error.flatten() });

  const { cursor, limit } = result.data;
  const page = await OrderRepository.list({ cursor, limit });
  return res.json(page);
});
```

---

### 5. Response shape — be consistent

Pick one shape and use it everywhere in the API. Inconsistent pagination shapes are one
of the most common API usability complaints.

```json
// Cursor-based (recommended for public APIs)
{
  "items": [...],
  "next_cursor": "eyJjcmVhdGVkX2F0IjoiMjAyNi0xMC0yMVQwMDowMDowMFoiLCJpZCI6NDJ9",
  "has_next": true,
  "limit": 20
}

// Offset-based (acceptable for internal/admin UIs)
{
  "items": [...],
  "page": 3,
  "limit": 20,
  "total": 847,
  "total_pages": 43,
  "has_next": true,
  "has_prev": true
}
```

---

### 6. Index requirement — cursors need a composite index

Keyset pagination is only fast if the sort columns are indexed together.

```sql
-- Supports: ORDER BY created_at DESC, id DESC
-- AND the WHERE (created_at, id) < (?, ?) keyset condition
CREATE INDEX idx_orders_created_id ON orders (created_at DESC, id DESC);

-- With a filter column — equality filters must come first in the index
-- Supports: WHERE status = ? ORDER BY created_at DESC, id DESC
CREATE INDEX idx_orders_status_created_id ON orders (status, created_at DESC, id DESC);
```

Run `EXPLAIN ANALYZE` on the paginated query to confirm the index is used. If you see
`Seq Scan` or `Sort` in the plan, the index is wrong or missing.

---

### 7. Common bugs to avoid

| Bug | Cause | Fix |
|-----|-------|-----|
| Duplicate records across pages | OFFSET while rows inserted between requests | Switch to keyset pagination |
| Missing records across pages | OFFSET while rows deleted between requests | Switch to keyset pagination |
| Cursor breaks after sort order change | Cursor encodes old sort fields | Version the cursor or treat old cursors as invalid |
| `limit=0` returns all rows | No lower bound on limit | Clamp: `limit = max(1, min(limit, 100))` |
| Total count times out | `COUNT(*)` on large table | Use approximate count or drop total entirely |
| Cursor leaks internal IDs | Unencoded `?cursor=42` in URL | Always encode cursors as opaque base64 |

### Rules

- Default to cursor pagination for any endpoint that may grow beyond 50k rows.
- Always clamp `limit` to a maximum (100 is a reasonable default). Never let callers
  request unbounded pages.
- Encode cursors as opaque strings — callers must not construct or parse them.
  If a cursor is invalid or expired, treat it as the first page, not an error.
- The sort columns in the keyset condition must exactly match the composite index.
  Verify with EXPLAIN ANALYZE before shipping.
- Keep the pagination shape consistent across all list endpoints in the API.
  Inconsistency is a developer experience problem that is never worth the tradeoff.
