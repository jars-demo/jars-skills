# idempotency — references

Key reading for the concepts and patterns in this skill.

## Idempotency keys

- [Stripe idempotency keys](https://stripe.com/docs/api/idempotent_requests) — the canonical
  real-world implementation. Stripe's approach (key in header, result cached server-side,
  key expires after 24 h) is the model this skill follows.

## Delivery semantics

- [Kafka exactly-once semantics](https://kafka.apache.org/documentation/#semantics) — the
  official explanation of at-most-once, at-least-once, and exactly-once in Kafka.
- [AWS SQS message deduplication](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/FIFO-queues-exactly-once-processing.html) — FIFO queue deduplication IDs.

## Database upserts

- [PostgreSQL INSERT ON CONFLICT](https://www.postgresql.org/docs/current/sql-insert.html#SQL-ON-CONFLICT) — full syntax reference for `ON CONFLICT DO NOTHING` and `ON CONFLICT DO UPDATE`.

## Distributed systems context

- [Designing Data-Intensive Applications, Ch. 11](https://dataintensive.net) — Martin Kleppmann's
  treatment of exactly-once semantics, idempotent consumers, and the challenges of distributed
  message delivery. Essential background reading.
