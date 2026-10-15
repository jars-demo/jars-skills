---
name: code-structure
description: >
  Structuring, naming, and organising a codebase for long-term navigability: enforces a 696-line
  file ceiling, splits files by single responsibility, applies consistent snake_case / PascalCase
  / SCREAMING_SNAKE naming, wires structured logging with full error context at every boundary,
  adds file-level navigation comments, and scaffolds a clean folder hierarchy where every
  directory has exactly one job. Use when you want to "structure a project properly", "clean up
  a messy codebase", "split a large file", "add proper logging", "set up a folder structure",
  "enforce naming conventions", "make the code easier to navigate", "avoid a god file", or
  "set up a clean architecture".
---

## code-structure

Apply this skill whenever starting a new project, adding a major feature, or cleaning up
an existing codebase. Every rule here is a constraint, not a suggestion.

---

### 1. The 696-line ceiling

No file — including comments and blank lines — exceeds 696 lines.

- At ~500 lines, extract proactively. Do not wait until the ceiling forces a messy split.
- When a file needs "and" in its description (`user_auth_and_session.py`), split it now.
- Tests count separately. A 400-line module may have a 400-line test file. Both are fine.

**When to split and where to put the pieces:**

| File is getting large because of… | Extract into… |
|-----------------------------------|---------------|
| Multiple data models | `models/<entity>.py` per entity |
| Multiple service operations | `services/<domain>_service.py` per domain |
| Multiple route groups | `routes/<resource>.py` per resource |
| Utility functions | `lib/<concern>.py` (e.g. `lib/pagination.py`) |
| Config loading + validation | `config/settings.py` |
| DB query logic | `repositories/<entity>_repository.py` |

---

### 2. Folder scaffold — organise by responsibility, not file type

```
my_app/
├── main.py                  # entrypoint only — wires app together, no business logic
├── config/
│   └── settings.py          # loads and validates all env vars / config
├── models/
│   ├── user.py              # User dataclass / ORM model
│   └── order.py
├── schemas/
│   ├── user_schema.py       # request/response validation (Pydantic, Marshmallow)
│   └── order_schema.py
├── repositories/
│   ├── user_repository.py   # all DB queries for User — no business logic here
│   └── order_repository.py
├── services/
│   ├── user_service.py      # business logic for users — calls repository, never DB directly
│   └── order_service.py
├── routes/
│   ├── user_routes.py       # HTTP handlers for /users — calls service, never repository
│   └── order_routes.py
├── lib/
│   ├── logger.py            # shared logger setup
│   ├── exceptions.py        # custom exception hierarchy
│   └── pagination.py        # shared utilities
└── tests/
    ├── services/
    │   └── test_user_service.py
    └── repositories/
        └── test_user_repository.py
```

**What each layer is allowed to call:**

```
routes  →  services  →  repositories  →  database
                    →  lib/
                    →  models/
```

- Routes never import from `repositories` directly.
- Services never import from `routes`.
- Repositories never contain business logic.
- `main.py` wires everything together and nothing else. If `main.py` exceeds ~80 lines,
  move the wiring into an `app_factory.py`.

---

### 3. Naming conventions — every case has one job

| Thing | Convention | Example |
|-------|-----------|---------|
| Variables | `snake_case` | `user_id`, `order_total` |
| Functions | `snake_case` | `get_user_by_email`, `calculate_tax` |
| Classes | `PascalCase` | `UserService`, `OrderRepository` |
| Constants | `SCREAMING_SNAKE` | `MAX_RETRY_COUNT`, `DEFAULT_PAGE_SIZE` |
| Module files | `snake_case` | `user_service.py`, `order_repository.py` |
| Packages / dirs | `snake_case` | `services/`, `lib/` |
| Private helpers | `_leading_underscore` | `_parse_address`, `_build_query` |

**Bad → good naming:**

```python
# ❌ meaningless
data = get()
res = process(x, obj)
temp = db.query(q)

# ✅ describes what it is and what it does
user_record    = fetch_user_by_id(user_id)
invoice_total  = calculate_invoice_total(line_items)
active_orders  = query_orders_by_status(status="active")
```

**Function names must be verb phrases:**
```python
# ❌
def user(id): ...
def data(): ...

# ✅
def get_user_by_id(user_id: int): ...
def fetch_pending_orders(since: datetime): ...
```

**Boolean variables and functions use is_ / has_ / can_ / should_ prefixes:**
```python
is_admin        = user.role == "admin"
has_active_sub  = check_subscription_status(user_id)
can_retry       = attempt_count < MAX_RETRY_COUNT
```

---

### 4. File-level navigation header

Every file starts with a module docstring that answers three questions:
what it does, what it depends on, and who depends on it.

```python
"""
services/user_service.py
------------------------
Business logic for user management: registration, profile updates, and deactivation.

Depends on:
  - repositories/user_repository.py   (DB reads/writes)
  - lib/exceptions.py                  (UserNotFoundError, DuplicateEmailError)
  - models/user.py                     (User)
  - config/settings.py                 (EMAIL_VERIFICATION_REQUIRED)

Used by:
  - routes/user_routes.py
"""
```

Keep it to 10 lines max. It is a navigation aid, not documentation prose.

---

### 5. Structured logger — wired once, used everywhere

Set up the logger once in `lib/logger.py`. Import it everywhere. Never use `print`.

```python
# lib/logger.py
"""
lib/logger.py
-------------
Shared logger factory for the entire application.

Depends on: nothing (stdlib only)
Used by:    every module that logs
"""

import logging
import sys


def get_logger(name: str) -> logging.Logger:
    """Return a named logger with structured formatting."""
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger  # already configured — avoid duplicate handlers

    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    return logger
```

