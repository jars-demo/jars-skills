---
name: event-driven-architecture
description: Designing and implementing event-driven systems: defines versioned event schemas with a registry, separates domain events from integration events, implements the transactional outbox pattern to guarantee event publication, designs idempotent consumers, handles event ordering and out-of-order delivery, and avoids the coupling and observability traps that make event-driven systems hard to debug. Use when you want to design an event-driven system, publish domain events, implement the outbox pattern, decouple services with events, version an event schema, design a consumer, handle event ordering, or use Kafka or a message broker correctly.
---

## event-driven-architecture

Design the event contract first. Everything else — producers, consumers, brokers — is plumbing.

### 1. Two kinds of events — keep them separate

| Kind | What it is | Who owns it | Example |
|------|-----------|-------------|---------|
| **Domain event** | Something that happened inside a bounded context | The service that owns the domain | `OrderPlaced`, `PaymentFailed` |
| **Integration event** | A domain event published across service boundaries | The publishing service | `order.placed.v1`, `payment.failed.v1` |

Domain events live inside a service. Integration events cross the wire and are part of a
public contract. **Version integration events from day one** — once a consumer depends on
the schema, changing it without versioning is a breaking change.

---

### 2. Event schema — define it before writing a producer or consumer

Every integration event has:
- A stable **type** string (e.g. `order.placed.v1`)
- A **version** embedded in the type or as a field
- An **event_id** for deduplication
- A **occurred_at** timestamp (ISO 8601)
- A **payload** with the relevant domain data

```python
# lib/events.py
"""
lib/events.py
-------------
Base event schema and registry for all integration events.
Producers and consumers import event classes from here — never define schemas inline.

Depends on: pydantic
Used by:    services/*, workers/*
"""

from datetime import datetime, timezone
from uuid import uuid4
from pydantic import BaseModel, Field


class IntegrationEvent(BaseModel):
    event_id:    str      = Field(default_factory=lambda: str(uuid4()))
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    event_type:  str      # set by subclass

    model_config = {"frozen": True}   # events are immutable


class OrderPlacedV1(IntegrationEvent):
    event_type: str = "order.placed.v1"
    order_id:   int
    tenant_id:  str
    user_id:    int
    total_cents: int
    currency:   str


class PaymentFailedV1(IntegrationEvent):
    event_type:   str = "payment.failed.v1"
    order_id:     int
    tenant_id:    str
    failure_code: str
    failure_message: str
```

```ts
// lib/events.ts
/**
 * lib/events.ts
 * -------------
 * Integration event base type and registry.
 * Import event types from here — never define inline in a service file.
 *
 * Depends on: zod
 * Used by:    services/*, workers/*
 */

import { z } from 'zod';
import { randomUUID } from 'crypto';

const baseEventSchema = z.object({
  event_id:    z.string().default(() => randomUUID()),
  occurred_at: z.string().datetime().default(() => new Date().toISOString()),
  event_type:  z.string(),
});

export const orderPlacedV1Schema = baseEventSchema.extend({
  event_type:  z.literal('order.placed.v1'),
  order_id:    z.number().int().positive(),
  tenant_id:   z.string(),
  user_id:     z.number().int().positive(),
  total_cents: z.number().int().positive(),
  currency:    z.string().length(3),
});

export type OrderPlacedV1 = z.infer<typeof orderPlacedV1Schema>;
```

---

### 3. The transactional outbox — never lose an event

The most common event-driven bug: publishing an event after a database commit but before
the broker acknowledges. If the process crashes in between, the event is lost.

**The outbox pattern fixes this atomically:**

```
1. Write the domain state change AND the event to the DB in one transaction
2. A separate outbox worker reads unpublished events and publishes them
3. Mark events as published only after the broker confirms delivery
```

```sql
-- migration: create the outbox table
CREATE TABLE outbox_events (
    id          BIGSERIAL PRIMARY KEY,
    event_id    TEXT        NOT NULL UNIQUE,
    event_type  TEXT        NOT NULL,
    payload     JSONB       NOT NULL,
    tenant_id   TEXT,
    published   BOOLEAN     NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    published_at TIMESTAMPTZ
);

CREATE INDEX idx_outbox_unpublished ON outbox_events (published, created_at)
  WHERE published = FALSE;
```

```python
# services/order_service.py — write state + event in one transaction
async def place_order(user_id: int, items: list) -> Order:
    async with db.transaction():
        # 1. Write domain state
        order = await order_repo.create(user_id=user_id, items=items)

        # 2. Write event to outbox in the same transaction
        event = OrderPlacedV1(
            order_id=order.id,
            tenant_id=get_tenant(),
            user_id=user_id,
            total_cents=order.total_cents,
            currency="USD",
        )
        await db.execute(
            """
            INSERT INTO outbox_events (event_id, event_type, payload, tenant_id)
            VALUES (:event_id, :event_type, :payload, :tenant_id)
            """,
            {
                "event_id":   event.event_id,
                "event_type": event.event_type,
                "payload":    event.model_dump_json(),
                "tenant_id":  event.tenant_id,
            },
        )
        logger.info("Order placed and event written to outbox. order_id=%s", order.id)
        return order
```

