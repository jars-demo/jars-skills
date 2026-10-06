---
name: refactor
description: Refactor code safely with no behaviour changes. Use when the user asks to clean up, simplify, rename, extract, modularise, split a large file, add logging, improve comments, or reduce complexity. Verifies tests pass before and after every change, and never mixes refactoring with features or bug fixes.
---

# Refactor

Make code easier to read, maintain, and extend — without changing what it does. Every
refactor step is small, verifiable, and reversible. Tests pass before you start and after
every change. If they do not, stop.

## Ground rules

- **No behaviour changes.** Refactoring means the code does exactly the same thing, just
  more clearly. If you find a bug, note it and fix it in a separate commit.
- **Tests pass at every step.** Run the test suite before touching anything. If tests are
  already failing, fix them first or ask the user — do not refactor a broken codebase.
- **One concern per commit.** Do not mix a rename, a file split, and a logging addition
  into one commit. Small commits are easy to review and easy to revert.
- **The repository's conventions win.** Match the existing style, naming, logging library,
  and module structure. Introduce nothing new without a reason.
- **Never refactor and fix a bug in the same change.** If you find a bug while refactoring,
  stop, note it, and ask the user whether to fix it first.
- **Ask before splitting a public API.** Moving or renaming exported symbols is a breaking
  change. Confirm with the user before doing it.

---

## Step 0: Baseline

Before writing a single line, establish a clean baseline.

```bash
# Run the full test suite
pytest                  # Python
npm test -- --run       # JS/TS (single run, no watch)
cargo test              # Rust
go test ./...           # Go

# Check for lint errors
ruff check .            # Python
npx eslint src/         # JS/TS

# Note the current line counts of affected files
wc -l src/**/*.py
```

If tests fail or lint is red, do not proceed. Fix or agree on a plan with the user first.
Record the baseline result — you will compare against it after every step.

---

## File size limits

Large files are a signal, not just a style issue. A 2 000-line file usually means the
module is doing too many things, making it hard to test, review, and change safely.

Use these thresholds as guidelines — enforce them when the repository has no rule:

| File type | Soft limit | Hard limit |
| --- | --- | --- |
| Business logic, services, controllers | 300 lines | 500 lines |
| Utility / helper modules | 200 lines | 400 lines |
| Test files | 400 lines | 600 lines |
| Configuration files | 150 lines | 300 lines |
| Any single file | — | 1 200 lines |

When a file exceeds its hard limit, split it. When it approaches the soft limit, flag it.
A file over 1 200 lines must be split before new features are added to it.

**How to decide where to split**

