---
name: perf-profile
description: Profile, diagnose, and fix performance bottlenecks using the right tools for the stack. Use when the user says something is slow, asks why an endpoint is taking too long, wants to reduce memory usage, needs to find what is hogging CPU, says a query is slow, asks to profile the app, or wants to improve response time. Never guesses — always measures before changing code.
---

# Performance profiling

Find what is actually slow, fix only that thing, and verify the fix made a real difference.
Guessing about performance is how you spend a week optimizing the wrong function. Measure first.

## Ground rules

- **Measure before changing anything.** Form a hypothesis, collect data, then fix. Never
  optimise code based on intuition alone.
- **Read the code in the hot path before profiling.** You need enough context to interpret
  what the profiler is telling you.
- **One change at a time.** Apply one fix, re-profile, compare. Multiple simultaneous changes
  make it impossible to know which one helped (or hurt).
- **Establish a baseline.** Record the before metric (latency, throughput, memory, query time)
  so you can prove the fix worked.
- **Never regress correctness for speed.** A wrong answer returned in 1 ms is worse than a
  correct one returned in 100 ms.
- **Stop when the bottleneck is gone.** Don't keep micro-optimizing once the problem is fixed.

---

## Step 0: Define the problem

Before touching a profiler:

1. **What is slow?** Endpoint? Build step? batch job? CLI command?
2. **What is the observed metric?** p50/p95/p99 latency? Requests per second? Peak memory? CPU %?
3. **What is acceptable?** Know the target before you start. "Fast enough" is a number.
4. **When did it regress?** Check recent commits if it used to be fast:
   ```bash
   git log --oneline -20
   git bisect start   # if the culprit isn't obvious
   ```

---

## Profiling by stack

### Node.js / TypeScript

**CPU profiling — find where time goes**

```bash
# Built-in V8 profiler (no deps)
node --prof server.js
# run your workload (curl the slow endpoint a few times)
node --prof-process isolate-*.log > profile.txt
# open profile.txt — look for the top entries in [Summary] and [Bottom up]

# Or use clinic.js for a visual flame graph
npx clinic flame -- node server.js
# (serve workload while it runs, then open the generated HTML)

# For a quick scripted function
node --inspect-brk script.js
# Open chrome://inspect → "Open dedicated DevTools for Node" → Profiler tab
```

**Memory profiling — find leaks and over-allocation**

```bash
# Heap snapshot via DevTools
node --inspect server.js
# In Chrome DevTools → Memory → Take snapshot → run workload → take another → compare

# Or automate with heapdump
node -e "
  const heapdump = require('heapdump');
  // run workload
  heapdump.writeSnapshot('./heap-before.heapsnapshot');
"
```

**In-process timing (no profiler needed for a specific function)**

```ts
const start = performance.now();
await doTheThing();
console.log(`doTheThing: ${(performance.now() - start).toFixed(2)}ms`);
```

### Python

**CPU profiling**

```bash
# cProfile — built-in, good first pass
python -m cProfile -o profile.out -s cumulative your_script.py
python -c "import pstats; pstats.Stats('profile.out').strip_dirs().sort_stats('cumulative').print_stats(20)"

# py-spy — low-overhead profiler, attaches to a running process, no code changes
pip install py-spy
py-spy record -o profile.svg --pid <pid>      # flame graph as SVG
py-spy top --pid <pid>                         # live top-like view

# For web apps (FastAPI / Flask / Django)
pip install pyinstrument
# Wrap the request handler or add middleware:
# FastAPI: add PyinstrumentProfilerMiddleware
# Django: PYINSTRUMENT_PROFILE_DIR = '/tmp/profiles'
```

**Memory profiling**

```bash
pip install memory-profiler
# Decorate the function:
# from memory_profiler import profile
# @profile
# def my_function(): ...
python -m memory_profiler your_script.py

# For live heap inspection
pip install memray
memray run -o output.bin your_script.py
memray flamegraph output.bin     # opens a flame graph in the browser
```

**Quick in-process timing**

```python
import time
start = time.perf_counter()
do_the_thing()
print(f"do_the_thing: {(time.perf_counter() - start) * 1000:.2f}ms")
```

### Go

```bash
# pprof — built-in, industry standard
# 1. Import net/http/pprof in your main (or use runtime/pprof directly)
import _ "net/http/pprof"

# 2. Run the server and collect a 30-second CPU profile
go tool pprof http://localhost:6060/debug/pprof/profile?seconds=30

# 3. Inside pprof interactive shell:
(pprof) top 20          # top functions by cumulative time
(pprof) web             # open flame graph in browser (requires graphviz)
(pprof) list MyFunc     # annotate source with per-line costs

# Heap / memory
go tool pprof http://localhost:6060/debug/pprof/heap

# For a script (not a server):
import "runtime/pprof"
f, _ := os.Create("cpu.prof")
pprof.StartCPUProfile(f)
defer pprof.StopCPUProfile()
```

### Java / JVM

```bash
# JFR — low-overhead, built into the JDK (Java 11+)
java -XX:StartFlightRecording=duration=60s,filename=recording.jfr -jar app.jar
# Open recording.jfr in JDK Mission Control (jmc)

# async-profiler — flame graphs, attaches to running JVM
./asprof -d 30 -f profile.html <pid>   # HTML flame graph

# Quick timing
long start = System.nanoTime();
doTheThing();
System.out.printf("doTheThing: %.2fms%n", (System.nanoTime() - start) / 1e6);
```

---

## Database queries

Slow queries are one of the most common performance killers. Always check here before
profiling application code.

### Find slow queries

