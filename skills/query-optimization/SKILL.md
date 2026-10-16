---
name: query-optimization
description: Diagnosing and fixing slow database queries: reads EXPLAIN ANALYZE output node by node, identifies sequential scans, cardinality misestimates, and bad join orders, creates the right index type (B-tree, partial, covering, GIN, BRIN), rewrites N+1s, correlated subqueries, implicit casts, and OFFSET pagination, and forces statistics refresh when the planner is wrong. Use when you want to optimize a slow query, read an EXPLAIN plan, add the right index, fix a sequential scan, fix N+1 queries, the query planner is wrong, reduce query time, fix a slow JOIN, or understand why a query is slow.
---

## query-optimization

Diagnose and fix slow queries systematically — read the plan before touching anything.

### 1. The diagnostic order

Never add an index or rewrite a query before reading the execution plan. The plan tells you
exactly what the engine is doing and why. Guessing wastes time and adds wrong indexes that
slow down writes.

```
1. Capture the slow query (slow query log, pg_stat_statements, Performance Schema)
2. Run EXPLAIN ANALYZE
3. Read the plan — find the most expensive node
4. Identify the cause (sequential scan, bad estimate, wrong join type)
5. Apply the smallest fix
6. Re-run EXPLAIN ANALYZE and measure the improvement
```

### 2. Read EXPLAIN ANALYZE (PostgreSQL)

```sql
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT o.id, o.total, u.email
FROM orders o
JOIN users u ON u.id = o.user_id
WHERE o.status = 'pending'
  AND o.created_at > now() - interval '7 days'
ORDER BY o.created_at DESC
LIMIT 50;
```

**What to look at, in order:**

```
Limit  (cost=1823.45..1823.58 rows=50 width=48)
       (actual time=312.4..312.5 rows=50 loops=1)
  ->  Sort  (cost=1823.45..1847.12 rows=9467 width=48)
            (actual time=312.3..312.4 rows=50 loops=1)
        Sort Key: o.created_at DESC
        Sort Method: top-N heapsort  Memory: 32kB
        ->  Hash Join  (cost=214.00..1594.31 rows=9467 width=48)
                       (actual time=8.2..298.1 rows=9423 loops=1)
              Hash Cond: (o.user_id = u.id)
              ->  Seq Scan on orders o                  ← ❌ sequential scan
                    (cost=0.00..1341.20 rows=9467 width=40)
                    (actual time=0.1..241.3 rows=9423 loops=1)
                    Filter: ((status = 'pending') AND (created_at > ...))
                    Rows Removed by Filter: 48211        ← ❌ 48k rows scanned, 9k kept
              ->  Hash  (cost=139.00..139.00 rows=6000 width=24)
                        (actual time=7.8..7.8 rows=6000 loops=1)
                    ->  Seq Scan on users u              ← acceptable — small table
```

**Key signals to find:**

| Signal | Meaning | Fix |
|--------|---------|-----|
| `Seq Scan` on a large table | No usable index | Add index on filter/join column |
| `rows=X` estimate far from `actual rows=Y` | Bad statistics | `ANALYZE table;` or partial index |
| `Rows Removed by Filter: N` large | Index exists but wrong columns | Composite or covering index |
| `cost` node much higher than siblings | Bottleneck node | Focus here |
| `loops=N` on inner node | Nested loop with N iterations | Hash join may be better; index the inner side |
| `Sort Method: external merge  Disk` | Sort spilled to disk | Increase `work_mem`; add index for sort order |
| `Hash Batches: N > 1` | Hash join spilled to disk | Increase `work_mem` |

**The most important comparison:**
```
estimated rows vs actual rows

Ratio > 10× means the planner had bad statistics.
The planner's cost model is only as good as its row estimates.
Fix estimates first — the wrong join order often corrects itself.
```

### 3. Read EXPLAIN for MySQL

```sql
EXPLAIN FORMAT=JSON
SELECT o.id, o.total, u.email
FROM orders o
JOIN users u ON u.id = o.user_id
WHERE o.status = 'pending'
  AND o.created_at > NOW() - INTERVAL 7 DAY
ORDER BY o.created_at DESC
LIMIT 50;
```

Key fields:
- `access_type`: `ALL` = full scan (bad), `ref` / `range` / `eq_ref` = index used (good)
- `rows`: estimated rows examined — large number with many filtered rows is the problem
- `Extra: Using filesort` — sort cannot use an index; add a covering index with the sort column
- `Extra: Using temporary` — intermediate result materialised to a temp table; often from GROUP BY / DISTINCT without an index