```python
# workers/outbox_worker.py
"""
workers/outbox_worker.py
-------------------------
Polls the outbox table and publishes unpublished events to the broker.
Runs as a separate process or background task.

Depends on: lib/broker.py, lib/logger.py
Used by:    background worker fleet
"""

import asyncio
from lib.broker import publish
from lib.logger import get_logger

logger = get_logger(__name__)
BATCH_SIZE = 100
POLL_INTERVAL_S = 1.0


async def run_outbox_worker() -> None:
    logger.info("Outbox worker started.")
    while True:
        await _process_batch()
        await asyncio.sleep(POLL_INTERVAL_S)


async def _process_batch() -> None:
    rows = await db.fetch_all(
        """
        SELECT id, event_id, event_type, payload, tenant_id
        FROM outbox_events
        WHERE published = FALSE
        ORDER BY created_at ASC
        LIMIT :limit
        FOR UPDATE SKIP LOCKED
        """,
        {"limit": BATCH_SIZE},
    )
    if not rows:
        return

    for row in rows:
        try:
            await publish(
                topic=row["event_type"],
                key=row["tenant_id"],
                value=row["payload"],
            )
            await db.execute(
                "UPDATE outbox_events SET published = TRUE, published_at = now() WHERE id = :id",
                {"id": row["id"]},
            )
            logger.info("Outbox event published. event_id=%s type=%s", row["event_id"], row["event_type"])
        except Exception as exc:
            logger.error(
                "Failed to publish outbox event. event_id=%s type=%s error=%s "
                "action=will_retry_on_next_poll",
                row["event_id"], row["event_type"], exc,
            )
```

---

### 4. Idempotent consumers

Consumers must handle duplicate delivery. Use the `event_id` to deduplicate.

```python
# workers/order_consumer.py
async def handle_event(raw_payload: str) -> None:
    import json
    data = json.loads(raw_payload)
    event_id   = data["event_id"]
    event_type = data["event_type"]

    # Deduplication — already processed?
    already = await db.fetch_val(
        "SELECT 1 FROM processed_events WHERE event_id = :id", {"id": event_id}
    )
    if already:
        logger.info("Duplicate event skipped. event_id=%s", event_id)
        return

    # Route to handler
    handlers = {
        "order.placed.v1":   _handle_order_placed,
        "payment.failed.v1": _handle_payment_failed,
    }
    handler = handlers.get(event_type)
    if not handler:
        logger.warning("Unknown event type, ignoring. event_type=%s", event_type)
        return

    await handler(data)

    # Mark processed atomically
    await db.execute(
        "INSERT INTO processed_events (event_id, event_type, processed_at) VALUES (:id, :type, now())",
        {"id": event_id, "type": event_type},
    )
```

---

### 5. Event versioning — backward-compatible changes only

Once an event schema is in production, consumers depend on it.

| Change | Safe? | How |
|--------|-------|-----|
| Add optional field | ✅ | Add with default; old consumers ignore it |
| Remove field | ❌ | Bump version: `order.placed.v2`; run both in parallel |
| Rename field | ❌ | Bump version |
| Change field type | ❌ | Bump version |
| Add required field | ❌ | Bump version |

**Running two versions in parallel:**
```python
# Producer publishes both during migration window
await publish_event(OrderPlacedV1(...))   # old consumers
await publish_event(OrderPlacedV2(...))   # new consumers

# Once all consumers migrate to v2, stop publishing v1
```

---

### 6. Ordering and out-of-order delivery

Most brokers guarantee ordering within a partition/key — not globally.

```python
# Use a stable partition key so related events are ordered
await publish(
    topic="order.placed.v1",
    key=str(order.id),      # all events for the same order go to the same partition
    value=event.model_dump_json(),
)
```

**Design consumers to handle out-of-order delivery:**
```python
async def _handle_order_placed(data: dict) -> None:
    order_id = data["order_id"]

    # Idempotent check — if order already exists and is further along, skip
    existing = await order_repo.find_by_id(order_id)
    if existing and existing["status"] != "pending":
        logger.info(
            "Order already past 'placed' state, skipping event. "
            "order_id=%s current_status=%s",
            order_id, existing["status"],
        )
        return
    # ... process
```

### Rules

- Define the event schema before writing the producer or consumer. The schema is the contract.
- Use the transactional outbox — never publish after a DB commit without it. Dual writes lose events.
- Version event types in the type string (`order.placed.v1`). Never mutate a published schema.
- Every consumer must deduplicate on `event_id`. At-least-once delivery is the default for every broker.
- Partition on a stable business key (order ID, user ID) to preserve ordering for related events.
- Log `event_id` and `event_type` on every log line in a consumer. They are the only way to correlate with the producer.
- Consume unknown event types silently (log + skip) — never crash. New event types will appear as producers evolve.
