---
name: chaos-engineering
description: Running controlled chaos experiments to find resilience weaknesses before production does: defines a steady-state hypothesis, injects realistic faults (latency, pod kill, disk fill, dependency failure) with Toxiproxy, tc/netem, Litmus, and stress-ng, limits blast radius, observes system behaviour against the hypothesis, runs a GameDay, and turns findings into hardening tasks. Use when you want to run a chaos experiment, test resilience, simulate a database outage, inject latency, do a GameDay, test circuit breakers, verify retry logic works, or find hidden failure modes.
---

## chaos-engineering

Break things on purpose, in a controlled way, to find weaknesses before they find you.

### 1. The experiment structure — never skip this

A chaos run without a hypothesis is just vandalism. Every experiment has five parts:

```
1. Steady state   — what does "healthy" look like right now? (metric + threshold)
2. Hypothesis     — "if we inject X, the system will continue to Y"
3. Blast radius   — scope the experiment so failures stay contained
4. Inject fault   — introduce the failure
5. Observe        — did the system behave as hypothesised? if not, why?
```

Write it down before touching anything:

```markdown
## Experiment: DB primary failover

**Steady state:** order API p99 < 300 ms, error rate < 0.1 % over the last 5 min

**Hypothesis:** if the primary database node fails, the app reconnects to the
replica within 10 s and resumes serving requests with < 1 % errors

**Blast radius:** staging environment only; 10 % of synthetic traffic

**Fault:** kill the primary PostgreSQL container

**Abort condition:** error rate > 5 % for > 60 s → stop the experiment immediately
```

---

### 2. Blast radius control — non-negotiable

Never run a chaos experiment without limiting the blast radius. Start as small as possible
and expand only when confidence is high.

| Dimension | How to limit |
|-----------|-------------|
| Environment | Start in staging; never start in production |
| Traffic | Route a percentage of traffic to the experiment cohort (feature flag, header) |
| Time | Set a hard end time; use a kill switch to stop injection immediately |
| Scope | Target one service, one region, one AZ — not the whole fleet |
| Data | Use synthetic or shadow traffic; never experiment on live user payment flows |

**Abort conditions must be defined before the experiment starts**, not decided in the moment.
If the abort metric is breached, stop the fault injection immediately and let the system
recover before investigating.

---

### 3. Tools

