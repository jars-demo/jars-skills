---
name: multi-tenancy
description: Designing and implementing multi-tenant data isolation: chooses between row-level, schema-per-tenant, and database-per-tenant strategies, propagates tenant context through the request lifecycle, enforces tenant scoping at the repository layer so business logic never touches another tenant's data, applies Row Level Security in PostgreSQL, and audits for tenant leakage bugs. Use when you want to add multi-tenancy, isolate tenant data, implement row-level security, propagate tenant context, prevent cross-tenant data leaks, add a tenant_id to queries, build a SaaS application, or audit for tenant isolation bugs.
---

## multi-tenancy

Pick the isolation strategy first. Enforce it at the data layer — never rely on
application code alone to keep tenants separate.

### 1. Choose the isolation strategy

| Strategy | Isolation | Cost | Use when |
|----------|----------|------|---------|
| **Row-level** (`tenant_id` column) | Logical | Low | Most SaaS apps, shared schema acceptable |
| **Schema-per-tenant** | Medium | Medium | Regulated data, easy per-tenant migrations |
| **Database-per-tenant** | Physical | High | Enterprise customers, strict data residency |

**Row-level is the right default** for most SaaS products. Schema-per-tenant adds
operational complexity without meaningful security improvement for most threat models.
Database-per-tenant is only justified when contractual or regulatory requirements demand
physical isolation.

This skill covers row-level isolation in depth — it is the most common and the most
likely to have subtle bugs.

---

### 2. Tenant context — propagate through the request lifecycle

Every request carries a tenant. Resolve it once at the boundary (middleware), store it
in a context variable, and read it everywhere else. Never pass `tenant_id` as a function
argument through every layer — that pattern is fragile and easily forgotten.

```python
# lib/tenant_context.py
"""
lib/tenant_context.py
----------------------
Thread/task-local tenant context. Set once per request in middleware.
All repositories read from here — never from function arguments.

Depends on: nothing (stdlib only)
Used by:    middleware/tenant_middleware.py, repositories/*
"""

from contextvars import ContextVar
from lib.logger import get_logger

logger = get_logger(__name__)

_tenant_id: ContextVar[str | None] = ContextVar("tenant_id", default=None)


def set_tenant(tenant_id: str) -> None:
    _tenant_id.set(tenant_id)


def get_tenant() -> str:
    tid = _tenant_id.get()
    if not tid:
        raise RuntimeError(
            "Tenant context not set. Ensure TenantMiddleware runs before this code."
        )
    return tid


def get_tenant_or_none() -> str | None:
    return _tenant_id.get()
```

```python
# middleware/tenant_middleware.py
"""
middleware/tenant_middleware.py
--------------------------------
Resolves tenant from JWT sub-claim or X-Tenant-ID header.
Must run before any route handler or repository call.

Depends on: lib/tenant_context.py, lib/auth.py
Used by:    main.py (registered as FastAPI middleware)
"""

from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from lib.tenant_context import set_tenant
from lib.auth import decode_jwt
from lib.logger import get_logger

logger = get_logger(__name__)

SKIP_PATHS = {"/health", "/metrics", "/docs", "/openapi.json"}


class TenantMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path in SKIP_PATHS:
            return await call_next(request)

        tenant_id = await self._resolve_tenant(request)
        if not tenant_id:
            raise HTTPException(status_code=401, detail="Tenant could not be resolved")

        set_tenant(tenant_id)
        logger.info("Tenant resolved. tenant_id=%s path=%s", tenant_id, request.url.path)
        return await call_next(request)

    async def _resolve_tenant(self, request: Request) -> str | None:
        # Primary: resolve from JWT (preferred — authenticated)
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header.removeprefix("Bearer ")
            try:
                claims = decode_jwt(token)
                return claims.get("tenant_id")
            except Exception as exc:
                logger.warning("JWT decode failed in tenant middleware. error=%s", exc)
                return None

        # Fallback: explicit header (for service-to-service calls with pre-auth)
        return request.headers.get("X-Tenant-ID")
```

---

### 3. Repository layer — enforce tenant scoping here, nowhere else

The repository is the only place that touches SQL. It is the correct and final place to
enforce tenant isolation. Business logic must never pass raw `tenant_id` into queries —
it reads from context and the repository applies it.

```python
# repositories/base_repository.py
"""
repositories/base_repository.py
---------------------------------
Base class for all tenant-scoped repositories.
Subclasses inherit _tenant_id and _scope() automatically.

Depends on: lib/tenant_context.py, lib/db.py
Used by:    repositories/*
"""

from lib.tenant_context import get_tenant
from lib.db import db
from lib.logger import get_logger

logger = get_logger(__name__)


class TenantRepository:
    """All queries in subclasses must call self._scope() to add tenant_id filter."""

    @property
    def _tenant_id(self) -> str:
        return get_tenant()

    def _scope(self, query: str, params: dict) -> tuple[str, dict]:
        """Append tenant_id filter to any WHERE clause."""
        connector = "WHERE" if "WHERE" not in query.upper() else "AND"
        scoped_query = f"{query} {connector} tenant_id = :tenant_id"
        return scoped_query, {**params, "tenant_id": self._tenant_id}
```

