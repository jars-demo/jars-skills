---
name: capacity-planning
description: >
  Modelling load, projecting resource ceilings, and deciding when and how to scale: derives
  request rates and data volumes from first principles, identifies the bottleneck resource
  (CPU, memory, I/O, connections, threads), calculates headroom and time-to-saturation,
  designs load tests that reflect real traffic shape, interprets results, and translates
  findings into concrete scaling decisions. Use when you want to "plan capacity", "estimate
  how much traffic we can handle", "find the bottleneck", "calculate how many servers we need",
  "plan for a traffic spike", "design a load test", "project database growth", "estimate
  connection pool size", or "prevent running out of headroom".
---

## capacity-planning

Model load, find bottlenecks, and make scaling decisions before the system finds them for you.

### 1. Establish the key numbers first

You cannot plan capacity without knowing the current state. Measure or derive these before
touching infrastructure.

**Traffic:**
```
RPS (requests per second)       = requests_per_day / 86,400
Peak RPS                        = avg_RPS × peak_multiplier
                                  (typical web: 3–10×; event-driven: up to 100×)
Read/write ratio                = read_ops / write_ops  (influences DB replica strategy)
```

**Latency budget:**
```
p50, p95, p99 latency           — from existing metrics (Prometheus, Datadog, CloudWatch)
Target SLA                      — what latency you've committed to users
Headroom                        = SLA_target − current_p99
```

**Resource utilisation (right now):**
```bash
# CPU — average and peak per instance
# Memory — RSS, heap, working set
# Network — bytes in/out per second
# Disk I/O — reads/writes per second, queue depth
# DB — active connections, query throughput, replication lag
# Thread/connection pools — utilisation %, queue depth
```

Collect these at the instance level, not just averaged across the fleet. A fleet average of
40% CPU can hide one instance at 95%.

### 2. Back-of-envelope: derive limits from first principles

Work out the theoretical ceiling for each resource. The lowest ceiling is the bottleneck.

**CPU ceiling:**
```
Single-threaded throughput      = 1 / avg_request_cpu_time
Multi-core throughput           = cores × single_threaded_throughput × (1 − overhead%)
Example:
  avg request takes 5 ms of CPU → 1 core handles 200 RPS
  8-core instance, 20% overhead → 8 × 200 × 0.8 = 1,280 RPS per instance
```

**Memory ceiling:**
```
Max RPS before OOM              = (available_memory − base_RSS) / per_request_allocation
Example:
  Instance: 4 GB RAM
  Base RSS: 800 MB
  Per-request allocation: 2 MB (including buffers, response body)
  → (4000 − 800) / 2 = 1,600 concurrent requests in flight
  At p99 latency 200 ms → throughput ceiling ≈ 1,600 / 0.2 = 8,000 RPS
```

**Connection pool ceiling (database):**
```
Max DB queries/sec              = pool_size / avg_query_duration_seconds
Example:
  Pool size: 20 connections
  Avg query: 10 ms = 0.01 s
  → 20 / 0.01 = 2,000 queries/sec ceiling
  If each request makes 3 queries → ~667 RPS before DB connections saturate
```

**I/O ceiling:**
```
Disk throughput limit           = device_MB_per_sec / avg_IO_size_MB
Network throughput limit        = NIC_bandwidth / avg_response_size
Example:
  NIC: 1 Gbps = 125 MB/s
  Avg response: 50 KB = 0.05 MB
  → 125 / 0.05 = 2,500 RPS before NIC saturates
```

Compile a table:

| Resource | Ceiling | Current load | Headroom | Time to saturation |
|----------|---------|-------------|----------|-------------------|
| CPU | 1,280 RPS | 320 RPS | 75% | ~9 months at 10%/mo growth |
| DB connections | 667 RPS | 320 RPS | 52% | ~5 months |
| Memory | 8,000 RPS | 320 RPS | 96% | Not the bottleneck |
| NIC | 2,500 RPS | 320 RPS | 87% | Not the bottleneck |

**The bottleneck is always the smallest headroom.** In this example: DB connections at 5 months.

### 3. Model traffic growth

```python
import math

def months_to_saturation(current_rps: float, ceiling_rps: float, monthly_growth_pct: float) -> float:
    """
    Returns the number of months until current_rps hits ceiling_rps
    at a constant monthly growth rate.
    """
    if current_rps >= ceiling_rps:
        return 0.0
    r = 1 + monthly_growth_pct / 100
    # current_rps * r^n = ceiling_rps  →  n = log(ceiling/current) / log(r)
    return math.log(ceiling_rps / current_rps) / math.log(r)

# Example:
print(months_to_saturation(320, 667, 10))   # → 8.8 months at 10 %/month growth
```

**Account for non-linear traffic:**
- Day-of-week patterns (weekday vs weekend)
- Seasonal spikes (Black Friday, year-end)
- Marketing event multipliers (email blast → 10× spike for 5 min)
- Viral effects (unpredictable; plan circuit breakers, not extra capacity)

### 4. Identify the bottleneck resource under load

Do not guess — reproduce it. Run a load test and watch all resources simultaneously.

