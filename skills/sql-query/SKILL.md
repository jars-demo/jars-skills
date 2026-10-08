---
name: sql-query
description: Write safe, readable, and performant SQL. Use when the user asks to write a query, optimise a slow query, add an index, design a schema, review SQL for correctness or injection risk, or translate application logic into SQL.
---

# SQL query

Write SQL that is correct first, readable second, and fast third — in that order. A clever
query that returns wrong results or opens an injection hole is worse than no query at all.

## Ground rules

- **Never interpolate user input into SQL strings.** Always use parameterised queries or
  prepared statements. No exceptions.
- **Read the schema before writing a query.** Assumptions about column types, nullability,
  and indexes cause subtle bugs. Read the migration files or `DESCRIBE`/`\d` output first.
- **Correctness before performance.** Get the right rows first, then optimise.
- **Explain your `JOIN` logic.** A silent Cartesian product from a missing `ON` clause is a
  disaster. State which column links the tables.
- **Never `SELECT *` in application code.** Name the columns you need. Wildcards break when
  the schema changes.

## Workflow

### 1. Understand the schema

```sql
-- PostgreSQL
\d table_name
SELECT column_name, data_type, is_nullable FROM information_schema.columns
WHERE table_name = 'your_table';

-- MySQL / MariaDB
DESCRIBE table_name;
SHOW CREATE TABLE table_name;

-- SQLite
PRAGMA table_info(table_name);
```

Also check:

```sql
-- What indexes exist?
-- PostgreSQL
\di table_name*
SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'your_table';

-- MySQL
SHOW INDEX FROM table_name;
```

If migration files exist, read the most recent ones:

```bash
ls -t migrations/ | head -10
```

### 2. Write parameterised queries

Never do this:

```python
# WRONG — SQL injection
query = f"SELECT * FROM users WHERE email = '{email}'"
```

Always do this:

```python
# Correct — parameterised
cursor.execute("SELECT id, name FROM users WHERE email = %s", (email,))

# SQLAlchemy ORM
user = session.query(User).filter(User.email == email).first()
```

```javascript
// node-postgres (pg)
const { rows } = await pool.query(
  'SELECT id, name FROM users WHERE email = $1',
  [email]
);

// Prisma — always parameterised automatically
const user = await prisma.user.findUnique({ where: { email } });
```

```go
// database/sql
row := db.QueryRowContext(ctx, "SELECT id, name FROM users WHERE email = ?", email)
```

### 3. Structure complex queries for readability

Use CTEs for multi-step logic. A long chain of subqueries is harder to audit:

```sql
WITH active_orders AS (
    SELECT id, user_id, total_amount
    FROM orders
    WHERE status = 'active'
      AND created_at >= NOW() - INTERVAL '30 days'
),
order_totals AS (
    SELECT user_id,
           COUNT(*)            AS order_count,
           SUM(total_amount)   AS lifetime_value
    FROM active_orders
    GROUP BY user_id
)
SELECT u.id,
       u.email,
       ot.order_count,
       ot.lifetime_value
FROM users u
JOIN order_totals ot ON ot.user_id = u.id
WHERE ot.lifetime_value > 100
ORDER BY ot.lifetime_value DESC;
```

Formatting rules:
- Keywords uppercase: `SELECT`, `FROM`, `WHERE`, `JOIN`, `ON`, `GROUP BY`.
- One clause per line; indent the clause contents.
- Alias every table in a multi-table query.
- Qualify every column with its table alias when more than one table is in scope.

### 4. Choose the right `JOIN`

| Join type | Use when |
| --- | --- |
| `INNER JOIN` | You only want rows where the relationship exists on both sides |
| `LEFT JOIN` | You want all rows from the left table, with NULLs when no match |
| `RIGHT JOIN` | Rarely needed; rewrite as a `LEFT JOIN` with tables swapped |
| `FULL OUTER JOIN` | You want all rows from both tables, with NULLs on either side |
| `CROSS JOIN` | Intentional Cartesian product (almost never what you want) |

Always write an explicit `ON` condition. A `JOIN` without `ON` (or with a stray comma) is a
Cartesian product that multiplies row counts silently.

