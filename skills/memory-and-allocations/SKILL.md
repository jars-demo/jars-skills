---
name: memory-and-allocations
description: Profiling and fixing memory leaks, excessive heap allocations, and GC pressure: captures heap snapshots and allocation timelines, identifies retaining paths and dominator objects, fixes event-listener accumulation, closure captures, unbounded caches, and goroutine leaks, and applies the same workflow across Node.js, Python, Go, and JVM runtimes. Use when you want to fix a memory leak, reduce memory usage, profile heap allocations, fix high GC pressure, analyse a heap dump, find what is retaining memory, debug an OOM crash, or RSS keeps growing.
---

## memory-and-allocations

Profile, diagnose, and fix memory leaks and allocation problems.

### 1. Distinguish the symptom before profiling

| Symptom | Likely cause |
|---------|-------------|
| RSS grows indefinitely, never shrinks | True leak — objects accumulate and are never collected |
| RSS grows then plateaus | Working-set growth — more data loaded, not necessarily a leak |
| Frequent GC pauses, high CPU | High allocation rate — too many short-lived objects created per request |
| OOM crash on a specific workload | Unbounded buffer, large object held in memory, or GC can't keep up |
| Memory high after load spike, never reclaimed | Fragmentation or runtime heap not returned to OS (common in Go, Node) |

Measure before assuming. "Memory is high" is not a diagnosis.

---

### 2. Node.js

#### Capture a heap snapshot

```bash
# Option A — from a running process (V8 inspector)
node --inspect src/index.js
# Open chrome://inspect → heap snapshot → take two snapshots (before and after load)

# Option B — programmatic (for automated capture on threshold breach)
```

```ts
import v8 from 'v8';
import fs from 'fs';

function takeHeapSnapshot(label: string) {
  const filename = `heap-${label}-${Date.now()}.heapsnapshot`;
  const buf = v8.writeHeapSnapshot(filename);
  console.log(`Heap snapshot written to ${buf}`);
}

// Trigger when RSS crosses threshold
setInterval(() => {
  const rss = process.memoryUsage().rss;
  if (rss > 500 * 1024 * 1024) takeHeapSnapshot('threshold');
}, 30_000);
```

Open `.heapsnapshot` in Chrome DevTools → **Memory** tab.

#### Read the snapshot

1. Switch to **Comparison** view between snapshot 1 (baseline) and snapshot 2 (after load).
2. Sort by **# Delta** — objects that accumulated between snapshots.
3. Click a constructor row → expand the **Retaining tree** to find what holds the reference.
4. The **Dominator** view shows which single objects retain the most memory transitively.

#### Common Node.js leak patterns

**Unbounded event listener accumulation:**
```ts
// ❌ Leak — new listener added on every request, EventEmitter grows forever
app.get('/data', (req, res) => {
  someEmitter.on('data', (d) => res.json(d));   // never removed
});

// ✅ Fix — use once(), or remove the listener explicitly
app.get('/data', (req, res) => {
  const handler = (d: unknown) => res.json(d);
  someEmitter.once('data', handler);
  // Or: req.on('close', () => someEmitter.off('data', handler));
});
```

**Closure capturing large scope:**
```ts
// ❌ Leak — the entire `largeBuffer` is kept alive by the closure
function process(largeBuffer: Buffer) {
  const id = largeBuffer.slice(0, 16).toString('hex');   // only need first 16 bytes
  setTimeout(() => {
    db.log(id);   // closure keeps `largeBuffer` alive for the full timeout duration
  }, 60_000);
}

// ✅ Fix — extract only what the closure needs
function process(largeBuffer: Buffer) {
  const id = largeBuffer.slice(0, 16).toString('hex');
  largeBuffer = null!;   // release reference before the closure forms
  setTimeout(() => db.log(id), 60_000);
}
```

**Unbounded in-memory cache:**
```ts
// ❌ Leak — Map grows forever, old entries never evicted
const cache = new Map<string, Result>();
async function compute(key: string): Promise<Result> {
  if (cache.has(key)) return cache.get(key)!;
  const result = await expensive(key);
  cache.set(key, result);
  return result;
}

// ✅ Fix — bound with LRU eviction (use lru-cache)
import { LRUCache } from 'lru-cache';
const cache = new LRUCache<string, Result>({ max: 1000, ttl: 1000 * 60 * 5 });
```

**Dangling timers / intervals keeping objects alive:**
```ts
// ❌ Leak — interval holds a reference to `this` forever even after the object is
//           logically done (common in service classes)
class PollingService {
  private timer?: NodeJS.Timer;
  start() { this.timer = setInterval(() => this.poll(), 5000); }
  // ✅ Fix — always provide a stop() and call it on shutdown
  stop() { clearInterval(this.timer); }
}
```

#### Profile allocation rate (find GC pressure)

```bash
node --prof src/index.js              # run with V8 profiler
node --prof-process isolate-*.log > processed.txt
# Search processed.txt for "[Summary]" → look at "ticks in GC"
# High GC% means too many short-lived allocations
```

---

### 3. Python

#### Baseline memory

```bash
pip install memory-profiler pympler
```

```python
# Line-by-line allocation profile for a specific function
from memory_profiler import profile

@profile
def process_records(records):
    result = []
    for r in records:
        result.append(transform(r))   # each append may trigger list realloc
    return result
```

#### Find what is alive in the heap

```python
import gc, sys
from pympler import muppy, summary

gc.collect()   # force collection before baseline
all_objects = muppy.get_objects()
summ = summary.summarize(all_objects)
summary.print_(summ)   # prints: type | count | total bytes
```