```python
# Usage in any module
from lib.logger import get_logger

logger = get_logger(__name__)   # __name__ = "services.user_service" — auto-namespaced
```

---

### 6. Logger levels — one rule per level

| Level | When to use |
|-------|-------------|
| `logger.debug` | Detailed internals — disabled in production; use for tracing data flow |
| `logger.info` | Normal milestones — request received, job started, record created |
| `logger.warning` | Unexpected but recoverable — retry triggered, deprecated path hit, config fallback used |
| `logger.error` | Operation failed, user impact possible — always include context and remediation hint |
| `logger.critical` | System cannot continue — database unreachable, config missing |

**Every `logger.error` and `logger.warning` must include:**
1. What operation failed
2. The inputs / identifiers involved
3. The exception message
4. What will happen next (retry, fallback, propagate)

```python
# ❌ useless
except Exception as e:
    logger.error("Something went wrong")
    raise

# ❌ too terse
except UserNotFoundError:
    logger.warning("User not found")

# ✅ full context — tells the on-call engineer exactly what happened
except UserNotFoundError as exc:
    logger.warning(
        "User lookup returned no record — returning 404 to caller. "
        "user_id=%s error=%s",
        user_id, exc,
    )
    raise

except EmailProviderError as exc:
    logger.error(
        "Failed to send verification email — user registration incomplete. "
        "user_id=%s email=%s provider=%s error=%s "
        "action=check EMAIL_PROVIDER_API_KEY and provider status page",
        user_id, email, settings.EMAIL_PROVIDER, exc,
    )
    raise RegistrationError("Email delivery failed") from exc
```

---

### 7. Custom exception hierarchy

Never raise bare `Exception`. Define a hierarchy in `lib/exceptions.py` so callers
can catch at the right granularity.

```python
# lib/exceptions.py
"""
lib/exceptions.py
-----------------
Application exception hierarchy. All custom exceptions inherit from AppError
so callers can catch broadly or narrowly as needed.

Depends on: nothing
Used by:    all services, repositories, routes
"""


class AppError(Exception):
    """Base for all application exceptions."""


class NotFoundError(AppError):
    """A requested resource does not exist."""


class UserNotFoundError(NotFoundError):
    """Specific to user lookups."""


class ConflictError(AppError):
    """An operation conflicts with existing state."""


class DuplicateEmailError(ConflictError):
    """Email address already registered."""


class ExternalServiceError(AppError):
    """A third-party service call failed."""


class EmailProviderError(ExternalServiceError):
    """Email delivery provider returned an error."""
```

---

### 8. Apply the rules to a real service file

```python
# services/user_service.py
"""
services/user_service.py
------------------------
Business logic for user management: registration and profile retrieval.

Depends on:
  - repositories/user_repository.py   (fetch_user_by_id, create_user)
  - lib/exceptions.py                  (UserNotFoundError, DuplicateEmailError)
  - lib/logger.py                      (get_logger)
  - models/user.py                     (User)

Used by:
  - routes/user_routes.py
"""

from models.user import User
from repositories.user_repository import UserRepository
from lib.exceptions import DuplicateEmailError, UserNotFoundError
from lib.logger import get_logger

logger = get_logger(__name__)

# Injected at construction — makes the service testable without a real DB.
class UserService:
    def __init__(self, user_repo: UserRepository) -> None:
        self._user_repo = user_repo

    def get_user(self, user_id: int) -> User:
        """Fetch a user by ID. Raises UserNotFoundError if not found."""
        logger.info("Fetching user. user_id=%s", user_id)

        user = self._user_repo.find_by_id(user_id)
        if user is None:
            logger.warning(
                "User not found. user_id=%s action=returning UserNotFoundError", user_id
            )
            raise UserNotFoundError(f"No user with id={user_id}")

        logger.info("User fetched successfully. user_id=%s", user_id)
        return user

    def register_user(self, email: str, display_name: str) -> User:
        """Create a new user. Raises DuplicateEmailError if email is taken."""
        logger.info("Registering new user. email=%s", email)

        existing = self._user_repo.find_by_email(email)
        if existing is not None:
            logger.warning(
                "Registration rejected — email already in use. "
                "email=%s existing_user_id=%s",
                email, existing.id,
            )
            raise DuplicateEmailError(f"Email already registered: {email}")

        new_user = self._user_repo.create(email=email, display_name=display_name)
        logger.info(
            "User registered successfully. user_id=%s email=%s",
            new_user.id, email,
        )
        return new_user
```

---

### 9. Checklist before committing any file

Run through this before every commit:

- [ ] File is under 696 lines (count with `wc -l <file>` or editor line count)
- [ ] Module docstring present: what it does, depends on, used by
- [ ] All variables and functions use `snake_case`
- [ ] All class names use `PascalCase`
- [ ] No variable named `data`, `result`, `temp`, `obj`, `res`, `x`, or `val` without a qualifier
- [ ] Every function name is a verb phrase
- [ ] No `print()` — only `logger.*`
- [ ] Every `logger.error` / `logger.warning` includes: operation, identifiers, error, next action
- [ ] No bare `except Exception: pass` or `catch(e) {}`
- [ ] Custom exceptions raised, not bare `Exception` or `Error`
- [ ] File only imports from layers it is allowed to call (routes→services→repos→db)

### Rules

- The 696-line limit is a hard ceiling, not a target. Aim for 300–400 lines per file.
- A file that needs a long name is already doing too much. Split it.
- Logger context is for engineers on call at 3 am. Write it like you will be that engineer.
- Folder structure is an API. Once established, moving files breaks imports across the team —
  establish it before writing business logic, not after.
- Apply these rules to new code first. Refactor existing code incrementally — one file per
  PR, tests passing at every step.
