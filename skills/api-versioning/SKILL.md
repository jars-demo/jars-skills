---
name: api-versioning
description: Designing and evolving APIs without breaking existing clients: chooses the right versioning strategy (URL path, header, query param), distinguishes breaking from non-breaking changes, implements a deprecation lifecycle with Sunset headers, routes version traffic cleanly, and manages the migration window so old versions can eventually be retired. Use when you want to version an API, add a new API version, deprecate an old endpoint, make a breaking change safely, add Sunset headers, design a v2 API, migrate clients from v1 to v2, or retire an old API version.
---

## api-versioning

Version from the first breaking change, not from day one. Once clients depend on a
contract, you cannot change it without a version boundary.

### 1. Breaking vs non-breaking changes

Know the difference before touching anything.

**Non-breaking — safe to ship without a new version:**
- Adding a new optional field to a response
- Adding a new optional request field with a default
- Adding a new endpoint
- Relaxing a validation rule (accepting more values)
- Adding a new enum value (if clients ignore unknown values)

**Breaking — requires a new version:**
- Removing a field from a response
- Renaming a field
- Changing a field's type
- Making an optional field required
- Changing a URL, HTTP method, or status code
- Changing error response shape
- Removing an endpoint

---

### 2. Choose a versioning strategy

| Strategy | Example | Pros | Cons |
|----------|---------|------|------|
| **URL path** | `/v1/users`, `/v2/users` | Explicit, cacheable, easy to test | URL changes between versions |
| **Header** | `Accept: application/vnd.api+json;version=2` | Clean URLs | Harder to test in browser |
| **Query param** | `/users?version=2` | Easy to add | Pollutes query string, cache-unfriendly |

**URL path versioning is the right default** for most REST APIs — explicit, bookmarkable,
and works with every HTTP client without special headers.

---

### 3. URL path versioning — clean implementation

```python
# routes/__init__.py
"""
routes/__init__.py
------------------
Registers all versioned routers. New versions added here only.

Depends on: routes/v1/, routes/v2/
Used by:    main.py
"""

from fastapi import FastAPI
from routes.v1 import router as v1_router
from routes.v2 import router as v2_router


def register_routes(app: FastAPI) -> None:
    app.include_router(v1_router, prefix="/v1")
    app.include_router(v2_router, prefix="/v2")
```

```python
# routes/v1/user_routes.py
"""
routes/v1/user_routes.py
------------------------
V1 user endpoints. Frozen — no new features added here.
Clients should migrate to /v2/users. Sunset: 2027-01-01.

Depends on: services/user_service.py, schemas/v1/user_schema.py
Used by:    routes/__init__.py
"""

from fastapi import APIRouter
from schemas.v1.user_schema import UserResponseV1
from services.user_service import UserService
from lib.deprecation import add_deprecation_headers

router = APIRouter(prefix="/users", tags=["users-v1"])


@router.get("/{user_id}", response_model=UserResponseV1)
async def get_user_v1(user_id: int, response: Response):
    add_deprecation_headers(
        response,
        sunset="2027-01-01",
        link='</v2/users/{user_id}>; rel="successor-version"',
    )
    user = await UserService().get_user(user_id)
    return UserResponseV1(
        id=user.id,
        name=user.display_name,   # v1 used 'name' — v2 uses 'display_name'
        email=user.email,
    )
```

```python
# routes/v2/user_routes.py
"""
routes/v2/user_routes.py
------------------------
V2 user endpoints — current stable version.

Depends on: services/user_service.py, schemas/v2/user_schema.py
Used by:    routes/__init__.py
"""

from fastapi import APIRouter
from schemas.v2.user_schema import UserResponseV2
from services.user_service import UserService

router = APIRouter(prefix="/users", tags=["users-v2"])


@router.get("/{user_id}", response_model=UserResponseV2)
async def get_user_v2(user_id: int):
    user = await UserService().get_user(user_id)
    return UserResponseV2(
        id=user.id,
        display_name=user.display_name,   # renamed from 'name' in v1
        email=user.email,
        created_at=user.created_at,       # new field in v2
        avatar_url=user.avatar_url,       # new field in v2
    )
```

---

### 4. Deprecation headers — tell clients before you remove

RFC 8594 defines the `Sunset` header. Use it so clients can programmatically detect
deprecated endpoints and alert their engineers.