#### Tracemalloc — track allocation origin

```python
import tracemalloc

tracemalloc.start(10)   # keep 10-frame traceback
# ... run workload ...
snapshot = tracemalloc.take_snapshot()
top = snapshot.statistics('traceback')
for stat in top[:5]:
    print(stat)
    for line in stat.traceback.format():
        print('  ', line)
```

#### Common Python leak patterns

**Circular references with `__del__`** — Python's reference counter cannot collect cycles
that involve objects defining `__del__`. Use `weakref` instead:
```python
import weakref

class Node:
    def __init__(self, parent=None):
        # ❌ self.parent = parent  — strong ref cycle
        self.parent = weakref.ref(parent) if parent else None   # ✅
```

**Growing exception objects** — caught exceptions carry a traceback that holds frame locals,
which can keep large objects alive:
```python
try:
    process(large_dataframe)
except Exception as e:
    log_error(e)
    # ✅ Always del the exception variable in except blocks in tight loops
    del e
```

**Class-level mutable defaults** — unintentional class-level accumulation:
```python
class Handler:
    results = []          # ❌ shared across all instances
    def handle(self, r): self.results.append(r)

class Handler:
    def __init__(self): self.results = []   # ✅ per-instance
```

---

### 4. Go

#### Heap profiling with pprof

```go
import _ "net/http/pprof"   // registers /debug/pprof endpoints automatically
import "net/http"

go func() { http.ListenAndServe("localhost:6060", nil) }()
```

```bash
# Capture heap profile (live process)
go tool pprof http://localhost:6060/debug/pprof/heap

# In pprof shell:
(pprof) top10          # top 10 functions by retained memory
(pprof) list funcName  # annotated source for a specific function
(pprof) web            # open flame graph in browser (requires graphviz)

# Allocation profile — find where most bytes are allocated (not retained)
go tool pprof http://localhost:6060/debug/pprof/allocs
```

#### Common Go leak patterns

**Goroutine leak — channel never closed:**
```go
// ❌ goroutine blocks forever on ch receive if producer exits early
func process(ch <-chan Item) {
    go func() {
        for item := range ch { handle(item) }
    }()
}

// ✅ Use context cancellation for clean shutdown
func process(ctx context.Context, ch <-chan Item) {
    go func() {
        for {
            select {
            case item, ok := <-ch:
                if !ok { return }
                handle(item)
            case <-ctx.Done():
                return
            }
        }
    }()
}
```

**Slice header retaining a large backing array:**
```go
// ❌ keeps the entire 1 MB buf alive
func readPrefix(buf []byte) []byte {
    return buf[:16]
}

// ✅ copy to a new, correctly sized slice
func readPrefix(buf []byte) []byte {
    result := make([]byte, 16)
    copy(result, buf[:16])
    return result
}
```

**Reducing allocation rate with sync.Pool:**
```go
var bufPool = sync.Pool{
    New: func() any { return make([]byte, 0, 4096) },
}

func handleRequest(data []byte) {
    buf := bufPool.Get().([]byte)
    defer bufPool.Put(buf[:0])   // reset length, keep capacity

    buf = append(buf, data...)
    process(buf)
}
```

---

### 5. JVM (Java / Kotlin / Scala)

#### Capture a heap dump

```bash
# From a running JVM (replace <pid> with the process ID)
jcmd <pid> GC.heap_dump /tmp/heap.hprof

# On OOM (add to JVM flags — dump automatically):
-XX:+HeapDumpOnOutOfMemoryError -XX:HeapDumpPath=/tmp/oom.hprof
```

Analyse with **Eclipse MAT** (`mat.sh /tmp/heap.hprof`):
- **Leak Suspects Report** — automated top-level analysis
- **Dominator Tree** — largest retained object graphs
- **OQL** — query: `SELECT * FROM java.util.HashMap$Entry WHERE key.toString().startsWith("session:")`

#### GC tuning starting points

```bash
# Print GC logs (JDK 11+)
-Xlog:gc*:file=/tmp/gc.log:time,uptime:filecount=5,filesize=20m

# Analyse with GCEasy (upload gc.log) or gceasy.io for automated analysis
```

| Symptom | First thing to check |
|---------|---------------------|
| Long stop-the-world pauses | Switch G1 → ZGC or Shenandoah (`-XX:+UseZGC`) |
| High allocation rate | Find hot `new` sites with async-profiler |
| Old gen fills up | Static caches, `ThreadLocal` not removed, intern pool |
| Metaspace OOM | Class loader leak — dynamic class generation, OSGi, JRebel |

---

### 6. Universal rules

- **Measure first.** Never optimise memory without a profile showing what is actually retained
  and where it was allocated. Gut feelings about memory are almost always wrong.
- **Take two snapshots** — one at baseline, one after a load cycle. Compare deltas, not
  absolute sizes. Absolute sizes include cold-start allocations that are intentional.
- **Identify the retaining path**, not just the retained type. Knowing `String[]` is large
  tells you nothing; knowing `RequestContext → SessionCache → String[]` tells you everything.
- **Fix the root cause.** Wrapping a leak in an LRU cache treats the symptom. Find why the
  object is retained and remove the reference.
- **Verify the fix with another profile run.** Memory improvements that can't be measured
  didn't happen.
- **Watch RSS, not just heap.** Off-heap memory (direct byte buffers, native libs, mmap files,
  thread stacks) does not show up in heap snapshots.
