---
name: logging
description: Add, improve, and fix structured logging in an application. Use when the user asks to add logging, fix noisy logs, improve log output, add structured logs, set up log levels, replace console.log with a real logger, add request tracing, or make logs parseable by a log aggregator like Datadog, CloudWatch, or Loki.
---

# Logging

Add logs that help you diagnose production incidents in minutes, not hours. Logs that are
too noisy are as useless as no logs — the goal is the right information at the right level.

## Ground rules

- **Read the codebase before adding logs.** Check what logger is already in use. Never
  introduce a second logging library into a project that already has one.
- **Use structured logging.** Key-value pairs or JSON, not interpolated strings. Aggregators
  (Datadog, CloudWatch, Loki, Splunk) can filter and alert on fields; they cannot parse
  sentences.
- **Never log secrets, PII, or credentials.** Scrub before logging: passwords, tokens,
  full credit card numbers, SSNs, raw request bodies that may contain any of the above.
- **Pick the right level.** A miscategorised level destroys the signal-to-noise ratio.
- **Logs are for operators, not developers.** Write messages that help someone who didn't
  write the code understand what happened and why.

---

## Step 0: Check what's already there

```bash
# Find the existing logger
grep -r "require.*logger\|import.*logger\|from.*logging\|winston\|pino\|bunyan\|log4j\|zap\|slog\|sentry" \
  --include="*.ts" --include="*.js" --include="*.py" --include="*.go" -l | head -10

# Check for raw console/print usage that should be replaced
grep -rn "console\.log\|console\.error\|print(\|fmt\.Print" \
  --include="*.ts" --include="*.js" --include="*.py" --include="*.go" | head -20
```

If a logger exists, use it. Read its configuration before adding anything.

---

## Log levels — when to use each

| Level | Use it for |
| --- | --- |
| **ERROR** | Something failed and a human needs to act. Unexpected exceptions, failed payments, data corruption. |
| **WARN** | Something unexpected happened but the system recovered. Deprecated API usage, retried operations, config fallbacks. |
| **INFO** | Normal significant events. Service started, user logged in, job completed, request served. |
| **DEBUG** | Detail useful during development or incident investigation. Query params, intermediate values, branch decisions. Off in production by default. |
| **TRACE** | Very fine-grained: every function call, loop iteration, raw payloads. Never on in production. |

The most common mistake: using `ERROR` for expected user errors (validation failures, 404s)
and `INFO` for every line of code. Both destroy the signal.

---

## Structured logging patterns

### Node.js — pino (preferred) or winston

```ts
// Setup — do this once, export the logger
import pino from "pino";

export const logger = pino({
  level: process.env.LOG_LEVEL ?? "info",
  // In production, output raw JSON. In dev, use pino-pretty for human output.
  transport:
    process.env.NODE_ENV !== "production"
      ? { target: "pino-pretty", options: { colorize: true } }
      : undefined,
  // Redact sensitive fields wherever they appear in log objects
  redact: ["req.headers.authorization", "body.password", "body.token", "*.creditCard"],
});

// Usage
logger.info({ userId: user.id, plan: user.plan }, "User upgraded plan");
logger.error({ err, orderId }, "Payment failed");  // pino serializes err automatically
logger.debug({ query, params }, "Running query");
```

Never use string interpolation: `logger.info("User " + id + " logged in")` — that's
unparseable. Always pass a context object as the first argument.

### Python — structlog (preferred) or standard logging

```python
# Setup
import structlog
import logging

logging.basicConfig(
    format="%(message)s",
    level=logging.getLevelName(os.getenv("LOG_LEVEL", "INFO")),
)

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),   # swap for ConsoleRenderer() in dev
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.root.level),
    logger_factory=structlog.stdlib.LoggerFactory(),
)

log = structlog.get_logger()

# Usage
log.info("user.plan_upgraded", user_id=user.id, plan=user.plan)
log.error("payment.failed", order_id=order_id, error=str(e))
log.debug("db.query", sql=query, params=params)
```

### Go — slog (stdlib, Go 1.21+) or zap

```go
// Setup with slog (no dependency)
import "log/slog"

logger := slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{
    Level: slog.LevelInfo,
}))
slog.SetDefault(logger)

// Usage
slog.Info("user.plan_upgraded", "user_id", userID, "plan", plan)
slog.Error("payment.failed", "order_id", orderID, "err", err)
slog.Debug("db.query", "sql", query)
```

