---
name: background-jobs
description: Designing, implementing, and operating background job queues: picks the right backend (BullMQ, Celery, Sidekiq, pg-boss), makes jobs idempotent and safe to retry, sets concurrency and back-off correctly, handles dead-letter queues, and monitors job throughput and lag. Use when you want to add a background job, process tasks asynchronously, send emails in the background, set up a job queue, use BullMQ or Celery or Sidekiq, schedule a recurring task, handle retries, or process a queue.
---

## background-jobs

Add reliable background job processing to a service.

### 1. Decide what belongs in a background job

Move work out of the request/response cycle when it:

- Takes more than ~200 ms (email sending, PDF generation, image resizing)
- Must survive a server restart (payment webhooks, invoice generation)
- Can be retried independently (third-party API calls)
- Needs to be rate-limited or throttled (bulk notifications)
- Runs on a schedule (nightly reports, data cleanup)

Do **not** put work in a background job when:
- The HTTP response depends on the result (use async/await instead)
- The job is tiny and synchronous work is fine
- Failure must block the user action (use a database transaction instead)

### 2. Pick a queue backend

| Stack | Library | Queue backend |
|-------|---------|---------------|
| Node.js | [BullMQ](https://docs.bullmq.io) | Redis |
| Node.js (Postgres) | [pg-boss](https://github.com/timgit/pg-boss) | PostgreSQL |
| Python | [Celery](https://docs.celeryq.dev) | Redis or RabbitMQ |
| Ruby | [Sidekiq](https://sidekiq.org) | Redis |
| Go | [asynq](https://github.com/hibiken/asynq) | Redis |
| Any | [Temporal](https://temporal.io) | Temporal server (durable workflows) |

Use pg-boss if you already have Postgres and want to avoid adding Redis. Use BullMQ or Sidekiq
for high-throughput queues. Use Temporal when jobs are multi-step workflows that need to survive
partial failure.

### 3. Define a job

Keep job payloads small and serialisable. Store large data in the database and pass an ID.

```ts
// Node.js + BullMQ

// types/jobs.ts — shared payload types
export interface SendEmailJobData {
  to: string;
  templateId: string;
  vars: Record<string, string>;
  idempotencyKey: string;   // always include — used to deduplicate retries
}

// queues/email.ts
import { Queue } from 'bullmq';
import { redis } from '../lib/redis';

export const emailQueue = new Queue<SendEmailJobData>('email', {
  connection: redis,
  defaultJobOptions: {
    attempts: 5,
    backoff: { type: 'exponential', delay: 1000 },  // 1s, 2s, 4s, 8s, 16s
    removeOnComplete: { count: 1000 },
    removeOnFail: { count: 5000 },
  },
});
```

```python
# Python + Celery

# tasks/email.py
from celery import shared_task
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)

@shared_task(
    bind=True,
    max_retries=5,
    default_retry_delay=60,
    acks_late=True,       # acknowledge only after the task succeeds
    reject_on_worker_lost=True,
)
def send_email(self, to: str, template_id: str, vars: dict, idempotency_key: str):
    try:
        email_client.send(to=to, template=template_id, variables=vars)
    except TemporaryError as exc:
        raise self.retry(exc=exc, countdown=2 ** self.request.retries * 30)
```

### 4. Make every job idempotent

A job **will** run more than once — Redis crashes, workers restart, networks blip.
Design each job so running it twice produces the same result as running it once.

Techniques:
- Include an `idempotencyKey` in the payload; check it before doing work.
- Use `INSERT ... ON CONFLICT DO NOTHING` for database writes.
- Check a status field before sending a notification: `if email.sent_at: return`.
- For external API calls, use the provider's idempotency key header.

```ts
// workers/email.worker.ts
import { Worker } from 'bullmq';
import type { SendEmailJobData } from '../types/jobs';

new Worker<SendEmailJobData>('email', async (job) => {
  const already = await db.emailLog.findUnique({ where: { key: job.data.idempotencyKey } });
  if (already) {
    job.log(`Skipping duplicate — already sent at ${already.sentAt}`);
    return;
  }

  await emailProvider.send(job.data);

  await db.emailLog.create({
    data: { key: job.data.idempotencyKey, sentAt: new Date() },
  });
}, { connection: redis, concurrency: 5 });
```

### 5. Set concurrency and back-off correctly

- **Concurrency**: start with 5–10 workers per queue. Tune based on CPU, memory, and the
  external service's rate limit.
- **Exponential back-off**: double the delay on each retry to avoid hammering a struggling
  dependency. Add jitter (±10%) to spread load across workers.
- **Timeout**: always set a per-job timeout. A hanging job blocks a worker slot forever.

```ts
new Worker('email', handler, {
  connection: redis,
  concurrency: 10,
  lockDuration: 30_000,   // job must complete within 30 s or another worker can claim it
});
```

### 6. Handle failure and dead-letter queues

Jobs that exhaust their retries land in the failed set. Process them:

1. Alert on a spike in failed jobs (see step 8).
2. Investigate the failure reason in the job's `failedReason` field.
3. Fix the bug, then either replay the jobs or discard them after logging.

```ts
// Replay all failed jobs in a queue (BullMQ)
import { Queue } from 'bullmq';
const q = new Queue('email', { connection: redis });
const failed = await q.getFailed();
for (const job of failed) {
  await job.retry();
}
```

For Celery, use a dedicated dead-letter queue in RabbitMQ or inspect the failed task store:
```bash
celery -A myapp inspect reserved
celery -A myapp result <task-id>
```

### 7. Schedule recurring jobs

```ts
// BullMQ — cron-style repeatable job
await emailQueue.add(
  'weekly-digest',
  { templateId: 'weekly-digest', to: 'all-users' },
  { repeat: { pattern: '0 9 * * 1' } }  // every Monday at 09:00
);
```

```python
# Celery beat schedule
CELERY_BEAT_SCHEDULE = {
    'weekly-digest': {
        'task': 'tasks.email.send_weekly_digest',
        'schedule': crontab(hour=9, minute=0, day_of_week='monday'),
    },
}
```

Only schedule a job once — check if the repeatable job already exists before adding it:
```ts
const repeatable = await emailQueue.getRepeatableJobs();
const exists = repeatable.some((r) => r.name === 'weekly-digest');
if (!exists) await emailQueue.add('weekly-digest', payload, { repeat: { pattern: '...' } });
```

### 8. Monitor queue health

Track these signals:

| Metric | Alert threshold |
|--------|----------------|
| Queue depth (waiting) | Sustained > 1000 for 5 min |
| Job failure rate | > 1 % of completions over 10 min |
| Processing latency (wait time) | p99 > 30 s |
| Worker count | < 1 active worker |

**BullMQ + Bull Board (local dashboard):**
```bash
npm install @bull-board/express
```
```ts
import { createBullBoard } from '@bull-board/api';
import { BullMQAdapter } from '@bull-board/api/bullMQAdapter';
import { ExpressAdapter } from '@bull-board/express';

const serverAdapter = new ExpressAdapter().setBasePath('/admin/queues');
createBullBoard({ queues: [new BullMQAdapter(emailQueue)], serverAdapter });
app.use('/admin/queues', serverAdapter.getRouter());
```

Expose queue metrics to Prometheus via `bullmq-prometheus` or a custom collector, then
alert in Grafana.

### 9. Graceful shutdown

Workers must drain in-flight jobs before the process exits, or jobs will be requeued
(BullMQ) or lost (if `acks_late=False` in Celery).

```ts
// BullMQ graceful shutdown
const worker = new Worker('email', handler, { connection: redis });

process.on('SIGTERM', async () => {
  await worker.close();   // waits for current jobs to finish, stops accepting new ones
  process.exit(0);
});
```

```python
# Celery handles SIGTERM gracefully by default when acks_late=True
# Send SIGTERM to the worker process; it finishes current tasks before stopping.
```

### Rules

- Always set `attempts` and `backoff` — unbounded retries fill the queue forever.
- Never store secrets or PII in the job payload — store a reference ID and fetch at runtime.
- Never enqueue a job inside a database transaction — the job may run before the transaction
  commits, leading to "record not found" errors.
- Keep job handlers short. If a handler exceeds ~100 lines, extract helper functions.
- One queue per concern (email, notifications, reports) — mixing unrelated jobs in one queue
  makes it impossible to tune concurrency or prioritise independently.
- Test job handlers directly (call the handler function, not the queue) so tests don't need
  a live Redis.
