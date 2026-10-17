---
name: code-comments
description: Reading an unfamiliar codebase and adding comments that help the next engineer: explains why decisions were made, documents non-obvious behaviour, adds contract comments on public functions, writes file-level navigation headers, and removes or replaces misleading and stale comments — without documenting the obvious. Use when you want to add comments to code, document a codebase, explain why this code works this way, add docstrings, understand and annotate unfamiliar code, improve code readability, or leave notes for the next engineer.
---

## code-comments

Read the code first. Understand it fully. Then comment only what the code cannot say for itself.

### 1. The one rule everything else follows

A comment that describes **what** the code does is almost always useless — the code already
says what it does. A comment that describes **why** is almost always valuable.

```python
# ❌ Describes what — the code already says this
i += 1  # increment i

# ❌ Still describes what — restates the function name
def get_user_by_id(user_id: int):
    # gets a user by their ID
    ...

# ✅ Explains why — the code cannot say this
# Retry up to 3 times: the payment provider returns 503 spuriously
# on the first attempt roughly 15 % of the time (confirmed with vendor).
for attempt in range(3):
    result = payment_provider.charge(amount)
    if result.success:
        break

# ✅ Explains a non-obvious constraint
# user_id must be checked before order_id — the DB schema allows orders
# with no user (guest checkout), but the audit log requires one.
if not user_id:
    raise ValueError("user_id required for audit log")
```

---

### 2. Read before you comment

Before adding a single comment, read the file end-to-end. Then:

1. Identify every section where you had to stop and re-read to understand.
2. Identify every decision that looks arbitrary but probably has a reason.
3. Identify every function with a non-obvious contract (preconditions, side effects, what it raises).
4. Identify stale or wrong comments that contradict the current code.

Those four categories are the only places comments are needed.

---

### 3. File-level header

Every non-trivial file gets a header answering three questions: what it does, what it depends on, and who uses it. Keep it under 10 lines.

```python
"""
services/payment_service.py
---------------------------
Handles charge initiation and refund logic for orders.
Communicates with the Stripe API only — no direct DB writes.

Depends on: lib/stripe_client.py, lib/exceptions.py, models/order.py
Used by:    routes/checkout_routes.py, workers/refund_worker.py
"""
```

```ts
/**
 * lib/queue.ts
 * ------------
 * Thin wrapper around BullMQ. Exposes typed enqueue helpers and
 * a single worker factory so queue names never drift between producer and consumer.
 *
 * Depends on: lib/redis.ts, lib/logger.ts
 * Used by:    services/*, workers/*
 */
```

---

### 4. Function / method contract comments

Comment public and exported functions. Comment private functions only when the contract
is non-obvious. A contract comment answers:

- What does this function expect? (preconditions, valid input ranges)
- What does it return?
- What does it raise / throw, and when?
- Any side effects the caller needs to know about?

```python
def charge_order(order_id: int, idempotency_key: str) -> ChargeResult:
    """
    Initiate a charge for a completed order.

    Args:
        order_id:        ID of an order in status='confirmed'. Raises OrderNotFoundError
                         if missing, InvalidStateError if already charged or cancelled.
        idempotency_key: Caller-provided key forwarded to Stripe. Must be unique per
                         charge attempt; reusing a key for a different amount raises
                         IdempotencyConflictError.

    Returns:
        ChargeResult with .charge_id and .status ('succeeded' or 'requires_action').

    Raises:
        OrderNotFoundError:      order_id does not exist.
        InvalidStateError:       order is not in 'confirmed' status.
        PaymentDeclinedError:    Stripe declined the card.
        ExternalServiceError:    Stripe returned a 5xx or network error.

    Side effects:
        Updates order.status to 'charged' on success.
        Writes a charge record to the audit_log table.
    """
```

```ts
/**
 * Resolves a paginated list of active users sorted by last-seen date.
 *
 * @param cursor - Opaque pagination cursor from a previous response.
 *                 Pass undefined for the first page.
 * @param limit  - Page size, 1–100. Values outside this range are clamped.
 * @returns      Page of users plus a `nextCursor` (null when no more pages).
 * @throws       DatabaseError if the query fails after 3 retries.
 */
async function listActiveUsers(cursor?: string, limit = 20): Promise<UserPage>
```

---

### 5. Inline why-comments — when and how

Add an inline comment when:

- The code uses a non-obvious algorithm or data structure choice.
- There is a bug that was fixed and the fix looks wrong without context.
- A seemingly cleaner alternative was deliberately rejected.
- An external constraint (API quirk, library bug, legal requirement) drives the logic.
- Magic numbers or thresholds need justification.