---

## Request logging (HTTP)

Log every inbound request at INFO with: method, path, status code, duration, and a
request/trace ID. Do not log request bodies by default — they may contain PII.

### Express / Node.js

```ts
import { randomUUID } from "crypto";

app.use((req, res, next) => {
  const requestId = (req.headers["x-request-id"] as string) ?? randomUUID();
  const start = Date.now();

  // Attach a child logger with the request ID bound to every log in this request
  req.log = logger.child({ requestId });

  res.on("finish", () => {
    req.log.info(
      {
        method: req.method,
        path: req.path,
        status: res.statusCode,
        durationMs: Date.now() - start,
      },
      "request completed"
    );
  });

  next();
});
```

### FastAPI / Python

```python
import time, uuid
from fastapi import Request

@app.middleware("http")
async def log_requests(request: Request, call_next):
    request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
    start = time.perf_counter()

    with structlog.contextvars.bound_contextvars(request_id=request_id):
        response = await call_next(request)
        log.info(
            "request.completed",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=round((time.perf_counter() - start) * 1000, 2),
        )

    return response
```

---

## Error logging

Log errors with the full stack trace and enough context to reproduce:

```ts
// Node.js — pino serialises err correctly when passed as a field
try {
  await processOrder(orderId);
} catch (err) {
  logger.error({ err, orderId, userId }, "Order processing failed");
  throw err;   // re-throw; don't swallow unless you have a recovery path
}
```

```python
# Python — structlog + exc_info captures the traceback
try:
    process_order(order_id)
except Exception:
    log.error("order.processing_failed", order_id=order_id, exc_info=True)
    raise
```

Rules:
- Log at the point where the error is **handled**, not where it propagates.
- Don't log the same error multiple times as it bubbles up the call stack — one log per
  error at the boundary where you decide what to do with it.
- Always include context: IDs, operation names, relevant input values (scrubbed).

---

## What not to log

| Don't log | Reason |
| --- | --- |
| Passwords, tokens, API keys | Secrets in logs are a security incident |
| Full credit card numbers, SSNs | PII / compliance (PCI-DSS, GDPR) |
| Raw request/response bodies | May contain any of the above |
| Every function entry/exit at INFO | Noise that buries real events |
| Stack traces at DEBUG | Use ERROR or WARN for exceptions |
| IDs that are UUIDs at TRACE everywhere | Only useful if a bug is already known |

Use your logger's `redact` option (pino) or a scrubber middleware rather than manually
checking every log call.

---

## Replacing console.log / print

When you find raw `console.log` or `print` calls, replace them:

```ts
// Before
console.log("Starting job", jobId);
console.error("Failed:", err);

// After
logger.info({ jobId }, "Job started");
logger.error({ err, jobId }, "Job failed");
```

Do this incrementally — replace a file at a time, verify the output, commit. Don't
replace every `console.log` in the repo in one pass.

---

## Log aggregator output format

For Datadog, CloudWatch, Loki, or any aggregator, output must be JSON on stdout:

```json
{"level":"info","time":"2024-01-15T10:30:00.123Z","requestId":"abc-123","userId":"42","msg":"User upgraded plan","plan":"pro"}
```

Key fields every line should have:
- `level` — string (`info`, `error`, etc.)
- `time` — ISO 8601 timestamp
- `msg` — human-readable description of the event
- `service` — name of the service (set once at logger init, not per call)
- Any IDs relevant to the operation (`userId`, `orderId`, `requestId`)

---

## Checklist

- [ ] Existing logger found and used — no second library introduced
- [ ] All `console.log` / `print` replaced with structured logger calls
- [ ] Context object passed as first arg, message as second (`logger.info({...}, "msg")`)
- [ ] Log levels match severity — no `ERROR` for 404s, no `INFO` for every function call
- [ ] `redact` or scrubber configured for passwords, tokens, PII
- [ ] Every HTTP request logs method, path, status, duration, and request ID
- [ ] Errors logged with full context at the handling boundary, not at every layer
- [ ] Output is JSON in production, human-readable in development
- [ ] `LOG_LEVEL` configurable via environment variable