```sql
-- MySQL slow query log — enable temporarily to catch queries > 1 s
SET GLOBAL slow_query_log = 'ON';
SET GLOBAL long_query_time = 1;
SET GLOBAL slow_query_log_file = '/tmp/mysql-slow.log';

-- Or query the Performance Schema directly
SELECT digest_text, count_star, avg_timer_wait / 1e12 AS avg_sec
FROM performance_schema.events_statements_summary_by_digest
ORDER BY avg_timer_wait DESC
LIMIT 20;
```

### 4. Fix the right index

The choice of index type, column order, and inclusion matters more than simply "add an index."

**B-tree (default) — equality and range:**
```sql
-- Single column: equality filter
CREATE INDEX idx_orders_status ON orders (status);

-- Composite: always put equality columns first, then range/sort columns
-- Query: WHERE status = 'pending' AND created_at > x ORDER BY created_at
CREATE INDEX idx_orders_status_created ON orders (status, created_at DESC);
-- This index satisfies the filter AND eliminates the sort in one pass.

-- Covering index: include non-filter columns to avoid heap fetches
CREATE INDEX idx_orders_covering ON orders (status, created_at DESC)
  INCLUDE (total, user_id);   -- PostgreSQL 11+; MySQL: just add cols to index
-- Now the query can be answered entirely from the index — no table heap access.
```

**Partial index — index only the rows you query:**
```sql
-- If 95% of orders are 'completed' and you only ever query 'pending':
CREATE INDEX idx_orders_pending ON orders (created_at DESC)
  WHERE status = 'pending';
-- Much smaller index → faster scans, cheaper writes, fits in memory.
```

**Expression index — index a computed value:**
```sql
-- Query uses: WHERE lower(email) = lower($1)
-- ❌ full scan — the index on email doesn't help here
-- ✅ index the expression:
CREATE INDEX idx_users_email_lower ON users (lower(email));
```

**GIN index — full-text search and JSONB:**
```sql
-- Full-text search
CREATE INDEX idx_posts_search ON posts USING gin(to_tsvector('english', body));

-- JSONB containment queries (@>)
CREATE INDEX idx_events_payload ON events USING gin(payload jsonb_path_ops);
```

**BRIN index — very large, naturally ordered tables (append-only logs, time series):**
```sql
-- Orders inserted roughly in time order — BRIN is tiny vs B-tree
CREATE INDEX idx_events_created_brin ON events USING brin(created_at);
-- Use when: table is huge, inserted in order, queries always filter by range.
-- Do NOT use for random-access lookup patterns.
```

**Index column order rule:**
```
(equality cols) → (range col) → (sort col)

Query: WHERE tenant_id = $1 AND status = $2 AND created_at > $3 ORDER BY created_at
Index: (tenant_id, status, created_at)   ← exactly this order
```

### 5. Fix bad cardinality estimates

When `estimated rows` is far from `actual rows`, the planner makes poor join and scan choices.

```sql
-- Refresh statistics on a specific table (PostgreSQL)
ANALYZE orders;

-- More thorough — increase sample size for a skewed column
ALTER TABLE orders ALTER COLUMN status SET STATISTICS 500;  -- default is 100
ANALYZE orders;

-- Check current statistics
SELECT attname, n_distinct, correlation
FROM pg_stats
WHERE tablename = 'orders';
```

`n_distinct`: negative = fraction of total rows; positive = absolute count.
`correlation`: 1.0 = perfectly ordered on disk (index scan cheap); 0.0 = random (index scan expensive at high selectivity).

**Extended statistics for correlated columns (PostgreSQL 10+):**
```sql
-- Planner treats (status, region) as independent — but in reality
-- status='pending' almost always means region='us-east'. Tell the planner:
CREATE STATISTICS orders_status_region ON status, region FROM orders;
ANALYZE orders;
```

### 6. Rewrite pathological queries

**N+1 — replace per-row queries with a JOIN or IN:**
```sql
-- ❌ N+1: app fetches 1000 orders, then runs 1000 separate user queries
SELECT * FROM orders WHERE status = 'pending';
-- then for each order:
SELECT * FROM users WHERE id = $order.user_id;

-- ✅ Single JOIN
SELECT o.*, u.email, u.name
FROM orders o
JOIN users u ON u.id = o.user_id
WHERE o.status = 'pending';
```

