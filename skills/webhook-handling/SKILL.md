---
name: webhook-handling
description: Receiving, verifying, and processing webhooks reliably: verifies signatures before touching the payload, returns 200 immediately and processes in the background, makes handlers idempotent, handles retries and out-of-order delivery, and never exposes raw errors to the sender. Use when you want to handle webhooks, verify a Stripe or GitHub webhook signature, process webhook events, avoid duplicate webhook processing, respond to webhooks correctly, handle webhook retries, or secure a webhook endpoint.
---

## webhook-handling

Receive fast, verify first, process in the background, handle duplicates. In that order.

### 1. The four rules — get these wrong and everything else is irrelevant

1. **Verify the signature before reading the payload.** An unverified webhook is an
   unauthenticated POST from the internet.
2. **Return 200 immediately.** Senders retry on anything that is not 2xx. If you do work
   synchronously and it takes > 30 s, the sender retries and you process twice.
3. **Make every handler idempotent.** Senders guarantee at-least-once delivery. You will
   receive the same event more than once.
4. **Never return error details in the response body.** The sender does not need your stack
   trace. Log it; return a generic message.

---

### 2. Signature verification

Every serious webhook provider signs payloads with HMAC-SHA256. Verify before anything else.
Use the **raw request body** — not parsed JSON. Parsing changes whitespace and key order,
breaking the signature.

```python
# routes/webhook_routes.py
"""
routes/webhook_routes.py
------------------------
Webhook ingestion endpoints. Verifies signatures, enqueues events for async processing.
Never does business logic synchronously.

Depends on: lib/webhook_verifier.py, lib/queue.py, lib/logger.py
Used by:    external webhook senders (Stripe, GitHub, etc.)
"""

import hashlib
import hmac
from fastapi import APIRouter, Header, HTTPException, Request
from lib.logger import get_logger
from lib.queue import enqueue_webhook_event
from config.settings import settings

router = APIRouter(prefix="/webhooks")
logger = get_logger(__name__)


@router.post("/stripe")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(..., alias="Stripe-Signature"),
):
    # 1. Read raw bytes — do NOT await request.json() here
    raw_body = await request.body()

    # 2. Verify signature before touching the payload
    if not verify_stripe_signature(raw_body, stripe_signature, settings.stripe_webhook_secret):
        logger.warning("Stripe webhook signature verification failed.")
        raise HTTPException(status_code=400, detail="Invalid signature")

    # 3. Return 200 immediately — enqueue for async processing
    import json
    event = json.loads(raw_body)
    await enqueue_webhook_event("stripe", event)
    logger.info("Stripe webhook accepted. event_type=%s event_id=%s", event.get("type"), event.get("id"))

    return {"received": True}


def verify_stripe_signature(payload: bytes, header: str, secret: str) -> bool:
    """
    Verifies a Stripe webhook signature using HMAC-SHA256.
    Stripe sends: Stripe-Signature: t=<timestamp>,v1=<signature>

    Raises nothing — returns False on any verification failure so
    the caller decides the HTTP response.
    """
    try:
        parts = dict(item.split("=", 1) for item in header.split(","))
        timestamp = parts["t"]
        expected_sig = parts["v1"]

        # Replay attack protection — reject events older than 5 minutes
        import time
        if abs(time.time() - int(timestamp)) > 300:
            logger.warning("Stripe webhook timestamp too old. age_s=%d", abs(time.time() - int(timestamp)))
            return False

        signed_payload = f"{timestamp}.{payload.decode('utf-8')}"
        computed = hmac.new(
            secret.encode("utf-8"),
            signed_payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(computed, expected_sig)
    except Exception as exc:
        logger.error("Stripe signature verification error. error=%s", exc)
        return False
```

```ts
// lib/webhookVerifier.ts
/**
 * lib/webhookVerifier.ts
 * ----------------------
 * HMAC-SHA256 signature verification for webhook endpoints.
 * Works for Stripe, GitHub, and any provider using the same scheme.
 *
 * Depends on: node:crypto, lib/logger.ts
 * Used by:    routes/webhookRoutes.ts
 */

import { createHmac, timingSafeEqual } from 'crypto';
import { logger } from './logger';

export function verifyStripeSignature(
  rawBody: Buffer,
  header: string,
  secret: string,
): boolean {
  try {
    const parts = Object.fromEntries(header.split(',').map(p => p.split('=')));
    const timestamp = parts['t'];
    const expected  = parts['v1'];

    // Replay protection — reject events older than 5 minutes
    const age = Math.abs(Date.now() / 1000 - Number(timestamp));
    if (age > 300) {
      logger.warning('Webhook timestamp too old', { age_s: age });
      return false;
    }

    const signed   = `${timestamp}.${rawBody.toString('utf8')}`;
    const computed = createHmac('sha256', secret).update(signed).digest('hex');

    return timingSafeEqual(Buffer.from(computed), Buffer.from(expected));
  } catch (err) {
    logger.error('Webhook signature verification error', { error: err });
    return false;
  }
}

export function verifyGitHubSignature(rawBody: Buffer, header: string, secret: string): boolean {
  try {
    // GitHub sends: X-Hub-Signature-256: sha256=<hex>
    const expected = header.replace('sha256=', '');
    const computed = createHmac('sha256', secret).update(rawBody).digest('hex');
    return timingSafeEqual(Buffer.from(computed), Buffer.from(expected));
  } catch {
    return false;
  }
}
```

---

### 3. Express / Node.js — raw body requirement

Signature verification needs the raw body. Express's `json()` middleware parses and
discards the raw bytes. Register the webhook route BEFORE the body parser, with a raw
body parser instead.

