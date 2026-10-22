---
name: database-transactions
description: Writing correct database transactions: applies ACID properties deliberately, chooses the right isolation level for the operation, keeps transactions short, avoids long-running transaction anti-patterns, uses SELECT FOR UPDATE and optimistic locking correctly, handles deadlocks with retry logic, and uses savepoints for nested rollback. Use when you want to write a database transaction, choose an isolation level, fix a lost update, use SELECT FOR UPDATE, implement optimistic locking, handle a deadlock, use savepoints, avoid long-running transactions, or ensure atomicity across multiple tables.
---

## database-transactions

Write transactions deliberately. Every transaction is a promise about what the database
will look like when it commits — know exactly what you are promising.

### 1. ACID in practice — what each property actually means for your code

| Property | What it means | How it fails in practice |
|----------|--------------|--------------------------|
| **Atomic** | All operations commit or none do | Partial update when code raises between two writes |
| **Consistent** | Constraints hold before and after | FK violation, NOT NULL breach committed mid-transaction |
| **Isolated** | Concurrent transactions don't interfere | Lost update, dirty read, phantom row |
| **Durable** | Committed data survives crashes | Misconfigured fsync, in-memory DB in production |

---

### 2. Keep transactions short — the most important rule

A transaction holds locks. Long transactions block other writers and readers (depending on
isolation level), fill the WAL/undo log, and cause replication lag.

```python
# ❌ Long transaction — holds locks while sending an email
async with db.transaction():
    order = await order_repo.create(user_id, items)
    await email_service.send_confirmation(order)   # network call inside transaction!
    await inventory_repo.reserve(items)

# ✅ Short transaction — only DB work inside; side effects after commit
async with db.transaction():
    order = await order_repo.create(user_id, items)
    await inventory_repo.reserve(items)

# Side effect outside the transaction — if this fails, the order still exists
# (handle with the outbox pattern — see event-driven-architecture skill)
await email_service.send_confirmation(order)
```

**Never do inside a transaction:**
- HTTP calls to external services
- File I/O
- Sending emails or notifications
- Long computations
- Sleeping or waiting

---

### 3. Isolation levels — choose deliberately

```sql
-- PostgreSQL default is READ COMMITTED
-- Set per transaction, not globally

BEGIN ISOLATION LEVEL REPEATABLE READ;
-- or
BEGIN ISOLATION LEVEL SERIALIZABLE;
```

```python
# SQLAlchemy — per-transaction isolation
async with engine.connect() as conn:
    await conn.execution_options(isolation_level="REPEATABLE READ")
    async with conn.begin():
        ...
```

**When to go beyond READ COMMITTED:**

```python
# REPEATABLE READ — prevents non-repeatable reads
# Use when: you read the same row twice and need consistent results
# Example: calculate a subtotal, then verify the total

async def calculate_order_total(order_id: int) -> int:
    # Without REPEATABLE READ, another transaction could update prices
    # between the two reads — subtotal and total would be inconsistent
    async with db.transaction(isolation="repeatable_read"):
        items    = await db.fetch_all("SELECT price, qty FROM order_items WHERE order_id=$1", order_id)
        subtotal = sum(i["price"] * i["qty"] for i in items)

        # Re-read to verify — guaranteed same rows under REPEATABLE READ
        total = await db.fetch_val("SELECT SUM(price*qty) FROM order_items WHERE order_id=$1", order_id)
        assert subtotal == total
        return total


# SERIALIZABLE — prevents phantom reads and write skew
# Use when: the correctness of a write depends on a read in the same transaction
# Example: two users each check "is there a slot available?" and both book it

async def book_slot(slot_id: int, user_id: int) -> bool:
    async with db.transaction(isolation="serializable"):
        count = await db.fetch_val(
            "SELECT COUNT(*) FROM bookings WHERE slot_id=$1", slot_id
        )
        if count >= 1:
            return False   # slot taken
        await db.execute(
            "INSERT INTO bookings (slot_id, user_id) VALUES ($1, $2)",
            slot_id, user_id,
        )
        return True
    # Under SERIALIZABLE: if two concurrent transactions both read count=0
    # and try to insert, one will fail with serialization error — retry it
```

---

### 4. Locking — pessimistic vs optimistic

**Pessimistic locking — `SELECT FOR UPDATE`:**
```sql
-- Locks the row immediately; other transactions block until this one commits
BEGIN;
SELECT balance FROM accounts WHERE id = $1 FOR UPDATE;
UPDATE accounts SET balance = balance - $2 WHERE id = $1;
COMMIT;
```

```python
# SQLAlchemy — SELECT FOR UPDATE
async with db.transaction():
    row = await db.fetch_one(
        "SELECT balance FROM accounts WHERE id = :id FOR UPDATE",
        {"id": account_id},
    )
    if row["balance"] < amount:
        raise InsufficientFundsError()
    await db.execute(
        "UPDATE accounts SET balance = balance - :amount WHERE id = :id",
        {"amount": amount, "id": account_id},
    )
```

**`FOR UPDATE SKIP LOCKED` — non-blocking queue processing:**
```sql
-- Used for job queues and outbox workers — skip rows locked by other workers
SELECT id, payload FROM jobs
WHERE status = 'pending'
ORDER BY created_at
LIMIT 10
FOR UPDATE SKIP LOCKED;
```

