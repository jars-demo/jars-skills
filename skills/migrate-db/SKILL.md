---
name: migrate-db
description: Write, review, and run database migrations safely. Use when the user asks to add a migration, rename a column, drop a table, change a schema, run migrations, roll back a migration, write a zero-downtime schema change, or fix a failed migration. Never runs destructive migrations without confirmation. Always reads the current schema before writing a migration.
---

# Database migrations

Write migrations that can be applied and rolled back cleanly, never destroy data without
a deliberate choice, and work in production without taking the site down.

## Ground rules

- **Read the current schema before writing a migration.** Never guess column names, types,
  or constraints.
- **Every migration needs an `up` and a `down`.** The rollback must actually undo the change.
  If a rollback is genuinely impossible (e.g. dropping a column with data), say so and make
  the user confirm before proceeding.
- **Never drop a column or table in the same migration that stops using it.** Data must
  stop being written before it can be dropped. Use the expand/contract pattern.
- **Never run a migration in production without confirmation.** Show the SQL first.
- **Prefer additive changes.** Adding columns and tables is safe. Removing and renaming are
  destructive — treat them with more caution.

---

## Step 0: Read the current schema

```bash
# PostgreSQL
psql $DATABASE_URL -c "\d+ table_name"
psql $DATABASE_URL -c "\dt"                   # list all tables

# MySQL / MariaDB
mysql -e "DESCRIBE table_name"
mysql -e "SHOW TABLES"

# SQLite
sqlite3 db.sqlite3 ".schema table_name"

# From migration files — read the last few to understand the current state
ls db/migrations/ | tail -5        # Rails / generic
ls migrations/ | tail -5           # many ORMs
ls alembic/versions/ | tail -5     # Python / SQLAlchemy
```

Also check the ORM model definitions — they're often the authoritative source:

```bash
cat app/models/user.py
cat prisma/schema.prisma
cat src/entities/User.ts
```

---

## Writing migrations

### Naming

Use a timestamp prefix and a descriptive name. The name must say what changes:

```
20240115_143000_add_email_verified_to_users.sql
0042_add_index_on_orders_user_id.py
1705329600_rename_fullname_to_full_name.ts
```

Never: `migration.sql`, `fix.py`, `update_table.ts`.

### Adding a column

```sql
-- up
ALTER TABLE users ADD COLUMN email_verified BOOLEAN NOT NULL DEFAULT false;

-- down
ALTER TABLE users DROP COLUMN email_verified;
```

For large tables in production, adding a column with a `DEFAULT` rewrites the table in
older Postgres (< 11) and MySQL (< 8.0). In modern versions it's instant. Check the
version before writing the migration.

### Adding a NOT NULL column to an existing table

Direct `ADD COLUMN col NOT NULL` fails if the table has rows and there's no default.
The safe sequence:

```sql
-- Step 1: add nullable
ALTER TABLE users ADD COLUMN phone VARCHAR(20);

-- Step 2: backfill (do this in batches on large tables)
UPDATE users SET phone = '' WHERE phone IS NULL;

-- Step 3: add the constraint
ALTER TABLE users ALTER COLUMN phone SET NOT NULL;
```

### Renaming a column (zero-downtime)

Never rename in one step in a live system. The app will be reading the old name after
the migration runs.

**Expand phase** (deploy first, before the migration):
```sql
-- Add the new column, keep the old one
ALTER TABLE users ADD COLUMN full_name VARCHAR(255);
UPDATE users SET full_name = fullname;
```

**Dual-write phase** (app writes to both columns):
- Deploy app code that writes both `fullname` and `full_name`
- Keep reading from `fullname` for now

**Contract phase** (after the new column is proven):
```sql
-- Drop the old column once no code references it
ALTER TABLE users DROP COLUMN fullname;
```

### Adding an index

Adding an index locks the table in standard SQL. Use `CONCURRENTLY` in Postgres to avoid
blocking reads and writes:

```sql
-- Postgres — non-blocking
CREATE INDEX CONCURRENTLY idx_orders_user_id ON orders (user_id);

-- down
DROP INDEX CONCURRENTLY IF EXISTS idx_orders_user_id;
```