```python
# ✅ Non-obvious algorithm choice
# Using a min-heap instead of sorting the full list — we only need
# the top 10 results and the input can be millions of records.
heap = []
for record in records:
    heapq.heappushpop(heap, (record.score, record))

# ✅ Bug fix context
# Stripe returns amount in cents but their webhook payload uses
# dollars for legacy reasons on this specific event type. Confirmed
# in Stripe docs: https://stripe.com/docs/api/events/types#event_types-charge.updated
amount_cents = int(event["data"]["amount"] * 100)

# ✅ Deliberate rejection of the obvious approach
# Cannot use ORDER BY created_at DESC here — the column has no index
# and the table has 50M rows. Using the covering index on (status, id)
# instead and sorting in application code for the small result set.
rows = db.query("SELECT id FROM orders WHERE status = $1", status)
rows.sort(key=lambda r: r.id, reverse=True)

# ✅ Magic number justified
# 696: maximum lines per file enforced by our code-structure convention.
MAX_FILE_LINES = 696
```

---

### 6. Section dividers for long functions

When a function is long (approaching the 696-line file limit, or just complex), group
related steps with section dividers. Keep them short and verb-led.

```python
def process_checkout(cart_id: int, payment_method: str) -> OrderResult:
    # ── Validate ──────────────────────────────────────────────────────────
    cart = fetch_cart(cart_id)
    validate_cart_items(cart)
    validate_payment_method(payment_method)

    # ── Reserve inventory ─────────────────────────────────────────────────
    for item in cart.items:
        reserve_stock(item.product_id, item.quantity)

    # ── Charge ────────────────────────────────────────────────────────────
    charge = charge_payment(payment_method, cart.total)

    # ── Persist ───────────────────────────────────────────────────────────
    order = create_order(cart, charge)
    clear_cart(cart_id)

    return OrderResult(order_id=order.id, charge_id=charge.id)
```

---

### 7. Architecture-level comments — for non-obvious design decisions

When a module uses a pattern that will surprise the next engineer, explain it at the top.

```python
# ARCHITECTURE NOTE
# -----------------
# This service deliberately does NOT use the shared DB session from the
# request context. Refund processing runs as a background job after the
# HTTP response is sent, so the request-scoped session is already closed.
# A dedicated session is created and committed per refund operation.
# See: docs/adr/0012-refund-background-session.md
```

```ts
// ARCHITECTURE NOTE
// -----------------
// UserCache uses copy-on-write via atomic pointer swap rather than
// an RWMutex. Under our read-heavy workload (1000:1 read/write ratio)
// mutex contention was measurable. The atomic swap means readers
// never block — they always see either the old or new snapshot, never partial.
```

---

### 8. What NOT to comment

Remove or rewrite any comment that:

| Anti-pattern | Why it hurts | Fix |
|-------------|-------------|-----|
| Restates the code | Adds noise, drifts from code over time | Delete it |
| States the obvious | Insults the reader | Delete it |
| Is a lie (out of date) | Actively misleads | Update or delete |
| Commented-out code | Clutters the file, version control has history | Delete it |
| TODO without an owner or ticket | Never gets done | Add ticket number or delete |
| Sarcastic / venting | Unprofessional, confuses future engineers | Rewrite neutrally |

```python
# ❌ Every one of these should be deleted or rewritten

x = x + 1  # add 1 to x

# TODO: fix this later

# I have no idea why this works but don't touch it

# def old_function():  ← entire commented-out function block

if user.is_admin:  # check if user is admin
```

```python
# ✅ The TODO rewritten with an owner and a ticket
# TODO(jars): replace with streaming parser when input > 10 MB — GH-4821

# ✅ The "don't touch it" rewritten with the actual reason
# The order of these two calls matters: session.flush() must happen before
# audit_log.write() so the FK constraint on audit_log.order_id resolves.
# Moving audit_log.write() first causes an IntegrityError on Postgres 14+.
session.flush()
audit_log.write(order)
```

---

### 9. Commenting workflow for an unfamiliar file

When asked to understand and comment an existing file:

1. **Read the whole file** without editing anything.
2. **Note every moment of confusion** — those are the comment locations.
3. **Trace the data flow** — follow inputs from the top to where they change or leave.
4. **Check git blame / log** for context on surprising lines (`git log -p --follow <file>`).
5. **Add comments in one pass** — file header first, then function contracts, then inline whys.
6. **Re-read with comments in place** — does it now read clearly to someone unfamiliar?
7. **Delete any comment that describes what the code already says clearly**.

### Rules

- Comment the why, never the what.
- A comment that can go stale is worse than no comment — keep them close to the code they explain.
- Every public function gets a contract comment. Every private function gets one only if the contract is non-obvious.
- Stale and wrong comments are bugs. Fix them the moment you notice them.
- Commented-out code is dead weight — delete it; git history is the backup.
- A TODO without a ticket number is a wishlist item, not a task. Add the ticket or delete the TODO.