```python
# repositories/order_repository.py
"""
repositories/order_repository.py
----------------------------------
All DB operations for orders — always tenant-scoped.

Depends on: repositories/base_repository.py
Used by:    services/order_service.py
"""

from repositories.base_repository import TenantRepository


class OrderRepository(TenantRepository):

    async def find_by_id(self, order_id: int) -> dict | None:
        query, params = self._scope(
            "SELECT * FROM orders WHERE id = :id",
            {"id": order_id},
        )
        # Final query: SELECT * FROM orders WHERE id = :id AND tenant_id = :tenant_id
        return await db.fetch_one(query, params)

    async def list_recent(self, limit: int = 20) -> list[dict]:
        query, params = self._scope(
            "SELECT id, total, status, created_at FROM orders ORDER BY created_at DESC LIMIT :limit",
            {"limit": limit},
        )
        rows = await db.fetch_all(query, params)
        return [dict(r) for r in rows]

    async def create(self, total: int, status: str) -> dict:
        # tenant_id always injected from context — never from caller
        row = await db.fetch_one(
            "INSERT INTO orders (tenant_id, total, status) VALUES (:tenant_id, :total, :status) RETURNING *",
            {"tenant_id": self._tenant_id, "total": total, "status": status},
        )
        return dict(row)
```

---

### 4. PostgreSQL Row Level Security — enforce at the database level too

RLS is a second line of defence. Even if application code has a bug, the database
refuses to return another tenant's rows.

```sql
-- Enable RLS on every tenant-scoped table
ALTER TABLE orders ENABLE ROW LEVEL SECURITY;
ALTER TABLE orders FORCE ROW LEVEL SECURITY;   -- applies to table owner too

-- Policy: app DB user can only see rows matching the session variable
CREATE POLICY tenant_isolation ON orders
  USING (tenant_id = current_setting('app.tenant_id', TRUE));

-- The application sets the variable at the start of each transaction:
-- SET LOCAL app.tenant_id = 'tenant_abc';
```

```python
# lib/db.py — set the RLS variable on every connection checkout
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import create_async_engine
from lib.tenant_context import get_tenant_or_none

engine = create_async_engine(settings.database_url)

@event.listens_for(engine.sync_engine, "connect")
def set_rls_variable(dbapi_connection, connection_record):
    # Called when a connection is first created — set safe default
    cursor = dbapi_connection.cursor()
    cursor.execute("SET app.tenant_id = ''")
    cursor.close()


async def get_scoped_connection():
    """Get a connection with the current tenant's RLS variable set."""
    tenant_id = get_tenant_or_none() or ""
    async with engine.connect() as conn:
        await conn.execute(text(f"SET LOCAL app.tenant_id = '{tenant_id}'"))
        yield conn
```

---

### 5. Schema and migration requirements

Every tenant-scoped table needs:

```sql
-- Every tenant-scoped table must have:
ALTER TABLE orders ADD COLUMN tenant_id TEXT NOT NULL;

-- Composite indexes: tenant_id first, then query columns
-- Without this, row-level filtering does a full table scan per query
CREATE INDEX idx_orders_tenant_status     ON orders (tenant_id, status);
CREATE INDEX idx_orders_tenant_created_at ON orders (tenant_id, created_at DESC);

-- Foreign keys reference within the same tenant (use partial unique constraints)
CREATE UNIQUE INDEX idx_orders_tenant_external_id
  ON orders (tenant_id, external_id);
```

---

### 6. Audit for tenant leakage

These patterns cause cross-tenant data leaks. Search for them actively.

```bash
# Find queries that may be missing tenant_id filter
grep -rn "FROM orders" src/ --include="*.py" | grep -v "tenant_id"
grep -rn "db.fetch" src/ --include="*.py" | grep -v "tenant_id"

# Find places that read tenant_id from request body instead of context
grep -rn "tenant_id" src/routes --include="*.py"
# tenant_id should NEVER appear in route handlers — only in repositories
```

**Common leakage patterns:**

| Pattern | Risk | Fix |
|---------|------|-----|
| `WHERE id = :id` without `tenant_id` | Returns any tenant's row by ID | Always use `_scope()` |
| `tenant_id` in request body | Caller supplies their own tenant | Read from context only |
| Background job missing tenant context | Processes wrong tenant's data | Set context from job payload |
| `COUNT(*)` without tenant filter | Leaks row counts to other tenants | Scope all aggregate queries |
| Cache key without tenant prefix | Tenant A reads tenant B's cached response | Prefix: `{tenant_id}:{key}` |

```python
# ✅ Cache key with tenant prefix
from lib.tenant_context import get_tenant

cache_key = f"{get_tenant()}:user:{user_id}"
```

```python
# ✅ Background job — set tenant context from job payload
async def handle_invoice_job(job_data: dict) -> None:
    from lib.tenant_context import set_tenant
    set_tenant(job_data["tenant_id"])   # must be first line
    # now all repository calls are scoped to the correct tenant
    await invoice_service.generate(job_data["order_id"])
```

### Rules

- Enforce tenant scoping at the repository layer. Business logic must never add
  `WHERE tenant_id = x` manually — it must come from the base repository automatically.
- Never accept `tenant_id` from the request body or query params. Resolve it from the
  authenticated JWT or session only.
- Prefix every cache key with `tenant_id`. A cache miss is far better than a cross-tenant
  data leak.
- Set tenant context as the first line of every background job handler.
- Enable PostgreSQL RLS as a second line of defence — it catches application-layer bugs
  that would otherwise silently leak data.
- Index `(tenant_id, <query_column>)` on every scoped table. Without it, every query
  scans the entire table and filters — performance collapses as tenant count grows.
