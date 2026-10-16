---
name: concurrency-and-locking
description: Identifying and fixing race conditions, deadlocks, and concurrency bugs: establishes happens-before relationships, chooses the right primitive (mutex, rwlock, atomic, channel), detects and breaks deadlock cycles with lock ordering, fixes TOCTOU races, uses CAS loops and copy-on-write atomics, pads to cache lines to eliminate false sharing, and runs the race detector. Use when you want to fix a race condition, debug a deadlock, make this thread-safe, use atomics correctly, design a lock hierarchy, understand the memory model, use channels vs mutexes, avoid lock contention, or reason about concurrent code.
---

## concurrency-and-locking

Design concurrent code correctly — understand the memory model before reaching for a lock.

### 1. Name what you are protecting, not what you are locking

The most common concurrency mistake is adding a lock without articulating the invariant it
protects. Before writing any synchronisation code, write a comment:

```
// INVARIANT: balance >= 0 at all times.
// INVARIANT: items and itemCount are always consistent with each other.
// GUARD: mu protects all fields below.
```

If you cannot state the invariant, you cannot reason about whether your lock is correct.

---

### 2. The memory model — why reads and writes are not what you think

Modern CPUs and compilers reorder instructions. Without synchronisation, thread A's write
is not guaranteed to be visible to thread B, even after A completes the write.

**Happens-before (HB):** a write W *happens-before* a read R if every thread that reads R
is guaranteed to see W's value. Synchronisation primitives establish HB edges.

```
Thread A                    Thread B
--------                    --------
x = 1                       // may see x = 0 even after A writes 1
mu.Lock()        ──HB──►   mu.Lock()   // B is guaranteed to see x = 1
x = 2                       print(x)   // prints 2
mu.Unlock()                 mu.Unlock()
```

**Without HB, even a single read/write of a 64-bit integer is not atomic on all platforms.**
This is why `volatile` in Java/C++ is not sufficient alone, and why `sync/atomic` in Go
must be used instead of plain variable access from multiple goroutines.

---

### 3. Identify the pattern before picking a primitive

| Pattern | Right primitive |
|---------|----------------|
| One writer, many readers, low contention | `sync.RWMutex` (Go), `ReentrantReadWriteLock` (Java), `threading.RLock` (Python) |
| One writer, many readers, high read contention | `atomic` reference swap (copy-on-write) |
| Counter incremented from many goroutines/threads | `atomic.Int64` / `AtomicLong` |
| Work distributed across goroutines | Buffered channel as semaphore |
| One-time initialisation | `sync.Once` (Go), `lazy` / class init (JVM) |
| Ordered pipeline between goroutines | Unbuffered channel |
| Fan-out / fan-in | `sync.WaitGroup` + channel |
| Producer-consumer with backpressure | Buffered channel with fixed capacity |

**Never reach for a mutex first.** Ask whether the problem can be solved with:
1. Immutability (share-nothing, copy the data)
2. Confinement (only one goroutine/thread ever owns the data)
3. Channels / message passing
4. An atomic operation

Only then: a mutex.

---

### 4. Mutexes — rules that prevent every common bug

```go
// Go

type SafeCounter struct {
    mu    sync.Mutex
    count int
}

func (c *SafeCounter) Inc() {
    c.mu.Lock()
    defer c.mu.Unlock()   // ✅ always defer — never skip unlock on error paths
    c.count++
}

func (c *SafeCounter) Value() int {
    c.mu.Lock()
    defer c.mu.Unlock()
    return c.count
}
```

```java
// Java — prefer java.util.concurrent over synchronized blocks

private final ReentrantLock mu = new ReentrantLock();
private int count = 0;

public void inc() {
    mu.lock();
    try {
        count++;
    } finally {
        mu.unlock();   // ✅ always in finally — never skip unlock on exception
    }
}
```

**Rules:**
- Lock the narrowest scope possible. Never hold a lock while doing I/O, sleeping, or calling
  external code you don't control.
- Never call a function that acquires the same lock (unless it's a `ReentrantLock` / recursive
  mutex). Self-deadlock.