```ts
// app.ts
import express from 'express';
import { webhookRouter } from './routes/webhookRoutes';

const app = express();

// ✅ Webhook routes registered FIRST with raw body parser
app.use('/webhooks', express.raw({ type: 'application/json' }), webhookRouter);

// ✅ All other routes get JSON parsing
app.use(express.json());
app.use('/api', apiRouter);
```

```ts
// routes/webhookRoutes.ts
import { Router, Request, Response } from 'express';
import { verifyStripeSignature } from '../lib/webhookVerifier';
import { enqueueWebhookEvent } from '../lib/queue';
import { logger } from '../lib/logger';

const router = Router();

router.post('/stripe', async (req: Request, res: Response) => {
  const sig = req.headers['stripe-signature'] as string;

  // req.body is a Buffer here because of express.raw()
  if (!verifyStripeSignature(req.body, sig, process.env.STRIPE_WEBHOOK_SECRET!)) {
    logger.warning('Invalid Stripe signature');
    return res.status(400).json({ error: 'Invalid signature' });
  }

  const event = JSON.parse(req.body.toString());

  // Return 200 before doing any work
  res.status(200).json({ received: true });

  // Enqueue for async processing — never await this before responding
  await enqueueWebhookEvent('stripe', event).catch((err) =>
    logger.error('Failed to enqueue webhook event', { error: err, event_id: event.id })
  );
});

export { router as webhookRouter };
```

---

### 4. Idempotent event processing

Every handler must check whether the event was already processed. Stripe, GitHub, and
most providers retry delivery on network errors — you will see the same event_id twice.

```python
# workers/stripe_webhook_worker.py
"""
workers/stripe_webhook_worker.py
---------------------------------
Processes Stripe webhook events dequeued from the background queue.
Each handler is idempotent — safe to run more than once for the same event.

Depends on: repositories/webhook_log_repository.py, services/order_service.py
Used by:    queue consumer
"""

from lib.logger import get_logger
from repositories.webhook_log_repository import WebhookLogRepository

logger = get_logger(__name__)


async def handle_stripe_event(event: dict) -> None:
    event_id   = event["id"]
    event_type = event["type"]
    log_repo   = WebhookLogRepository()

    # Deduplication — already processed?
    if await log_repo.exists(event_id):
        logger.info("Duplicate webhook event skipped. event_id=%s type=%s", event_id, event_type)
        return

    logger.info("Processing webhook event. event_id=%s type=%s", event_id, event_type)

    try:
        await _dispatch(event_type, event["data"]["object"])
        await log_repo.mark_processed(event_id, event_type)
        logger.info("Webhook event processed. event_id=%s", event_id)

    except Exception as exc:
        logger.error(
            "Webhook event processing failed. event_id=%s type=%s error=%s "
            "action=event will be retried by queue",
            event_id, event_type, exc,
        )
        raise   # re-raise so the queue retries


async def _dispatch(event_type: str, data: dict) -> None:
    handlers = {
        "payment_intent.succeeded": _handle_payment_succeeded,
        "payment_intent.payment_failed": _handle_payment_failed,
        "customer.subscription.deleted": _handle_subscription_cancelled,
    }
    handler = handlers.get(event_type)
    if handler:
        await handler(data)
    else:
        logger.info("Unhandled webhook event type, ignoring. type=%s", event_type)
```

```sql
-- migration: create webhook_logs table for deduplication
CREATE TABLE webhook_logs (
    event_id    TEXT        PRIMARY KEY,
    event_type  TEXT        NOT NULL,
    processed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

---

### 5. Handle retries and exponential back-off

Providers retry with exponential back-off (Stripe retries up to 3 days). Your handler
must distinguish between retriable and non-retriable failures.

```python
# Retriable: temporary DB error, external service 503 → re-raise so queue retries
# Non-retriable: invalid event shape, business logic error → log and return (do not re-raise)

async def _handle_payment_succeeded(data: dict) -> None:
    order_id = data.get("metadata", {}).get("order_id")
    if not order_id:
        # Non-retriable — bad data from Stripe, retrying won't fix it
        logger.error(
            "payment_intent.succeeded missing order_id in metadata. "
            "action=investigate Stripe dashboard for event %s", data.get("id")
        )
        return   # do NOT raise — queue would retry forever

    # Retriable — DB errors propagate up
    await order_service.mark_paid(order_id, charge_id=data["id"])
```

---

### 6. Webhook endpoint security checklist

- [ ] Signature verified on every request using `hmac.compare_digest` (timing-safe)
- [ ] Raw body used for verification — not parsed JSON
- [ ] Replay attack protection — timestamp checked, reject if older than 5 minutes
- [ ] Returns 200 before processing — no synchronous business logic in the handler
- [ ] Event processing is idempotent — deduplication table checked before any side effect
- [ ] Error details never returned to sender — only generic `{"error": "Bad request"}`
- [ ] Webhook secret stored in secrets manager or env var — never hardcoded
- [ ] Endpoint is not behind CSRF protection middleware (webhook senders cannot set CSRF tokens)

### Rules

- Verify the signature first. A webhook endpoint without signature verification is an
  open HTTP endpoint that executes your business logic on demand for anyone.
- Use `hmac.compare_digest` / `timingSafeEqual` — not `==`. String equality is vulnerable
  to timing attacks.
- Return 200 before doing work. If you process synchronously and fail, the sender retries.
  If you enqueue and return 200, you control the retry logic.
- Never trust the event type in the payload to determine what happened — trust the
  verified payload from the provider's API if needed (re-fetch the object for sensitive events).
- Log the event_id on every log line in the handler. When debugging a webhook issue,
  the event_id is the only way to correlate logs with the provider's dashboard.