| Tool | Best for |
|------|---------|
| [Chaos Monkey](https://github.com/Netflix/chaosmonkey) | Random EC2/instance termination |
| [Litmus](https://litmuschaos.io) | Kubernetes-native fault injection (pod kill, node drain, network chaos) |
| [chaos-mesh](https://chaos-mesh.org) | Kubernetes: network partition, latency, pod failure, I/O fault |
| [Toxiproxy](https://github.com/Shopify/toxiproxy) | TCP-level latency, jitter, bandwidth, disconnect — great for local/CI |
| [tc + netem](https://wiki.linuxfoundation.org/networking/netem) | Linux kernel network emulation — no extra install |
| [stress-ng](https://github.com/ColinIanKing/stress-ng) | CPU, memory, and I/O saturation |
| [kill / SIGSTOP](https://man7.org/linux/man-pages/man1/kill.1.html) | Process pause/kill — no tools needed |

---

### 4. Fault recipes

#### Latency injection — Toxiproxy (local / CI)

```bash
# Install
brew install toxiproxy   # or download binary from releases

# Start proxy
toxiproxy-server &

# Create a proxy in front of your PostgreSQL
toxiproxy-cli create postgres_proxy --listen 0.0.0.0:5433 --upstream localhost:5432

# Add 300 ms latency with 50 ms jitter (simulates a flaky network)
toxiproxy-cli toxic add postgres_proxy --type latency --attribute latency=300 --attribute jitter=50

# Point your app at port 5433 instead of 5432
DATABASE_URL=postgresql://user:pass@localhost:5433/mydb

# Observe — does your connection pool handle it? do queries time out gracefully?

# Remove the toxic
toxiproxy-cli toxic remove postgres_proxy --toxicName latency_downstream

# Nuclear option — cut the connection entirely (timeout simulation)
toxiproxy-cli toxic add postgres_proxy --type timeout --attribute timeout=0
```

#### Network latency — Linux tc/netem (no extra install)

```bash
# Add 200 ms delay to all outbound traffic on eth0
tc qdisc add dev eth0 root netem delay 200ms

# Add 200 ms delay with 20 ms jitter and 10 % packet loss
tc qdisc add dev eth0 root netem delay 200ms 20ms loss 10%

# Remove
tc qdisc del dev eth0 root

# Scope to a specific destination IP only (e.g., your DB server)
tc qdisc add dev eth0 root handle 1: prio
tc qdisc add dev eth0 parent 1:3 handle 30: netem delay 200ms
tc filter add dev eth0 protocol ip parent 1:0 prio 3 u32 \
  match ip dst <DB_IP>/32 flowid 1:3
```

#### Pod kill — Kubernetes / Litmus

```yaml
# litmus-pod-delete.yaml
apiVersion: litmuschaos.io/v1alpha1
kind: ChaosEngine
metadata:
  name: order-service-pod-delete
  namespace: staging
spec:
  appinfo:
    appns: staging
    applabel: "app=order-service"
    appkind: deployment
  chaosServiceAccount: litmus-admin
  experiments:
    - name: pod-delete
      spec:
        components:
          env:
            - name: TOTAL_CHAOS_DURATION
              value: "60"          # inject for 60 s
            - name: CHAOS_INTERVAL
              value: "10"          # kill a pod every 10 s
            - name: FORCE
              value: "false"       # graceful kill first
```

```bash
kubectl apply -f litmus-pod-delete.yaml
# Watch your monitoring dashboard — does the deployment recover?
# Does the load balancer stop routing to the killed pod fast enough?
kubectl delete -f litmus-pod-delete.yaml   # stop the experiment
```

#### CPU saturation — stress-ng

```bash
# Saturate 2 CPU cores for 60 seconds
stress-ng --cpu 2 --timeout 60s --metrics-brief

# Does your service degrade gracefully? Does it shed load or just get slower?
# Watch: request queue depth, p99 latency, error rate
```

#### Disk fill — simulate storage pressure

```bash
# Fill disk to 90 % capacity temporarily
fallocate -l $(df / | awk 'NR==2 {printf "%.0f", $4 * 0.8}')K /tmp/chaos_fill

# Observe: does the app handle ENOSPC errors? do logs rotate? does the DB crash?

# Clean up
rm /tmp/chaos_fill
```

#### Dependency kill — simulate a downstream service going down

```bash
# Block all traffic to an external dependency IP/port with iptables
iptables -A OUTPUT -p tcp --dport 443 -d api.stripe.com -j DROP

# Does your circuit breaker trip? Does the error surface cleanly to the user?
# Does the retry logic back off or hammer the blocked endpoint?

# Remove the rule
iptables -D OUTPUT -p tcp --dport 443 -d api.stripe.com -j DROP
```

---

### 5. What to observe during an experiment

Run the experiment and watch these simultaneously:

```
✓ Error rate          — is it within the abort threshold?
✓ p99 latency         — is it degrading or holding?
✓ Retry counters      — are retries firing? are they backing off?
✓ Circuit breaker     — did it open? did it half-open and recover?
✓ Queue depth         — is work piling up?
✓ Downstream errors   — is the fault spreading to other services?
✓ Recovery time       — how long from fault injection to steady state restored?
```

Record the actual numbers, not just "it worked" or "it failed."

---

### 6. GameDay — structured team exercise

A GameDay is a scheduled, team-wide chaos experiment run like a fire drill.

```markdown
## GameDay runbook template

**Date:** YYYY-MM-DD  **Duration:** 2 hours  **Environment:** staging

### Scenario
Primary database AZ goes down. Replica promoted. S3 returns 503 for 5 min.

### Roles
- Experiment lead:   runs the fault injection, watches abort conditions
- Observability:     monitors dashboards, calls abort if threshold breached
- On-call engineer:  responds as if this were a real incident
- Scribe:            records timeline, findings, and action items

### Timeline
| Time  | Action |
|-------|--------|
| T+0   | Baseline captured, steady state confirmed |
| T+5   | Kill primary DB container |
| T+15  | Restore primary DB |
| T+20  | Inject S3 503 responses via Toxiproxy |
| T+30  | Remove S3 fault |
| T+35  | Debrief begins |

### Findings → action items
| Finding | Severity | Owner | Due |
|---------|----------|-------|-----|
| Replica failover took 45 s, SLA is 10 s | High | DB team | 2 weeks |
| S3 errors surfaced as 500 to users, not 503 | Medium | API team | 1 month |
```

---

### 7. Turn findings into hardening

Every experiment that reveals a gap produces a ticket:

| Finding | Hardening action |
|---------|----------------|
| Circuit breaker never opened | Add circuit breaker; tune failure threshold |
| Retry logic hammered the broken dependency | Add exponential back-off + jitter |
| Failover took 45 s | Tune health check interval + DB connection timeout |
| Error from dependency leaked as 500 | Map external errors to appropriate status codes |
| Service crashed on disk full | Add ENOSPC error handling; set up log rotation |
| Downstream failure spread to callers | Add bulkhead / timeout on the outbound call |

### Rules

- Define the hypothesis and abort conditions before starting. Never improvise mid-experiment.
- Start in staging. Graduate to production only after multiple successful staging runs.
- One fault at a time. Injecting multiple faults simultaneously makes root cause impossible
  to determine.
- Always have a kill switch ready — a single command that removes all fault injection
  immediately. Test the kill switch before running the experiment.
- Never experiment on payment flows, PII pipelines, or data that cannot be rolled back
  without explicit sign-off from the team.
- Document every run: hypothesis, what actually happened, recovery time, action items.
  An undocumented chaos run teaches the team nothing.