**Load test with k6 (HTTP):**
```js
// load-test.js
import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  stages: [
    { duration: '2m', target: 100 },   // ramp up
    { duration: '5m', target: 100 },   // steady state
    { duration: '2m', target: 300 },   // stress
    { duration: '5m', target: 300 },   // steady at stress
    { duration: '2m', target: 0   },   // ramp down
  ],
  thresholds: {
    http_req_duration: ['p(99)<500'],   // 99th percentile < 500 ms
    http_req_failed:   ['rate<0.01'],   // error rate < 1 %
  },
};

export default function () {
  const res = http.get('https://staging.example.com/api/products');
  check(res, { 'status 200': (r) => r.status === 200 });
  sleep(1);
}
```

```bash
k6 run --out influxdb=http://localhost:8086/k6 load-test.js
```

**While the test runs, watch:**
```bash
# CPU per core (Linux)
mpstat -P ALL 2

# Memory pressure + swap
vmstat 2

# Network saturation
sar -n DEV 2

# Disk I/O queue depth (> 1 sustained = saturated)
iostat -x 2

# DB active connections vs pool size
SELECT count(*), state FROM pg_stat_activity GROUP BY state;

# Application thread pool queue (JVM)
jcmd <pid> Thread.print | grep -c 'waiting'
```

**The bottleneck is whichever resource hits ~80% first as VUs increase.** It is not necessarily
where errors start — errors lag behind saturation.

### 5. Little's Law — derive concurrency requirements

Little's Law: `L = λ × W`

```
L = average number of requests in the system (concurrency)
λ = arrival rate (RPS)
W = average time a request spends in the system (latency in seconds)

Example:
  Target: 500 RPS at p99 200 ms (0.2 s)
  Required concurrency: L = 500 × 0.2 = 100 concurrent requests

  Thread pool or connection pool must be sized to at least 100 + 20% buffer = 120.
  Below that, requests queue and latency climbs.
```

Use this to size:
- HTTP server thread pools (`--workers` in gunicorn, `workerThreads` in Node cluster)
- Database connection pools
- gRPC channel concurrency
- Message queue consumer concurrency

### 6. Database-specific capacity

**Row growth projection:**
```sql
-- PostgreSQL: estimate table growth rate from pg_stat_user_tables
SELECT
  relname                                               AS table,
  n_live_tup                                           AS live_rows,
  pg_size_pretty(pg_total_relation_size(relid))        AS total_size,
  -- Compute avg bytes per row
  pg_total_relation_size(relid) / NULLIF(n_live_tup,0) AS bytes_per_row
FROM pg_stat_user_tables
ORDER BY pg_total_relation_size(relid) DESC
LIMIT 10;
```

```python
def months_until_disk_full(
    current_rows: int,
    bytes_per_row: int,
    daily_insert_rate: int,
    disk_bytes_available: int,
) -> float:
    daily_growth_bytes = daily_insert_rate * bytes_per_row
    current_bytes = current_rows * bytes_per_row
    remaining = disk_bytes_available - current_bytes
    return remaining / daily_growth_bytes / 30
```

**Index bloat — check before it affects query plans:**
```sql
-- Tables where dead tuple ratio > 10 % (autovacuum may be lagging)
SELECT relname, n_dead_tup, n_live_tup,
       round(n_dead_tup::numeric / NULLIF(n_live_tup + n_dead_tup, 0) * 100, 1) AS dead_pct
FROM pg_stat_user_tables
WHERE n_dead_tup > 10000
ORDER BY dead_pct DESC;
```

### 7. Translate findings into scaling decisions

| Finding | Action |
|---------|--------|
| CPU bottleneck, stateless service | Horizontal scale — add instances behind load balancer |
| Memory bottleneck, large working set | Vertical scale — larger instance type; or shard the dataset |
| DB connection pool exhaustion | Increase pool size; or add PgBouncer/RDS Proxy for pooling |
| DB CPU / I/O bottleneck | Read replicas for read traffic; query optimisation; vertical scale |
| Network I/O bottleneck | CDN for static assets; response compression; pagination |
| Thread pool saturation | Async I/O rewrite; increase pool size up to CPU × 2 guideline |
| Disk growth | Archive old data; partition tables; object storage for blobs |

**Before scaling out horizontally, check:**
1. Is there a single query or endpoint consuming disproportionate resources? Fix it first.
2. Are there N+1 query patterns the profiler missed under low load?
3. Is caching applicable? A 90% cache hit rate reduces load by 10×.

### 8. Define scaling triggers (not guesses)

Set concrete, measurable thresholds that trigger scaling actions — not "when it feels slow."

```yaml
# Example autoscaling policy (Kubernetes HPA)
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: api-server
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: api-server
  minReplicas: 3
  maxReplicas: 20
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 60   # scale out before hitting 80%+ headroom
    - type: Pods
      pods:
        metric:
          name: http_request_duration_p99_seconds
        target:
          type: AverageValue
          averageValue: "0.3"      # scale when p99 > 300 ms
```

Scale on **p99 latency degradation** not just CPU — CPU can look fine while the queue
fills and latency climbs.

### Rules

- Measure current state before modelling future state. Capacity planning without baselines
  is fiction.
- Plan to 70% utilisation ceiling, not 100%. The last 30% is your incident response margin.
- Identify the bottleneck resource — scaling the wrong resource wastes money and time.
- Load test against staging with production-shaped traffic, not uniform synthetic load.
  Uniform load misses hot-key patterns, burst behaviour, and cache warming effects.
- Rerun capacity analysis after every significant feature that changes resource consumption
  (new query, new background job, new external call on the hot path).
- Document your assumptions. A capacity model is only as good as its inputs; when traffic
  behaves differently, you need to know which assumption was wrong.