Read the file and identify natural seams:
- Groups of functions that share a single concern ("all database queries", "all formatting
  helpers", "all auth checks")
- Classes that have grown beyond one responsibility
- Sections separated by large comment blocks — those blocks are a sign the file already
  has internal modules trying to get out

Name the new files after what they do, not after what they contain:
`user_queries.py` not `user_stuff2.py`, `formatters.ts` not `utils2.ts`.

---

## Modularisation

Break large or coupled modules into focused, single-responsibility units.

### Signs a module needs splitting

- It imports from more than five unrelated areas of the codebase
- Its public API has more than ten exports that are not closely related
- Reading a function requires understanding context from a completely different part of the
  file
- Tests for it require mocking more than two or three dependencies
- Two developers have edited it in the same sprint for unrelated reasons

### How to split a module

1. **Identify the seams** — group functions and classes by what they are responsible for.
2. **Create the new file** — name it clearly, move the group into it.
3. **Update imports** — fix every file that imported from the original.
4. **Re-export from the original if needed** — when the original is a public API, keep the
   old import path working by re-exporting: `from .queries import get_user` in the original.
5. **Run tests** — confirm nothing broke.
6. **Commit** — one commit per extracted module.

```
# Before
services/
  user.py   (850 lines: auth, queries, formatting, email)

# After
services/
  user/
    __init__.py       (re-exports the public API)
    auth.py           (login, logout, token refresh)
    queries.py        (all database reads and writes)
    formatters.py     (display names, avatar URLs)
    email.py          (verification, password reset)
```

---

## Logging

Good logging makes a system observable without a debugger. Add logs that tell the story of
what the code is doing, at the right volume.

### Log levels — use them correctly

| Level | When to use |
| --- | --- |
| `DEBUG` | Detailed internal state useful during development: loop iterations, parsed values, branch taken. Off in production. |
| `INFO` | Normal operational events: request received, job started, user logged in, file processed. |
| `WARNING` | Something unexpected but recoverable: a retry, a missing optional config, a slow response. |
| `ERROR` | A failure the system cannot recover from on its own: unhandled exception, DB connection lost, required config missing. |
| `CRITICAL` | The process must stop or data integrity is at risk. Use sparingly. |

### What to log

```python
# INFO — mark the start and end of meaningful operations
logger.info("Processing invoice", invoice_id=invoice.id, user_id=user.id)
# ... work ...
logger.info("Invoice processed", invoice_id=invoice.id, duration_ms=elapsed)

# WARNING — recoverable problems
logger.warning("Payment gateway timeout, retrying", attempt=attempt, invoice_id=invoice.id)

# ERROR — failures with context
logger.error("Invoice processing failed", invoice_id=invoice.id, exc_info=True)

# DEBUG — internal state (only when it helps diagnose a class of problems)
logger.debug("Discount applied", rule=rule.name, original=price, discounted=final)
```

### What not to log

- **Secrets**: passwords, tokens, API keys, PII (names, emails, card numbers)
- **Noise**: every iteration of a tight loop, values that never change
- **Redundant messages**: do not log and then immediately raise — the exception handler
  will log it
- **Raw request bodies** unless you have a compelling reason and have redacted sensitive fields

### Structured logging

Prefer key=value pairs or JSON fields over string interpolation. They are searchable:

```python
# Bad — hard to search and parse
logger.info(f"User {user_id} logged in from {ip}")

# Good — structured, filterable
logger.info("User logged in", user_id=user_id, ip=ip)
```

Use the logging library the project already uses (`structlog`, `winston`, `zap`, `slog`,
`logrus`, `pino`). Do not introduce a new one.

---

## Comments

Comments explain **why**, not **what**. The code already shows what it does — a comment
that restates it adds noise, not signal.

### Write a comment when

- The code does something non-obvious for a non-obvious reason
- A constraint comes from outside the code (a business rule, a legal requirement, a
  third-party limitation, a known bug in a dependency)
- You chose one approach and deliberately rejected another — say why
- A regex, a bit-mask, or a formula would be opaque without explanation

```python
# Good — explains why, not what
# Stripe requires idempotency keys to be unique per payment attempt.
# We combine invoice ID and attempt number so retries do not double-charge.
idempotency_key = f"{invoice.id}-{attempt}"

# Bad — restates the code
# Set idempotency key to invoice id and attempt number
idempotency_key = f"{invoice.id}-{attempt}"
```

### Public API documentation

Every exported function, class, and module needs a docstring or JSDoc comment that covers:

- What it does (one sentence)
- Parameters: name, type, what it means
- Return value
- Exceptions or errors it raises/rejects
- A short example when the usage is not obvious

```python
def calculate_discount(price: float, coupon: Coupon) -> float:
    """Apply a coupon to a price and return the discounted amount.

    Args:
        price: The original price in the account's currency, must be >= 0.
        coupon: A valid, unexpired Coupon object.

    Returns:
        The price after discount, always >= 0. Never negative even if the
        coupon value exceeds the price.

    Raises:
        ExpiredCouponError: If coupon.expires_at is in the past.
        ValueError: If price is negative.
    """
```

### Remove these on sight

- Commented-out code — delete it, git has the history
- `# TODO` items older than one sprint with no owner — delete or file a ticket
- Comments that just repeat the function name: `# get user`, `def get_user()`

---

## Common refactors

### Extract function

When a block of code does one thing and can be named, extract it:

```python
# Before — what does this block do?
users = db.query(User).all()
active = [u for u in users if u.last_login > thirty_days_ago and not u.is_banned]

# After — the name says it all
def get_active_users(db, since: datetime) -> list[User]:
    """Return users who have logged in since `since` and are not banned."""
    return [
        u for u in db.query(User).all()
        if u.last_login > since and not u.is_banned
    ]

active = get_active_users(db, since=thirty_days_ago)
```

### Rename for clarity

Names should say what a thing is, not how it is implemented:

| Before | After | Why |
| --- | --- | --- |
| `data` | `invoice_payload` | Says what the data represents |
| `flag` | `is_email_verified` | Boolean names start with `is_`, `has_`, `can_` |
| `process()` | `generate_invoice()` | Says what processing means here |
| `Manager` | `InvoiceRepository` | Says the role, not a generic suffix |
| `util.py` | `date_formatters.py` | Says what utilities are in here |

### Simplify conditionals

```python
# Before — nested, hard to follow
if user:
    if user.is_active:
        if user.has_permission("write"):
            do_thing()

# After — early returns flatten the nesting
if not user:
    raise NotFoundError("User not found")
if not user.is_active:
    raise ForbiddenError("Account is inactive")
if not user.has_permission("write"):
    raise ForbiddenError("Write permission required")

do_thing()
```

### Remove duplication

When the same logic appears in two places, extract it once. When it appears in three, it
is a module. Name it after what it does, not where it came from.

---

## Refactor checklist

Before calling a refactor done, verify:

- [ ] Tests pass (`pytest`, `npm test -- --run`, or equivalent)
- [ ] Lint is clean
- [ ] No file exceeds its hard line limit
- [ ] Every new or moved function has a docstring / JSDoc
- [ ] Logs use the correct level and contain structured fields, not string interpolation
- [ ] No secrets or PII in log statements
- [ ] Commented-out code removed
- [ ] Each commit touches one concern only (rename, extract, split, log — not all at once)
- [ ] Public API import paths still work (or breaking change was confirmed with user)

---

## Examples

| Shortcut | Correct approach |
| --- | --- |
| Rename everything in one commit | One rename per commit; run tests after each |
| Add logging everywhere at INFO | Use DEBUG for internal state, INFO for operations |
| `# TODO: clean this up` with no ticket | File a ticket or fix it now; remove the comment |
| Split a 1 500-line file into two 750-line files by cut-and-paste | Split by responsibility; update imports; verify tests |
| Write a comment explaining what the code does | Rename the function so it explains itself; save comments for why |