`CONCURRENTLY` cannot run inside a transaction. If your migration tool wraps everything in
a transaction, disable that for this migration specifically.

### Dropping a column or table

Confirm with the user before writing a destructive migration. Show what data will be lost.

```sql
-- Only after confirming no code reads or writes this column
-- up
ALTER TABLE users DROP COLUMN legacy_token;

-- down — data is gone, rollback cannot restore it
-- ALTER TABLE users ADD COLUMN legacy_token TEXT;   -- column exists but data is lost
```

Document in the migration comment that the `down` is lossy.

---

## ORM-specific patterns

### Prisma (TypeScript)

```bash
# Create a migration from schema changes
npx prisma migrate dev --name add_email_verified_to_users

# Preview SQL without applying
npx prisma migrate dev --create-only

# Apply in production (never runs dev-only seed)
npx prisma migrate deploy

# Roll back: Prisma has no built-in rollback — write a new migration that undoes the change
```

Read `prisma/schema.prisma` before editing. Run `npx prisma validate` after editing.

### Alembic (Python / SQLAlchemy)

```bash
# Auto-generate from model changes
alembic revision --autogenerate -m "add email_verified to users"

# Always review the generated file — autogenerate misses some changes
cat alembic/versions/<revision>.py

# Apply
alembic upgrade head

# Roll back one step
alembic downgrade -1

# Roll back to a specific revision
alembic downgrade <revision>
```

### ActiveRecord (Rails)

```bash
rails generate migration AddEmailVerifiedToUsers email_verified:boolean
# Edit the generated file to add default: false, null: false

rails db:migrate
rails db:rollback STEP=1   # undo last migration
rails db:migrate:status    # see which migrations have run
```

### Flyway / Liquibase (Java)

```bash
# Flyway — naming: V{version}__{description}.sql
# V20240115143000__add_email_verified_to_users.sql

mvn flyway:migrate
mvn flyway:info       # show migration status
# No built-in rollback in community edition — write a new migration

# Liquibase — XML or YAML changesets with rollback blocks
liquibase update
liquibase rollbackCount 1
```

---

## Before running in production

1. **Show the SQL.** Generate and display the exact statements before running:
   ```bash
   npx prisma migrate dev --create-only   # Prisma
   alembic upgrade head --sql             # Alembic — dry-run SQL output
   rails db:migrate:status                # Rails — see pending
   ```

2. **Estimate the impact.** For large tables, an `ALTER TABLE` or backfill can take
   minutes and lock the table. Check the row count:
   ```sql
   SELECT COUNT(*) FROM orders;
   SELECT pg_size_pretty(pg_total_relation_size('orders'));
   ```

3. **Test the rollback.** Run `down` on a staging database before deploying.

4. **Back up first.** For destructive migrations, confirm a backup exists before running.

5. **Run with `--dry-run` or equivalent** if the tool supports it.

---

## Fixing a failed migration

```bash
# 1. Find out what state the database is in
alembic current          # Alembic
rails db:migrate:status  # Rails
npx prisma migrate status  # Prisma

# 2. Check if the partial migration left the schema in an inconsistent state
psql $DATABASE_URL -c "\d+ affected_table"

# 3. If the migration ran partially:
#    - Manually revert the changes that did apply
#    - Mark the migration as not run in the migration table
#    - Fix the migration file
#    - Re-run

# Alembic: stamp to a specific revision without running migrations
alembic stamp <previous_revision>

# Rails: delete the row from schema_migrations
rails db:environment:set RAILS_ENV=development
# Then manually remove the broken migration's timestamp from schema_migrations
```

---

## Checklist

- [ ] Current schema read before writing the migration
- [ ] Migration has both `up` (apply) and `down` (rollback)
- [ ] SQL shown and confirmed before running against production
- [ ] Destructive changes (DROP COLUMN, DROP TABLE) confirmed by user
- [ ] Large-table `ALTER TABLE` uses `CONCURRENTLY` or equivalent to avoid locks
- [ ] Column rename uses expand/contract pattern, not a single rename
- [ ] `NOT NULL` column added in steps: add nullable → backfill → add constraint
- [ ] Rollback tested on staging
- [ ] Migration name is timestamped and descriptive