```python
# lib/deprecation.py
"""
lib/deprecation.py
------------------
Helpers for adding RFC 8594 deprecation and sunset headers.

Depends on: nothing (stdlib only)
Used by:    routes/v1/*
"""

from fastapi import Response
from lib.logger import get_logger

logger = get_logger(__name__)


def add_deprecation_headers(
    response: Response,
    sunset: str,         # ISO date: "2027-01-01"
    link: str | None = None,
) -> None:
    """
    Add Deprecation and Sunset headers per RFC 8594.

    Sunset:      the date after which the endpoint will no longer be available
    Deprecation: signals the endpoint is deprecated (set to 'true' or a date)
    Link:        points to the successor endpoint
    """
    response.headers["Deprecation"] = "true"
    response.headers["Sunset"]      = sunset
    if link:
        response.headers["Link"] = link

    logger.info(
        "Deprecated endpoint called. sunset=%s link=%s path=%s",
        sunset, link, response.headers.get("x-path", "unknown"),
    )
```

**What clients should do with these headers:**
```ts
// Client-side — check for deprecation headers and log a warning
async function apiFetch(url: string): Promise<Response> {
  const response = await fetch(url);

  if (response.headers.get('Deprecation')) {
    const sunset = response.headers.get('Sunset');
    const link   = response.headers.get('Link');
    console.warn(
      `[API] Deprecated endpoint called: ${url}. Sunset: ${sunset}. Successor: ${link}`
    );
  }

  return response;
}
```

---

### 5. Versioned schemas — keep them separate

Each version owns its request/response schemas. Never share mutable schemas between
versions — a change to a shared schema is a silent breaking change.

```
schemas/
  v1/
    user_schema.py     ← frozen after v1 ships
    order_schema.py
  v2/
    user_schema.py     ← current
    order_schema.py
```

```python
# schemas/v1/user_schema.py — FROZEN, never modify after v1 ships
from pydantic import BaseModel

class UserResponseV1(BaseModel):
    id:    int
    name:  str      # v1 field name
    email: str


# schemas/v2/user_schema.py
from pydantic import BaseModel
from datetime import datetime

class UserResponseV2(BaseModel):
    id:           int
    display_name: str        # renamed from 'name'
    email:        str
    created_at:   datetime   # new
    avatar_url:   str | None # new
```

---

### 6. Deprecation lifecycle

```
Phase 1 — Ship v2
  ├── v1 still fully supported
  ├── v2 available at new URL
  └── No Sunset header yet

Phase 2 — Announce deprecation (Sunset: T+6 months)
  ├── Add Deprecation + Sunset headers to all v1 responses
  ├── Email / changelog notice to API consumers
  └── Monitor v1 traffic — who is still calling it?

Phase 3 — Sunset date approaches
  ├── Reach out to consumers still on v1 (from traffic logs)
  ├── Consider extending Sunset if significant traffic remains
  └── Return 410 Gone for v1 (not 404 — 410 signals intentional removal)

Phase 4 — Retire v1
  ├── Remove v1 route handlers
  ├── Keep v1 schemas in git history (never delete)
  └── Return 410 with migration link for 90 days as a courtesy
```

```python
# Graceful 410 after sunset — do not just 404
@router.get("/v1/users/{user_id}")
async def get_user_v1_retired():
    raise HTTPException(
        status_code=410,
        detail={
            "error":   "gone",
            "message": "The v1 API was retired on 2027-01-01. Please migrate to /v2/users.",
            "docs":    "https://docs.example.com/migration/v1-to-v2",
        },
    )
```

---

### 7. Monitor version traffic before retiring

```sql
-- If you log requests to a table, check which clients still use v1
SELECT
    DATE_TRUNC('day', created_at) AS day,
    COUNT(*)                       AS requests,
    COUNT(DISTINCT user_agent)     AS unique_clients
FROM request_logs
WHERE path LIKE '/v1/%'
  AND created_at > now() - interval '30 days'
GROUP BY 1
ORDER BY 1 DESC;
```

Never remove a version while it still has meaningful traffic. The Sunset date is a
commitment — push it back rather than surprise clients.

### Rules

- Version only on breaking changes. Non-breaking changes go into the existing version.
- URL path versioning is the default. Use header versioning only when clean URLs are a
  hard requirement.
- Freeze v1 schemas the moment v2 ships. A change to a v1 schema is a silent breaking change.
- Add `Sunset` headers the day you decide to deprecate — not the day you plan to remove.
- Return `410 Gone`, not `404 Not Found`, for retired endpoints. 410 communicates intent.
- Never retire a version with non-trivial traffic. Check the logs; reach out to stragglers.
- Keep old schema files in the repo forever. They are the historical record of the contract.
