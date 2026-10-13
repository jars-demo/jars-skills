---
name: monitoring
description: >
  Adding application monitoring, metrics, and alerting: instruments the app with a metrics library
  (Prometheus/OpenTelemetry), exposes a /health and /metrics endpoint, defines alert rules for
  error rate, latency p99, and saturation, wires up a Grafana dashboard, and avoids leaking
  internal topology through public probes. Use when you want to "add monitoring", "set up
  Prometheus", "add a health check endpoint", "instrument my app", "set up Grafana", "add
  alerts", "track error rate or latency", or "make my service observable".
---

## monitoring

Add application monitoring, metrics, and alerting to a service.

### 1. Read the service first

1. Identify the runtime (Node.js, Python, Go, Java, etc.) and existing dependencies.
2. Check whether a `/health` or `/metrics` endpoint already exists.
3. Look for a `docker-compose.yml` or Kubernetes manifests — if present, Prometheus and Grafana
   can be added there.
4. Note the HTTP framework so you wire the middleware in the right place.

### 2. Add a /health endpoint

Add a lightweight health check endpoint that:

- Returns `200 OK` with `{"status": "ok"}` when the service is healthy.
- Returns `503 Service Unavailable` when a required dependency (database, cache) is down.
- Checks **only dependencies whose failure would stop the service from serving requests**.
- Never exposes hostnames, passwords, internal IPs, or stack traces in the response body.

```
GET /health
200  {"status":"ok","uptime":42}
503  {"status":"degraded","checks":{"db":"unreachable"}}
```

### 3. Instrument with metrics

Pick the library that fits the stack:

| Runtime | Library |
|---------|---------|
| Node.js | `prom-client` |
| Python | `prometheus-client` |
| Go | `prometheus/client_golang` |
| Java | `micrometer-registry-prometheus` |
| Any | OpenTelemetry SDK (exports to OTLP → Prometheus) |

Collect the four golden signals at minimum:

- **Latency** — HTTP request duration histogram, labeled by `method`, `route`, `status_code`.
- **Traffic** — request counter, same labels.
- **Errors** — counter or a ratio derived from the above (5xx / total).
- **Saturation** — event-loop lag (Node), thread-pool queue depth (Java), CPU % (Go/Python).

Expose `/metrics` in Prometheus text format. Protect it behind an internal network rule or
a bearer token — never make it public.

```js
// Node.js example (Express + prom-client)
import client from 'prom-client';
client.collectDefaultMetrics();

const httpDuration = new client.Histogram({
  name: 'http_request_duration_seconds',
  help: 'HTTP request duration',
  labelNames: ['method', 'route', 'status_code'],
  buckets: [0.005, 0.01, 0.05, 0.1, 0.5, 1, 5],
});

app.use((req, res, next) => {
  const end = httpDuration.startTimer();
  res.on('finish', () =>
    end({ method: req.method, route: req.route?.path ?? req.path, status_code: res.statusCode })
  );
  next();
});

app.get('/metrics', async (_req, res) => {
  res.set('Content-Type', client.register.contentType);
  res.end(await client.register.metrics());
});
```

### 4. Wire up Prometheus

Add a `prometheus.yml` scrape config or update the existing one:

```yaml
scrape_configs:
  - job_name: my-service
    scrape_interval: 15s
    static_configs:
      - targets: ['my-service:3000']
    metrics_path: /metrics
    # bearer_token_file: /etc/prometheus/token  # if endpoint is protected
```

If using Docker Compose, add a `prometheus` service and mount the config:

```yaml
prometheus:
  image: prom/prometheus:v2.51.2
  volumes:
    - ./prometheus.yml:/etc/prometheus/prometheus.yml:ro
  ports:
    - "9090:9090"
```

### 5. Define alert rules

Create `alerts.yml` and reference it from `prometheus.yml`:

```yaml
groups:
  - name: my-service
    rules:
      - alert: HighErrorRate
        expr: |
          rate(http_request_duration_seconds_count{status_code=~"5.."}[5m])
          / rate(http_request_duration_seconds_count[5m]) > 0.05
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "Error rate above 5 % for 2 minutes"

      - alert: SlowRequests
        expr: |
          histogram_quantile(0.99,
            rate(http_request_duration_seconds_bucket[5m])) > 1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "p99 latency above 1 s for 5 minutes"

      - alert: ServiceDown
        expr: up{job="my-service"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "my-service is not reachable by Prometheus"
```

Tune thresholds against real traffic — never copy alert rules blindly without understanding
the service's normal behaviour.

### 6. Add a Grafana dashboard

Add a `grafana` service to Compose (or deploy separately):

```yaml
grafana:
  image: grafana/grafana:10.4.2
  environment:
    GF_SECURITY_ADMIN_PASSWORD: "${GRAFANA_ADMIN_PASSWORD}"
  volumes:
    - grafana-data:/var/lib/grafana
  ports:
    - "3001:3000"
```

Provision the Prometheus datasource automatically:

```yaml
# grafana/provisioning/datasources/prometheus.yml
apiVersion: 1
datasources:
  - name: Prometheus
    type: prometheus
    url: http://prometheus:9090
    isDefault: true
```

Recommended dashboard panels:
- Request rate (RPS) per route
- Error rate (%) over time
- p50 / p95 / p99 latency
- Active connections / saturation gauge
- Service health (up/down indicator)

Export the dashboard JSON and commit it to `grafana/dashboards/` so it is reproducible.

### 7. Verify

1. Start the service and hit a few endpoints.
2. `curl http://localhost:<port>/health` → `200 {"status":"ok"}`.
3. `curl http://localhost:<port>/metrics` → Prometheus text with `http_request_duration_seconds_*` lines.
4. Open Prometheus → **Status → Targets**: `my-service` shows `UP`.
5. Open Grafana → confirm the dashboard populates with real data.
6. Trigger an error (e.g., call a nonexistent route) — verify the `5xx` counter increments.

### Rules

- Never expose `/metrics` publicly. Protect with network policy, mTLS, or a token.
- Never use the health endpoint to expose internal connection strings or secrets.
- Instrument at the framework middleware level — not inside every handler.
- Prefer histograms over averages for latency; averages hide tail-latency problems.
- Alert on symptoms (high error rate, slow p99) not on causes (high CPU). Cause-based alerts
  fire too often and lose their meaning.
- If the project already has a monitoring setup, extend it rather than replacing it.