**Correlated subquery — rewrite as JOIN or window function:**
```sql
-- ❌ Correlated subquery — re-executes for every row in orders
SELECT id, total,
  (SELECT sum(total) FROM orders o2 WHERE o2.user_id = o.user_id) AS user_lifetime_value
FROM orders o;

-- ✅ Derived table computed once
SELECT o.id, o.total, lt.lifetime
FROM orders o
JOIN (
  SELECT user_id, sum(total) AS lifetime
  FROM orders
  GROUP BY user_id
) lt ON lt.user_id = o.user_id;

-- ✅ Or window function (even cleaner)
SELECT id, total,
  sum(total) OVER (PARTITION BY user_id) AS user_lifetime_value
FROM orders;
```

**Implicit type cast killing an index:**
```sql
-- ❌ user_id is INTEGER but $1 is passed as TEXT → cast on every row, index unused
SELECT * FROM orders WHERE user_id = '12345';

-- ✅ Match the type exactly
SELECT * FROM orders WHERE user_id = 12345;

-- ❌ Function on indexed column — index on created_at is ignored
SELECT * FROM orders WHERE date_trunc('day', created_at) = '2026-01-15';

-- ✅ Rewrite as a range — index on created_at is used
SELECT * FROM orders WHERE created_at >= '2026-01-15' AND created_at < '2026-01-16';
```

**OR across columns preventing index use:**
```sql
-- ❌ Planner often falls back to seq scan for OR across different columns
SELECT * FROM users WHERE email = $1 OR phone = $1;

-- ✅ UNION ALL — each branch uses its own index
SELECT * FROM users WHERE email = $1
UNION ALL
SELECT * FROM users WHERE phone = $1 AND email != $1;
```

**Pagination with OFFSET — degrades at high page numbers:**
```sql
-- ❌ OFFSET 10000 scans and discards 10,000 rows
SELECT * FROM orders ORDER BY created_at DESC LIMIT 20 OFFSET 10000;

-- ✅ Keyset (cursor) pagination — O(1) regardless of page depth
SELECT * FROM orders
WHERE created_at < $last_seen_created_at
   OR (created_at = $last_seen_created_at AND id < $last_seen_id)
ORDER BY created_at DESC, id DESC
LIMIT 20;
```

### 7. Tune work_mem for sort and hash operations

```sql
-- Check if sorts are spilling to disk (look for "external merge")
EXPLAIN (ANALYZE, BUFFERS) SELECT ... ORDER BY ...;

-- Increase work_mem for the current session only (not global — it multiplies per sort node)
SET work_mem = '64MB';
EXPLAIN (ANALYZE, BUFFERS) SELECT ... ORDER BY ...;
-- If "external merge" disappears → the query benefits from more work_mem
-- Set it per connection or per query, not globally, unless you've done the math:
-- global work_mem × max_connections × sort nodes per query = RAM budget
```

### 8. Identify slow queries in production without guessing

```sql
-- PostgreSQL: pg_stat_statements — top queries by total time
SELECT
  left(query, 80)                                AS query_snippet,
  calls,
  round(total_exec_time::numeric / 1000, 2)     AS total_sec,
  round(mean_exec_time::numeric, 2)              AS mean_ms,
  round(stddev_exec_time::numeric, 2)            AS stddev_ms,
  rows
FROM pg_stat_statements
ORDER BY total_exec_time DESC
LIMIT 20;

-- Reset after a deploy to get a clean baseline
SELECT pg_stat_statements_reset();
```

```sql
-- Find tables with sequential scans that have indexes available
-- (high seq_scan + high seq_tup_read = missing index)
SELECT relname, seq_scan, seq_tup_read, idx_scan,
       round(seq_tup_read::numeric / NULLIF(seq_scan,0)) AS avg_rows_per_seqscan
FROM pg_stat_user_tables
WHERE seq_scan > 100
ORDER BY seq_tup_read DESC
LIMIT 20;
```

### Rules

- Read the plan before writing any fix. Every other step depends on it.
- Measure after every change with the same `EXPLAIN ANALYZE`. A change that looks right
  can make things worse if it shifts the bottleneck elsewhere.
- Never add an index "just in case" — every index slows down writes and uses memory.
  Add it only when the plan shows it will be used and the query is actually slow in production.
- Match data types exactly in query parameters. A single implicit cast silently disables
  the index on that column.
- `ANALYZE` the table before concluding the planner is wrong. Stale statistics cause most
  bad plans.
- `work_mem` changes must be sized against `max_connections` — multiplying per connection
  can OOM the database server.
- Fixing the query is always better than throwing hardware at it. A missing index or a
  correlated subquery rewrite can give 100× improvement; a larger server gives 2–4×.
