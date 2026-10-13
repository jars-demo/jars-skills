---
name: distributed-tracing
description: >
  Instrumenting services with distributed tracing end-to-end: initialises the OpenTelemetry SDK
  before any other import, propagates W3C TraceContext across HTTP calls, message queues, and
  database queries, adds meaningful span attributes and events, configures head-based and
  tail-based sampling, exports to Jaeger or Tempo, and reads traces to diagnose latency and
  failure across service boundaries. Use when you want to "add distributed tracing", "instrument
  with OpenTelemetry", "set up Jaeger or Tempo", "trace requests across services", "add trace
  context to logs", "debug slow requests", "find where latency comes from", or "correlate logs
  and traces".
---

## distributed-tracing

Add end-to-end distributed tracing to a service using OpenTelemetry.

### 1. Understand the data model

- **Trace** — the complete journey of one request across all services. Identified by a
  `traceId` (16-byte hex string shared by every span in the trace).
- **Span** — one unit of work (an HTTP handler, a DB query, a queue publish). Has a `spanId`,
  a `parentSpanId`, a start time, a duration, a status, attributes, and events.
- **Context propagation** — the mechanism that carries `traceId` + `spanId` across process
  boundaries (HTTP headers, message metadata, gRPC metadata).
- **Exporter** — ships completed spans to a backend (Jaeger, Grafana Tempo, Honeycomb,
  Datadog, OTLP collector).

```
Browser ──► API Gateway ──► Auth Service ──► User Service ──► PostgreSQL
              span 1          span 2            span 3          span 4
              └─────────────── traceId: abc123 ────────────────────────┘
```

### 2. Initialise the SDK — before everything else

The SDK must be the first code that runs. Auto-instrumentation patches Node built-ins at
require-time; if anything loads first, those calls go untraced.

```ts
// tracing.ts  ← must be the very first import in your entrypoint
import { NodeSDK } from '@opentelemetry/sdk-node';
import { OTLPTraceExporter } from '@opentelemetry/exporter-trace-otlp-http';
import { Resource } from '@opentelemetry/resources';
import { SEMRESATTRS_SERVICE_NAME, SEMRESATTRS_SERVICE_VERSION } from '@opentelemetry/semantic-conventions';
import { getNodeAutoInstrumentations } from '@opentelemetry/auto-instrumentations-node';

const sdk = new NodeSDK({
  resource: new Resource({
    [SEMRESATTRS_SERVICE_NAME]: process.env.OTEL_SERVICE_NAME ?? 'my-service',
    [SEMRESATTRS_SERVICE_VERSION]: process.env.npm_package_version ?? 'unknown',
  }),
  traceExporter: new OTLPTraceExporter({
    url: process.env.OTEL_EXPORTER_OTLP_ENDPOINT ?? 'http://localhost:4318/v1/traces',
  }),
  instrumentations: [
    getNodeAutoInstrumentations({
      '@opentelemetry/instrumentation-fs': { enabled: false }, // too noisy
    }),
  ],
});

sdk.start();

process.on('SIGTERM', () => sdk.shutdown());
```

```ts
// index.ts  — entrypoint
import './tracing';   // ← first line, before express/fastify/anything
import express from 'express';
// ...
```

```python
# Python — use the opentelemetry-instrument CLI wrapper instead of manual init
# so it patches libraries before your app code runs:
#   opentelemetry-instrument --service-name my-service python -m uvicorn app:app

# Or manually in main.py (must be before any library imports):
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.auto_instrumentation import sitecustomize

provider = TracerProvider(resource=Resource.create({"service.name": "my-service"}))
provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
trace.set_tracer_provider(provider)
```

### 3. Propagate context across boundaries

Auto-instrumentation handles HTTP client/server propagation automatically via W3C
`traceparent` headers. You need to handle it manually for:

**Message queues (BullMQ / Kafka):**
```ts
import { context, propagation, trace } from '@opentelemetry/api';
import type { Job } from 'bullmq';

// Producer — inject current context into job data
export async function enqueueEmail(data: EmailJobData) {
  const carrier: Record<string, string> = {};
  propagation.inject(context.active(), carrier);   // adds traceparent / tracestate
  await emailQueue.add('send', { ...data, _otel: carrier });
}

// Consumer — restore context so spans in the worker are children of the producer's span
new Worker('email', async (job: Job) => {
  const parentCtx = propagation.extract(context.active(), job.data._otel ?? {});
  return context.with(parentCtx, () => processEmail(job.data));
}, { connection: redis });
```

**Outbound HTTP (manual fetch):**
```ts
import { context, propagation } from '@opentelemetry/api';

async function callDownstream(url: string) {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  propagation.inject(context.active(), headers);   // injects traceparent automatically
  return fetch(url, { headers });
}
// Note: if you use node-fetch or undici with auto-instrumentation enabled,
// injection happens automatically — no manual step needed.
```

### 4. Create custom spans for business-critical operations

Auto-instrumentation traces infrastructure (HTTP, DB, Redis). Add manual spans for
domain logic that matters in production debugging.

```ts
import { trace, SpanStatusCode } from '@opentelemetry/api';

const tracer = trace.getTracer('payment-service');

export async function chargeCard(userId: string, amountCents: number) {
  return tracer.startActiveSpan('payment.charge', async (span) => {
    span.setAttributes({
      'payment.user_id': userId,
      'payment.amount_cents': amountCents,
      'payment.currency': 'USD',
    });

    try {
      const result = await stripeClient.charges.create({ amount: amountCents, currency: 'usd' });

      span.addEvent('stripe.charge.created', { 'charge.id': result.id });
      span.setStatus({ code: SpanStatusCode.OK });
      return result;
    } catch (err) {
      span.recordException(err as Error);
      span.setStatus({ code: SpanStatusCode.ERROR, message: (err as Error).message });
      throw err;
    } finally {
      span.end();   // always end — forgetting this leaks memory and drops the span
    }
  });
}
```

