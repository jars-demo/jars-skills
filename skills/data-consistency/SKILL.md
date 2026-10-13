---
name: data-consistency
description: >
  Reasoning about and implementing data consistency in distributed systems: picks the right
  consistency model (strong, eventual, causal), chooses a replication strategy (single-leader,
  multi-leader, leaderless), handles conflict detection and resolution, prevents split-brain,
  applies the right isolation level for database transactions, and makes deliberate CAP and
  PACELC trade-offs. Use when you want to "design a distributed system", "handle concurrent
  writes", "avoid split-brain", "choose a consistency model", "implement optimistic locking",
  "design for high availability", "handle replication lag", "use CRDTs", or "reason about
  CAP theorem".
---

## data-consistency

Design and implement data consistency in distributed systems deliberately.

### 1. Name the consistency model you need before writing any code

Consistency models exist on a spectrum. Choosing the wrong one causes either data loss or
unavailability — both are production incidents.

| Model | Guarantee | Typical use |
|-------|-----------|-------------|
| **Linearisability (strong)** | Every read sees the most recent write; operations appear instantaneous and globally ordered | Bank balances, inventory counts, leader election |
| **Sequential consistency** | All nodes see operations in the same order, but not necessarily real-time | Distributed locks, configuration stores |
| **Causal consistency** | Causally related operations are seen in order; concurrent ops may diverge | Comment threads, collaborative editing |
| **Eventual consistency** | All replicas converge given no new writes; reads may return stale data | DNS, shopping cart, social media likes |
| **Read-your-writes** | A client always sees its own writes | User profile updates, settings pages |

Most systems need **different models for different data**. Shopping carts can be eventually
consistent; checkout stock deduction must be linearisable.

### 2. Understand the CAP and PACELC trade-offs

**CAP theorem**: during a network partition you must choose between:
- **Consistency** (CP) — reject requests that might return stale data (ZooKeeper, etcd, HBase)
- **Availability** (AP) — return potentially stale data rather than refuse (Cassandra, CouchDB, DynamoDB with eventual consistency)

CAP is often misunderstood. It only applies *during a partition*. The practical question
is: **what does your system do when a partition occurs?**

**PACELC** is more useful day-to-day: even without a partition, there is a trade-off between:
- **Latency** — write to one node and acknowledge fast
- **Consistency** — wait for quorum before acknowledging

```
           No partition                  Partition
PACELC:   Latency  vs  Consistency     Availability  vs  Consistency

DynamoDB:     L           C                  A              C    → EL / PA
Spanner:      L           C                  A              C    → EC / PC
Cassandra:    L           C                  A              C    → EL / PA (tunable)
```

Document the choice explicitly in your architecture: "We accept replication lag on the
read path for user activity feeds (EL), but stock deduction is synchronous two-phase commit (EC)."

### 3. Choose a replication strategy

**Single-leader (primary/replica):**
- All writes go to one leader; replicas follow asynchronously or semi-synchronously.
- PostgreSQL streaming replication, MySQL binlog replication, MongoDB replica sets.
- Watch for: **replication lag** — a replica may be seconds behind the leader.

```sql
-- Prevent reading stale data on a PostgreSQL replica by routing
-- read-your-writes queries to the primary:
-- App code: use primary connection for writes + immediate subsequent reads;
-- use replica pool only for reads that tolerate lag (analytics, reports).

-- Detect lag programmatically:
SELECT EXTRACT(EPOCH FROM (now() - pg_last_xact_replay_timestamp()))::int AS lag_seconds;
-- Alert when this exceeds your SLA threshold (e.g., 30 s).
```

**Multi-leader:**
- Multiple nodes accept writes simultaneously. Used for geo-distributed writes (active-active
  across regions).
- Requires **conflict resolution** — see step 5.
- Avoid within a single datacenter; the complexity cost is rarely worth it.