- Never expose the guarded data outside the lock boundary — returning a pointer to a field
  while holding a lock does not protect the field after the lock is released.

---

### 5. Detect and break deadlocks

**Deadlock requires all four Coffman conditions simultaneously:**
1. Mutual exclusion — resources are not shareable
2. Hold and wait — thread holds one lock while waiting for another
3. No preemption — locks cannot be forcibly taken
4. Circular wait — A waits for B, B waits for A

**Break circular wait with a global lock ordering:**

```go
// ❌ Deadlock: goroutine 1 holds mu_a, waits for mu_b
//              goroutine 2 holds mu_b, waits for mu_a
func transfer(from, to *Account, amount int) {
    from.mu.Lock(); defer from.mu.Unlock()
    to.mu.Lock();   defer to.mu.Unlock()     // ← order depends on caller
    from.balance -= amount
    to.balance   += amount
}

// ✅ Always lock in a globally consistent order (e.g., by account ID)
func transfer(from, to *Account, amount int) {
    first, second := from, to
    if from.id > to.id {
        first, second = to, from
    }
    first.mu.Lock();  defer first.mu.Unlock()
    second.mu.Lock(); defer second.mu.Unlock()
    from.balance -= amount
    to.balance   += amount
}
```

**Detect deadlocks in development:**
```go
// Go — the runtime detects goroutine deadlocks automatically.
// "all goroutines are asleep - deadlock!" is printed and the program exits.
// For partial deadlocks (some goroutines still running), use:
go func() {
    time.Sleep(5 * time.Second)
    buf := make([]byte, 1<<20)
    n := runtime.Stack(buf, true)
    log.Printf("goroutine dump:\n%s", buf[:n])
}()
```

```bash
# Java — thread dump on a live JVM
jcmd <pid> Thread.print        # shows all threads and their lock wait graph
# Or: kill -3 <pid>  (SIGQUIT prints thread dump on Linux)
# Look for: "waiting to lock" chains that form a cycle
```

```python
# Python — the GIL prevents true data races but not deadlocks on I/O-bound threads
import faulthandler, signal
faulthandler.register(signal.SIGUSR1)   # kill -USR1 <pid> dumps all thread tracebacks
```

---

### 6. TOCTOU — time-of-check to time-of-use races

A check followed by an action is never atomic unless you hold the lock across both.

```go
// ❌ TOCTOU: another goroutine can modify m between the check and the write
if _, exists := m[key]; !exists {
    m[key] = computeExpensiveValue()
}

// ✅ sync.Map with LoadOrStore — atomic check-and-set
actual, loaded := sm.LoadOrStore(key, computeExpensiveValue())

// ✅ Or mutex held across both check and write
mu.Lock()
if _, exists := m[key]; !exists {
    m[key] = computeExpensiveValue()
}
mu.Unlock()

// ✅ sync.Once for one-time initialisation
var (
    instance *Service
    once     sync.Once
)
func GetService() *Service {
    once.Do(func() { instance = &Service{} })
    return instance
}
```

```python
# ❌ TOCTOU in filesystem operations — classic race
if not os.path.exists(path):
    open(path, 'w').write(data)      # another process can create file between check and open

# ✅ Use O_CREAT|O_EXCL — atomic at the kernel level
import os
try:
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    with os.fdopen(fd, 'w') as f:
        f.write(data)
except FileExistsError:
    pass   # another writer won the race — handle appropriately
```

---

### 7. Atomics — when and how to use them correctly

Atomics are faster than mutexes for single-value operations but are subtle. Use them only
for counters, flags, and reference swaps — not for multi-field invariants.

```go
// Go
import "sync/atomic"

var requestCount atomic.Int64   // ✅ safe from any goroutine

// ❌ This is NOT atomic — two separate atomic ops are not atomic together
if atomic.LoadInt64(&balance) >= amount {
    atomic.AddInt64(&balance, -amount)   // another goroutine can deduct between the two ops
}

// ✅ Compare-and-swap for conditional update
func deduct(balance *atomic.Int64, amount int64) bool {
    for {
        old := balance.Load()
        if old < amount { return false }
        if balance.CompareAndSwap(old, old-amount) { return true }
        // CAS failed — another goroutine changed the value; retry
    }
}
```