**Optimistic locking — version column:**
```python
# Read current version; update only if version unchanged; retry if not
async def deduct_balance(account_id: int, amount: int, max_retries: int = 3) -> None:
    for attempt in range(max_retries):
        row = await db.fetch_one(
            "SELECT balance, version FROM accounts WHERE id = :id",
            {"id": account_id},
        )
        if row["balance"] < amount:
            raise InsufficientFundsError()

        updated = await db.execute(
            """
            UPDATE accounts
            SET balance = balance - :amount, version = version + 1
            WHERE id = :id AND version = :version
            """,
            {"amount": amount, "id": account_id, "version": row["version"]},
        )

        if updated.rowcount == 1:
            return   # ✅ won the race

        logger.warning(
            "Optimistic lock conflict on account update. "
            "account_id=%s attempt=%d", account_id, attempt + 1
        )
        await asyncio.sleep(0.05 * (attempt + 1))   # back off before retry

    raise ConcurrencyError(f"Could not update account {account_id} after {max_retries} retries")
```

**When to use which:**
| Use pessimistic (`FOR UPDATE`) | Use optimistic (version column) |
|-------------------------------|--------------------------------|
| High contention (same rows written frequently) | Low contention (conflicts are rare) |
| Short critical section | Longer read-compute-write cycle |
| Cannot afford retries | Retry overhead is acceptable |

---

### 5. Deadlock detection and retry

PostgreSQL detects deadlocks and raises `deadlock_detected` (error code 40P01).
Always retry on deadlock — it is not a bug, it is a normal concurrent event.

```python
import asyncpg

DEADLOCK_ERROR_CODE = "40P01"
SERIALIZATION_ERROR_CODE = "40001"
RETRYABLE_CODES = {DEADLOCK_ERROR_CODE, SERIALIZATION_ERROR_CODE}

async def with_retry(fn, max_retries: int = 3):
    """Run fn() in a transaction; retry on deadlock or serialization failure."""
    for attempt in range(max_retries):
        try:
            return await fn()
        except asyncpg.exceptions.PostgresError as exc:
            if exc.sqlstate in RETRYABLE_CODES and attempt < max_retries - 1:
                delay = 0.05 * (2 ** attempt)   # exponential back-off
                logger.warning(
                    "Retryable transaction error. code=%s attempt=%d delay_s=%.2f",
                    exc.sqlstate, attempt + 1, delay,
                )
                await asyncio.sleep(delay)
                continue
            raise
    raise ConcurrencyError("Transaction failed after max retries")


# Usage
await with_retry(lambda: transfer_funds(from_id, to_id, amount))
```

**Prevent deadlocks with consistent lock ordering** (same as the concurrency-and-locking skill):
```python
# Always lock accounts in ID order — prevents A→B / B→A deadlock cycle
async def transfer_funds(from_id: int, to_id: int, amount: int) -> None:
    first_id, second_id = sorted([from_id, to_id])
    async with db.transaction():
        await db.execute("SELECT 1 FROM accounts WHERE id = :id FOR UPDATE", {"id": first_id})
        await db.execute("SELECT 1 FROM accounts WHERE id = :id FOR UPDATE", {"id": second_id})
        await db.execute("UPDATE accounts SET balance = balance - :a WHERE id = :id", {"a": amount, "id": from_id})
        await db.execute("UPDATE accounts SET balance = balance + :a WHERE id = :id", {"a": amount, "id": to_id})
```

---

### 6. Savepoints — partial rollback inside a transaction

Savepoints let you roll back part of a transaction without aborting the whole thing.
Useful when one operation in a batch is allowed to fail while the rest succeed.

```python
# Process a batch — roll back individual failures, commit the rest
async with db.transaction():
    for item in batch:
        try:
            await db.execute("SAVEPOINT item_save")
            await process_item(item)
            await db.execute("RELEASE SAVEPOINT item_save")
            logger.info("Item processed. item_id=%s", item["id"])
        except Exception as exc:
            await db.execute("ROLLBACK TO SAVEPOINT item_save")
            logger.error(
                "Item processing failed, rolled back to savepoint. "
                "item_id=%s error=%s action=continuing_batch",
                item["id"], exc,
            )
```

---

### 7. Long transaction anti-patterns — find and fix them

```bash
# Find transactions open longer than 30 seconds (PostgreSQL)
SELECT pid, usename, state, query_start,
       EXTRACT(EPOCH FROM (now() - query_start))::int AS age_s,
       left(query, 80) AS query_snippet
FROM pg_stat_activity
WHERE state != 'idle'
  AND query_start < now() - interval '30 seconds'
ORDER BY age_s DESC;
```

| Anti-pattern | Why it hurts | Fix |
|-------------|-------------|-----|
| HTTP call inside transaction | Holds locks for network round-trip duration | Move side effects outside transaction |
| Transaction per HTTP request spanning multiple user interactions | Open for seconds | Use optimistic locking; commit after each step |
| `BEGIN` without `COMMIT` in a script | Locks rows forever | Always use context managers / `with transaction()` |
| Large batch in one transaction | Holds all locks until batch done | Process in smaller chunks with savepoints |
| `SELECT COUNT(*)` in a long transaction | Holds snapshot; blocks VACUUM | Run counts outside transactions or use approximate counts |

### Rules

- Never do I/O (HTTP, email, file) inside a transaction. Commit first, then do the side effect.
- Choose the isolation level deliberately for each transaction — never rely on the default blindly.
- Retry on `40P01` (deadlock) and `40001` (serialization failure) — they are expected, not bugs.
- Lock rows in a consistent global order to prevent deadlock cycles.
- Use `FOR UPDATE SKIP LOCKED` for queue-style processing — never plain `FOR UPDATE` on a queue table.
- Prefer short transactions and optimistic locking over long transactions and pessimistic locking.
- Monitor `pg_stat_activity` for long-running transactions in production — they block VACUUM and replication.