**Leaderless (Dynamo-style):**
- Any node can accept a write. Reads and writes go to a quorum of nodes.
- Quorum condition: `W + R > N` (where N = replication factor, W = write quorum, R = read quorum)

```
N=3, W=2, R=2  →  W+R=4 > 3  →  at least one node overlaps  →  strong quorum
N=3, W=1, R=1  →  W+R=2 < 3  →  no overlap guaranteed  →  eventual consistency
N=3, W=3, R=1  →  high write durability, fast reads, slow writes
N=3, W=1, R=3  →  fast writes, slow reads, full read repair
```

Cassandra example — tunable per query:
```python
from cassandra import ConsistencyLevel
from cassandra.query import SimpleStatement

# Strong consistency (quorum read + quorum write)
stmt = SimpleStatement(
    "SELECT balance FROM accounts WHERE user_id = %s",
    consistency_level=ConsistencyLevel.QUORUM,
)
session.execute(stmt, [user_id])

# Fast eventual read (acceptable for non-critical data)
stmt = SimpleStatement(
    "SELECT activity_count FROM user_stats WHERE user_id = %s",
    consistency_level=ConsistencyLevel.ONE,
)
```

### 4. Choose the right database isolation level

Isolation levels control what concurrent transactions can see. Most engineers leave the
default without thinking about it — that is how subtle data corruption happens.

| Level | Prevents | Allows | Use when |
|-------|----------|--------|----------|
| **Read Uncommitted** | — | Dirty reads | Almost never |
| **Read Committed** (PG default) | Dirty reads | Non-repeatable reads, phantom reads | Most OLTP |
| **Repeatable Read** (MySQL InnoDB default) | Dirty + non-repeatable reads | Phantom reads | Reports that scan ranges |
| **Serialisable** | All anomalies | Nothing | Financial ledgers, inventory |

```sql
-- Detect a lost-update anomaly at Read Committed:
-- Thread A reads balance = 100
-- Thread B reads balance = 100
-- Thread A writes balance = 90  (deducted 10)
-- Thread B writes balance = 80  (deducted 20) — A's deduction is lost

-- Fix with SELECT FOR UPDATE (pessimistic locking):
BEGIN;
SELECT balance FROM accounts WHERE id = $1 FOR UPDATE;
UPDATE accounts SET balance = balance - $2 WHERE id = $1;
COMMIT;

-- Or with optimistic locking (add a version column):
UPDATE accounts
SET balance = balance - $2, version = version + 1
WHERE id = $1 AND version = $3;
-- If rows_affected = 0, another transaction won the race → retry
```

### 5. Detect and resolve conflicts

**Last-write-wins (LWW):** keep the write with the highest timestamp. Simple but lossy —
concurrent writes from clocks that drift will silently drop data.

```python
# LWW — use only when losing concurrent writes is acceptable (e.g., user avatar)
def resolve_lww(local: Record, remote: Record) -> Record:
    return local if local.updated_at >= remote.updated_at else remote
```

**Vector clocks / version vectors:** track causal history per replica. Detect concurrent
writes without a global clock.

```python
# Simplified vector clock comparison
def compare(vc_a: dict[str, int], vc_b: dict[str, int]) -> str:
    nodes = set(vc_a) | set(vc_b)
    a_gte = all(vc_a.get(n, 0) >= vc_b.get(n, 0) for n in nodes)
    b_gte = all(vc_b.get(n, 0) >= vc_a.get(n, 0) for n in nodes)
    if a_gte and b_gte: return "equal"
    if a_gte:           return "a_dominates"   # a is causally after b
    if b_gte:           return "b_dominates"
    return "concurrent"                          # conflict — needs resolution
```

**CRDTs (Conflict-free Replicated Data Types):** data structures that merge automatically
without coordination. Use when you need concurrent writes that must never conflict.