### 5. Avoid common correctness traps

**NULL comparisons**

```sql
-- WRONG: NULL = NULL is never true
WHERE deleted_at = NULL

-- Correct
WHERE deleted_at IS NULL
WHERE deleted_at IS NOT NULL
```

**Aggregation without the right GROUP BY**

```sql
-- WRONG: orders column not in GROUP BY and not aggregated
SELECT user_id, order_id, COUNT(*) FROM orders GROUP BY user_id;

-- Correct: include every non-aggregated column
SELECT user_id, COUNT(*) AS order_count FROM orders GROUP BY user_id;
```

**`HAVING` vs `WHERE`**

- `WHERE` filters rows before aggregation.
- `HAVING` filters groups after aggregation.
- Never use `HAVING` where `WHERE` would do — it forces the database to aggregate all rows first.

**Date arithmetic**

```sql
-- PostgreSQL: last 7 days
WHERE created_at >= NOW() - INTERVAL '7 days'

-- MySQL
WHERE created_at >= NOW() - INTERVAL 7 DAY

-- SQLite
WHERE created_at >= datetime('now', '-7 days')
```

**Pagination**

```sql
-- Offset-based (simple but slow on large offsets)
SELECT id, title FROM posts ORDER BY created_at DESC LIMIT 20 OFFSET 40;

-- Cursor-based (fast at any depth)
SELECT id, title FROM posts
WHERE created_at < :last_seen_cursor
ORDER BY created_at DESC
LIMIT 20;
```

Use cursor-based pagination when the table is large or the user could page deep.

### 6. Check the query plan before shipping a slow query

```sql
-- PostgreSQL
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT ...;

-- MySQL
EXPLAIN SELECT ...;

-- SQLite
EXPLAIN QUERY PLAN SELECT ...;
```

Red flags in the plan:
- `Seq Scan` on a large table — likely needs an index.
- `Hash Join` or `Nested Loop` on millions of rows — check the join columns are indexed.
- `Sort` on a large dataset — check if an index can satisfy the `ORDER BY`.

### 7. Add indexes correctly

Create an index when:
- A column appears in `WHERE`, `JOIN ON`, or `ORDER BY` on a frequently-run query against a
  large table, and the query plan shows a sequential scan.

```sql
-- Single column
CREATE INDEX CONCURRENTLY idx_orders_user_id ON orders (user_id);

-- Composite: put the equality column(s) first, range/sort column last
CREATE INDEX CONCURRENTLY idx_orders_user_status ON orders (user_id, status);

-- Partial index (only index the rows you query)
CREATE INDEX CONCURRENTLY idx_orders_active ON orders (created_at)
WHERE status = 'active';
```

Rules:
- Use `CONCURRENTLY` in PostgreSQL so the index builds without locking the table.
- Every index slows down writes slightly and uses disk space. Only add indexes that have a
  matching query to justify them.
- Never add an index to fix a one-time query. Index the column, not the query.
- Do not index low-cardinality columns (boolean flags, small enums) unless combined with a
  high-cardinality column in a composite.

### 8. Schema design notes

When asked to write a migration or design a table:

- Use surrogate primary keys (`id BIGSERIAL` / `id BIGINT AUTO_INCREMENT` / `id INTEGER PRIMARY KEY` in SQLite).
- Store timestamps in UTC. Use `TIMESTAMPTZ` in PostgreSQL; `DATETIME` in MySQL.
- Mark columns `NOT NULL` by default. Add `NULL` only when "no value" is a valid business state.
- Use `TEXT` (PostgreSQL) or `VARCHAR(n)` (MySQL) for strings; only add a length constraint when
  the business rule requires one.
- Keep foreign keys explicit: `user_id BIGINT NOT NULL REFERENCES users(id)`.
- Never store delimited lists in a single column. Normalise.

### 9. Report

When handing back a query, include:

- The query, formatted.
- A brief explanation of what it does and why the `JOIN` / `WHERE` logic is correct.
- Any indexes it relies on (and whether they exist or need to be created).
- The `EXPLAIN` output or a summary if you ran it.
- Any assumptions you made about the schema or data distribution.