```java
// Java
import java.util.concurrent.atomic.*;

AtomicLong balance = new AtomicLong(1000);

// Compare-and-swap loop (same pattern as Go)
long old, next;
do {
    old = balance.get();
    if (old < amount) return false;
    next = old - amount;
} while (!balance.compareAndSet(old, next));
return true;
```

**Copy-on-write with atomic reference — high-read, low-write maps:**
```go
// Instead of an RWMutex on a frequently-read map:
var routeTable atomic.Pointer[map[string]Handler]

// Writer: build a new map, swap atomically
func updateRoutes(newRoutes map[string]Handler) {
    routeTable.Store(&newRoutes)   // readers see either old or new, never partial
}

// Reader: zero contention
func route(path string) Handler {
    return (*routeTable.Load())[path]
}
```

---

### 8. Channels vs mutexes in Go (the real rule)

The Go proverb "share memory by communicating" is often misapplied.

| Use channels when | Use mutexes when |
|------------------|-----------------|
| Transferring ownership of data between goroutines | Protecting shared state that multiple goroutines read and write |
| Signalling events / coordinating lifecycle | Caches, counters, registries |
| Building pipelines and fan-out patterns | Data structures with complex multi-field invariants |

```go
// ✅ Channel for ownership transfer — the sender gives up the buffer
func producer(ch chan<- []byte) {
    buf := make([]byte, 4096)
    io.ReadFull(conn, buf)
    ch <- buf   // ownership moves to consumer; producer must not touch buf after this
}

// ✅ Mutex for shared state with invariants
type Cache struct {
    mu    sync.RWMutex
    items map[string]Item
}
func (c *Cache) Get(k string) (Item, bool) {
    c.mu.RLock(); defer c.mu.RUnlock()
    v, ok := c.items[k]; return v, ok
}
```

---

### 9. Avoid lock contention

High contention on a single mutex serialises goroutines and kills throughput.

**Shard the lock:**
```go
const shards = 256

type ShardedMap struct {
    shards [shards]struct {
        sync.RWMutex
        m map[string]int
        _ [64 - unsafe.Sizeof(sync.RWMutex{}) - 8]byte   // pad to cache line
    }
}

func (s *ShardedMap) shard(key string) int {
    h := fnv.New32a()
    h.Write([]byte(key))
    return int(h.Sum32()) % shards
}

func (s *ShardedMap) Set(key string, val int) {
    i := s.shard(key)
    s.shards[i].Lock()
    s.shards[i].m[key] = val
    s.shards[i].Unlock()
}
```

**False sharing — pad structs to cache line boundaries:**
```go
// ❌ Both counters share a 64-byte cache line — writes by goroutine A invalidate
// goroutine B's cache even though they modify different fields
type Counters struct {
    a int64
    b int64
}

// ✅ Each counter on its own cache line
type Counters struct {
    a struct {
        val int64
        _   [56]byte   // pad to 64 bytes
    }
    b struct {
        val int64
        _   [56]byte
    }
}
```

---

### 10. Race detector — always run it

```bash
# Go — built-in race detector (use in CI always)
go test -race ./...
go run -race main.go

# Java — thread sanitiser is not built-in, use:
# - Helgrind (Valgrind): valgrind --tool=helgrind ./program
# - ThreadSanitizer (TSan): compile with -fsanitize=thread (Kotlin Native, GraalVM native)
# - jcstress for JMM-level concurrency tests: https://github.com/openjdk/jcstress

# Python — no built-in race detector; use threading.Lock consistently and test
# with concurrent.futures stress tests
```

### Rules

- State the invariant before writing the lock. If you can't state it, you don't know what
  you're protecting.
- Never hold a lock across I/O, a sleep, or a call into external code.
- Always lock in a consistent global order to prevent deadlock cycles.
- Two atomic operations are never atomic together — use a mutex for multi-step invariants.
- Run the race detector in CI on every commit. Races that don't show up in happy-path tests
  will show up in production under load.
- Prefer immutability and confinement over sharing. The fastest lock is the one you don't take.