```ts
// Grow-only counter (G-Counter) — simplest CRDT
// Each node increments only its own slot; merge takes the max per slot
type GCounter = Record<string, number>;   // { "node-1": 5, "node-2": 3 }

function increment(counter: GCounter, nodeId: string): GCounter {
  return { ...counter, [nodeId]: (counter[nodeId] ?? 0) + 1 };
}

function merge(a: GCounter, b: GCounter): GCounter {
  const nodes = new Set([...Object.keys(a), ...Object.keys(b)]);
  const merged: GCounter = {};
  for (const n of nodes) merged[n] = Math.max(a[n] ?? 0, b[n] ?? 0);
  return merged;
}

function value(counter: GCounter): number {
  return Object.values(counter).reduce((s, v) => s + v, 0);
}
```

CRDT-backed data types: G-Counter, PN-Counter, OR-Set, LWW-Register, RGA (for text).
Libraries: Automerge (JS), Yjs (JS), Riak (storage-level).

### 6. Prevent split-brain

Split-brain: two nodes believe they are the leader simultaneously and accept conflicting writes.

**Fencing tokens (STONITH pattern):**
```
1. Leader acquires lock with token T=42.
2. Leader is paused (GC, network blip).
3. Lock expires; new leader acquires lock with T=43.
4. Old leader resumes, tries to write with T=42.
5. Storage layer rejects any write with token < current max (42 < 43). ✓
```

```python
# Redis-backed fencing token (Redlock simplified — use a battle-tested lib in prod)
import redis, uuid

def acquire_lock(r: redis.Redis, resource: str, ttl_ms: int) -> str | None:
    token = str(uuid.uuid4())
    acquired = r.set(resource, token, px=ttl_ms, nx=True)
    return token if acquired else None

def release_lock(r: redis.Redis, resource: str, token: str) -> bool:
    script = """
    if redis.call("get", KEYS[1]) == ARGV[1] then
        return redis.call("del", KEYS[1])
    else
        return 0
    end
    """
    return bool(r.eval(script, 1, resource, token))
```

**Quorum-based leader election (etcd / ZooKeeper):**
```bash
# etcd — acquire a lease; only the holder can write under the key
etcdctl lease grant 30                          # 30-second TTL
etcdctl put --lease=<lease-id> /service/leader "node-1"
etcdctl lease keep-alive <lease-id> &           # heartbeat; stops on crash
```

**Epoch numbers:** every term/epoch is monotonically increasing. Nodes refuse messages
from a lower epoch. Used in Raft, Paxos, Kafka partition leadership.

### 7. Design for replication lag

Never assume replicas are up-to-date. Be explicit about where lag is acceptable.

```ts
// Route reads to primary when read-your-writes is required
class UserRepository {
  async update(userId: string, data: Partial<User>): Promise<User> {
    return this.primaryDb.user.update({ where: { id: userId }, data });
  }

  async findForOwner(userId: string): Promise<User | null> {
    // Owner reads their own profile — must use primary to see their own write
    return this.primaryDb.user.findUnique({ where: { id: userId } });
  }

  async findForPublic(userId: string): Promise<User | null> {
    // Public profile view — replica lag is acceptable
    return this.replicaDb.user.findUnique({ where: { id: userId } });
  }
}
```

### Rules

- Write down the consistency model and rationale in a comment or ADR before implementing.
  "We chose eventual consistency here because X" is essential for the next engineer.
- Never rely on wall-clock timestamps alone for ordering across nodes — clocks drift.
  Use logical clocks (Lamport timestamps, vector clocks) or a globally-ordered sequence
  (Postgres sequences on a single primary, Spanner TrueTime).
- Linearisability is expensive: it requires synchronous replication or consensus on every
  write. Only pay for it where the business actually requires it.
- Test failure scenarios explicitly: kill the primary, partition the network, inject a GC
  pause. Consistency bugs appear only under failure, not in happy-path tests.
- If you implement a distributed lock, add a fencing token. A lock without a token is not
  a lock — it is a suggestion.
- Prefer well-tested consensus implementations (etcd, ZooKeeper, CockroachDB) over
  building your own Raft or Paxos. The edge cases take years to discover and fix.