```sql
-- PostgreSQL: queries taking > 100ms
SELECT query, calls, mean_exec_time, total_exec_time
FROM pg_stat_statements
WHERE mean_exec_time > 100
ORDER BY mean_exec_time DESC
LIMIT 20;

-- MySQL: slow query log
SHOW VARIABLES LIKE 'slow_query_log';
SET GLOBAL slow_query_log = 'ON';
SET GLOBAL long_query_time = 0.1;  -- log queries > 100ms

-- SQLite: use EXPLAIN QUERY PLAN
EXPLAIN QUERY PLAN SELECT ...;
```

### Read the query plan

```sql
-- PostgreSQL
EXPLAIN (ANALYZE, BUFFERS) SELECT ...;
-- Look for: Seq Scan on large tables, nested loop joins, high actual rows vs estimated rows

-- MySQL
EXPLAIN FORMAT=JSON SELECT ...;

-- Look for:
-- "Seq Scan" instead of "Index Scan" → probably missing index
-- Estimated rows wildly different from actual → stale statistics
-- Nested loop on large tables → consider a hash join or index
```

### Common query fixes

| Symptom | Fix |
| --- | --- |
| `Seq Scan` on a large table with a `WHERE` clause | Add an index on the filtered column |
| `N+1` queries (1 query per row) | Fetch related data in one query or use eager loading |
| `SELECT *` when only 2 columns are needed | List columns explicitly; composite index can cover the query |
| Stale statistics | `ANALYZE table_name` (Postgres) / `ANALYZE TABLE t` (MySQL) |
| Large `OFFSET` pagination | Cursor-based pagination (keyset) instead of `OFFSET` |
| Missing index on a `JOIN` column | Index the foreign key column |

### Fix an N+1

```python
# Bad — 1 query for users + N queries for their orders
users = db.query(User).all()
for user in users:
    print(user.orders)   # lazy-loads each user's orders

# Good — 2 queries total (or 1 with a JOIN)
users = db.query(User).options(joinedload(User.orders)).all()
```

---

## Common application-level patterns

### Unnecessary work in the hot path

Read the code around the slow function. Ask:

- Is it reading a file or config on every request that could be loaded once at startup?
- Is it re-computing something that could be cached?
- Is it doing sequential I/O that could be parallel?

```ts
// Bad — reads config file on every request
app.get("/api/data", async (req, res) => {
  const config = JSON.parse(fs.readFileSync("./config.json"));  // every request!
  ...
});

// Good — load once at startup
const config = JSON.parse(fs.readFileSync("./config.json"));
app.get("/api/data", async (req, res) => { ... });
```

### Sequential I/O vs parallel I/O

```ts
// Bad — two independent fetches in series (~400ms)
const user = await fetchUser(id);
const orders = await fetchOrders(id);

// Good — run in parallel (~200ms)
const [user, orders] = await Promise.all([fetchUser(id), fetchOrders(id)]);
```

```python
# Python equivalent with asyncio
user, orders = await asyncio.gather(fetch_user(id), fetch_orders(id))
```

### Adding a cache

Only add a cache after confirming the operation is actually slow and called repeatedly.

```ts
// Simple in-memory cache with TTL (good for single-instance apps)
const cache = new Map<string, { value: unknown; expiresAt: number }>();

function getFromCache<T>(key: string): T | null {
  const entry = cache.get(key);
  if (!entry || Date.now() > entry.expiresAt) return null;
  return entry.value as T;
}

function setInCache(key: string, value: unknown, ttlMs: number) {
  cache.set(key, { value, expiresAt: Date.now() + ttlMs });
}
```

For distributed caches, use Redis via the app's existing client. Don't introduce a new
dependency without checking what's already available.

### Memory leaks (Node.js)

Common causes:

| Cause | Signal |
| --- | --- |
| Growing global/module-level arrays or Maps | Memory climbs and never falls between requests |
| Event listeners not removed | `process.on`, `emitter.on` called in a request handler |
| Closures capturing large objects | Lambda or callback holds a reference to a large scope |
| Timers not cleared | `setInterval` inside a function that gets called repeatedly |

```ts
// Bad — listener accumulates on every request
app.get("/start", (req, res) => {
  someEmitter.on("data", handleData);  // never removed!
  res.send("ok");
});

// Good — use once or clean up
app.get("/start", (req, res) => {
  someEmitter.once("data", handleData);
  res.send("ok");
});
```

---

## Measuring the fix

After applying a change, re-run the same measurement you started with.

```bash
# HTTP endpoint — compare before and after with autocannon (Node) or wrk
npx autocannon -c 10 -d 10 http://localhost:3000/api/slow
# look at: Req/Sec, Latency avg/p99

# Or with curl timing
curl -o /dev/null -s -w "time_total: %{time_total}s\n" http://localhost:3000/api/slow

# Python function — use timeit
python -m timeit -n 1000 "from mymodule import my_func; my_func()"

# Go benchmark
go test -bench=BenchmarkMyFunc -benchmem -count=5 ./...
```

Present the result as a before/after table:

| Metric | Before | After | Change |
| --- | --- | --- | --- |
| p50 latency | 420 ms | 38 ms | −91 % |
| p99 latency | 1 200 ms | 95 ms | −92 % |
| Memory (peak) | 512 MB | 210 MB | −59 % |

---

## When to stop

You are done when:
- The metric meets the target defined in Step 0.
- The fix is correct (existing tests pass).
- The improvement is confirmed with a real measurement, not an assumption.

Do not keep going once the target is met. Premature optimization beyond the bottleneck
wastes time and adds complexity.

---

## Checklist

- [ ] Baseline metric recorded before any change
- [ ] Profiler output read and the actual bottleneck identified (not guessed)
- [ ] One change applied at a time
- [ ] Fix verified by re-running the same measurement
- [ ] Before/after numbers compared
- [ ] Existing tests still pass
- [ ] No correctness regression introduced
- [ ] No new dependency added without checking what's already in the project