### 5. Add the right span attributes

Follow [OpenTelemetry semantic conventions](https://opentelemetry.io/docs/specs/semconv/)
so your backend can query and alert on standard fields.

**Always set:**
- `service.name`, `service.version` — set on the Resource, not per-span
- `http.method`, `http.route`, `http.status_code` — auto-instrumentation sets these
- `db.system`, `db.statement` (sanitised) — auto-instrumentation sets these

**Set on custom spans:**
```ts
span.setAttributes({
  // Use dot-separated namespaces — matches semconv style
  'user.id': userId,
  'order.id': orderId,
  'order.item_count': items.length,
  'payment.provider': 'stripe',
});
```

**Never put in attributes:**
- Passwords, tokens, API keys
- Full SQL with unsanitised user input
- PII beyond what your data retention policy allows (hash user IDs if needed)

### 6. Correlate traces with logs

Attach `traceId` and `spanId` to every log line so you can jump from a log entry to the
full trace.

```ts
// pino + OpenTelemetry
import pino from 'pino';
import { trace, context } from '@opentelemetry/api';

const logger = pino({
  mixin() {
    const span = trace.getActiveSpan();
    if (!span) return {};
    const { traceId, spanId } = span.spanContext();
    return { traceId, spanId };
  },
});
```

```python
# structlog + OpenTelemetry
import structlog
from opentelemetry import trace

def add_trace_context(logger, method, event_dict):
    span = trace.get_current_span()
    if span.is_recording():
        ctx = span.get_span_context()
        event_dict['trace_id'] = format(ctx.trace_id, '032x')
        event_dict['span_id']  = format(ctx.span_id, '016x')
    return event_dict

structlog.configure(processors=[add_trace_context, structlog.dev.ConsoleRenderer()])
```

### 7. Configure sampling

Sending 100% of spans is expensive at scale. Pick a strategy:

| Strategy | When to use | Config |
|----------|-------------|--------|
| **Always-on** | Development, low-traffic services | `AlwaysOnSampler` |
| **Head-based (ratio)** | High-traffic, cost-sensitive | `TraceIdRatioBased(0.1)` — 10% |
| **Parent-based** | Respect upstream sampling decisions | `ParentBasedSampler(root=TraceIdRatioBased(0.1))` |
| **Tail-based** | Sample 100% of errors/slow traces | Requires a collector (OpenTelemetry Collector + `tailsampling` processor) |

```ts
import { ParentBasedSampler, TraceIdRatioBased } from '@opentelemetry/sdk-trace-base';

const sdk = new NodeSDK({
  sampler: new ParentBasedSampler({
    root: new TraceIdRatioBased(
      process.env.NODE_ENV === 'production' ? 0.1 : 1.0
    ),
  }),
  // ...
});
```

**Tail-based sampling with the OTel Collector** (sample 100% of error traces, 5% of the rest):
```yaml
# otel-collector-config.yml
processors:
  tail_sampling:
    decision_wait: 10s
    policies:
      - name: errors
        type: status_code
        status_code: { status_codes: [ERROR] }
      - name: slow-traces
        type: latency
        latency: { threshold_ms: 1000 }
      - name: probabilistic-fallback
        type: probabilistic
        probabilistic: { sampling_percentage: 5 }
```

### 8. Deploy a backend

**Local dev (Docker Compose):**
```yaml
jaeger:
  image: jaegertracing/all-in-one:1.57
  ports:
    - "16686:16686"   # Jaeger UI
    - "4318:4318"     # OTLP HTTP receiver

# Or Grafana Tempo + Grafana
tempo:
  image: grafana/tempo:2.4.1
  command: [ "-config.file=/etc/tempo.yaml" ]
  volumes:
    - ./tempo.yaml:/etc/tempo.yaml
grafana:
  image: grafana/grafana:10.4.2
  environment:
    GF_SECURITY_ADMIN_PASSWORD: admin
  ports:
    - "3000:3000"
```

Point `OTEL_EXPORTER_OTLP_ENDPOINT=http://jaeger:4318` in your service and spans appear
in the Jaeger UI at `http://localhost:16686`.

### 9. Verify instrumentation

1. Make a request that crosses at least two services.
2. Open the Jaeger/Tempo UI and search by `service.name`.
3. Confirm: the trace shows all expected spans with correct parent-child relationships.
4. Confirm: a span started in service A is the parent of spans in service B.
5. Confirm: errors set `span.status = ERROR` and include a recorded exception.
6. Confirm: log lines include `traceId` matching the trace in the UI.

### Rules

- Import `./tracing` before anything else in your entrypoint — order is not negotiable.
- Always call `span.end()` in a `finally` block. Unclosed spans are dropped silently.
- Never store secrets or full PII in span attributes.
- Sanitise DB statements before setting `db.statement` — strip bind parameter values.
- Use `BatchSpanProcessor` in production, never `SimpleSpanProcessor` (it blocks the event
  loop on every span export).
- Keep custom span names stable — changing them breaks dashboards and alerts that query
  by operation name.
- If auto-instrumentation is too noisy (e.g., Redis pings every 2 s), disable specific
  instrumentations rather than turning off auto-instrumentation entirely.
