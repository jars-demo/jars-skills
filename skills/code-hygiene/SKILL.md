---
name: code-hygiene
description: Audit and clean up code quality issues that accumulate over time — not bugs, but rot. Use when the user asks to clean up code, fix naming conventions, remove unused imports, remove dead code, fix inconsistent variable names, eliminate AI-generated boilerplate, remove vendor-generated noise, standardize casing (camelCase, snake_case, PascalCase), remove stale comments, fix magic numbers, or sweep a file or module for code quality issues before a release or review.
---

# Code hygiene

Hunt and eliminate the rot that accumulates in real codebases: wrong casing, dead imports,
stale comments, magic numbers, AI-generated filler, unused variables, inconsistent naming.
None of this is a bug — but all of it slows down every developer who reads the code after you.

## Ground rules

- **Read the project conventions first.** Check `CONTRIBUTING.md`, linter config
  (`.eslintrc`, `ruff.toml`, `.pylintrc`, `biome.json`), and the existing codebase style.
  The project's rules override everything in this skill.
- **No behaviour changes.** Renaming a variable, removing a dead import, and fixing a
  comment do not change what the code does. If you find a bug while cleaning, note it and
  fix it separately.
- **One concern per commit.** Don't mix naming fixes, dead code removal, and comment
  cleanup into one commit. Each is its own change with its own message.
- **Tests pass before and after.** Run the suite before touching anything. If tests are
  already failing, stop and report — don't clean a broken codebase.
- **Never remove code you don't understand.** If something looks unused but you can't
  trace every call site, flag it rather than delete it.
- **Never push, publish, or deploy** unless explicitly asked.

---

## Step 0: Establish baseline

```bash
# Tests green before you start?
pytest                    # Python
npm test -- --run         # JS/TS
go test ./...             # Go

# What does the linter already catch?
ruff check .              # Python
npx eslint src/           # JS/TS
npx biome check src/      # JS/TS (Biome)
```

If the linter already catches it, let the linter fix it — don't do it manually:

```bash
ruff check . --fix        # Python: auto-fix safe issues
npx eslint src/ --fix     # JS/TS: auto-fix
npx biome check src/ --write  # Biome: auto-fix
```

Only proceed manually for issues the linter doesn't catch. Record baseline test result.

---

## What to audit

### 1. Naming conventions

Consistent naming is the difference between code you can scan and code you have to decode.

| Language | Variables/functions | Classes | Constants | Files |
| --- | --- | --- | --- | --- |
| JavaScript / TypeScript | `camelCase` | `PascalCase` | `UPPER_SNAKE_CASE` | `kebab-case` or `camelCase` |
| Python | `snake_case` | `PascalCase` | `UPPER_SNAKE_CASE` | `snake_case` |
| Go | `camelCase` | `PascalCase` | `PascalCase` (exported) | `snake_case` |
| Rust | `snake_case` | `PascalCase` | `UPPER_SNAKE_CASE` | `snake_case` |

**Red flags to search for:**

```bash
# Mixed casing in Python (camelCase variables in a snake_case codebase)
grep -rn "[a-z][A-Z]" src/ --include="*.py" | grep -v "def \|class \|#"

# Single-letter variables outside of loops and math
grep -rn "\b[a-df-z]\b\s*=" src/ --include="*.ts"

# Vague names that carry no meaning
grep -rn "\bdata\b\|\binfo\b\|\btemp\b\|\bobj\b\|\bval\b\|\bres\b\|\bret\b" src/ --include="*.ts"
```

Fix them with your editor's rename refactor — not find-and-replace, which breaks partial
matches. In an agent context, use a semantic rename tool so all references update together.

**Good names say what a thing is, not what it contains:**

| Bad | Good | Why |
| --- | --- | --- |
| `data` | `invoicePayload` | Says what the data represents |
| `res` | `userResponse` | Says what the response is for |
| `temp` | `filteredOrders` | Says what it holds |
| `flag` | `isEmailVerified` | Booleans: `is`, `has`, `can`, `should` |
| `cb` | `onPaymentSuccess` | Callbacks named for their trigger |
| `arr` | `pendingInvoices` | Arrays named for their contents |
| `Manager` | `SessionCache` | Classes named for their role |
| `utils.ts` | `dateFormatters.ts` | Files named for what they contain |

---

### 2. Unused imports

Unused imports add noise to every file and slow down linters, bundlers, and readers.

```bash
# Python: ruff catches these
ruff check . --select F401

# TypeScript/JavaScript: ESLint with no-unused-vars / unused-imports plugin
npx eslint src/ --rule '{"no-unused-vars": "error"}'

# Go: the compiler enforces this — unused imports are a build error
go build ./...

# Find manually in TS/JS if no linter is set up
grep -rn "^import" src/ --include="*.ts" | grep -v "from"
```

Remove the import. If it was providing a side effect (e.g. `import './polyfill'`), add a
comment explaining why the side-effect-only import exists.

---

### 3. Dead code

Code that is defined but never called. Every dead function is a maintenance trap — future
developers read it, try to understand it, and wonder if removing it will break something.

```bash
# TypeScript: ts-prune finds unused exports
npx ts-prune

# Python: vulture finds dead code
pip install vulture
vulture src/

# Find functions defined but never called (rough grep — verify before deleting)
grep -rn "^def \|^function \|^const.*= (" src/ --include="*.py" -l | \
  xargs -I{} sh -c 'grep -oh "def \w\+" {} | awk "{print \$2}"'
```

Before deleting:
- Search all call sites including tests, config files, and dynamic invocations.
- Check if it's part of a public API or plugin interface — deletion is a breaking change.
- If unsure, add a `# TODO: verify unused before removal` comment and flag it in the PR
  rather than deleting blindly.

---

### 4. AI-generated and vendor-generated slop

AI coding tools and code generators produce working code — but they also produce patterns
that are wasteful, over-engineered, or stylistically inconsistent with the rest of the
codebase. Common signs:

**Unnecessary abstraction:**
```ts
// AI slop: a wrapper that does nothing
function getUserById(id: string) {
  return fetchUser(id);   // just call fetchUser directly
}
```

**Over-commented obvious code:**
```python
# Increment the counter by 1
counter += 1

# Return the result
return result
```

**Defensive guards on values that are always defined:**
```ts
if (user && user.id && user.id !== null && user.id !== undefined) {
  // user.id is typed as string — this is all noise
}
```

**Unused parameters left in from a template:**
```python
def process(data, config=None, options=None, verbose=False):
    # config, options, verbose never used in the body
    return transform(data)
```

**Generic error messages from scaffolding:**
```ts
throw new Error("An error occurred");   // tells the caller nothing
throw new Error("Something went wrong");
```

**What to do:**
- Remove the wrapper and call the underlying function directly.
- Delete comments that restate the code. Keep comments that explain *why*.
- Remove defensive guards that the type system already guarantees.
- Remove unused parameters — or add `_` prefix if the signature is required by an interface.
- Replace generic error messages with specific ones that include the value and context.

---

### 5. Stale comments and commented-out code

```bash
# Find commented-out code blocks (Python)
grep -rn "^#\s*[a-zA-Z_]*(" src/ --include="*.py"

# Find TODO/FIXME with no owner or ticket
grep -rn "TODO\|FIXME\|HACK\|XXX" src/
```

**Commented-out code:** delete it. Git has the history. Commented-out code confuses every
reader into wondering if it's intentional, in progress, or forgotten.

**Stale TODOs:** either fix the issue now, open a ticket and replace the comment with the
ticket number (`# TODO(PROJ-123): ...`), or delete it if the concern is no longer valid.

**Comments that restate the code:** delete them.

**Comments that explain *why*:** keep and improve them.

```python
# Bad — restates the code
# Get the user by id
user = db.get_user(user_id)

# Good — explains a non-obvious constraint
# Stripe requires idempotency keys scoped to a single payment attempt.
# Reusing a key from a failed attempt causes a 400.
key = f"{payment_id}-{attempt}"
```

---

### 6. Magic numbers and strings

A bare number or string in logic is a bug waiting to happen — no one knows what it means
or whether it's safe to change.

```python
# Bad
if retries > 3:
    ...
time.sleep(0.5)
if status == 2:
    ...

# Good
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 0.5
STATUS_ACTIVE = 2

if retries > MAX_RETRIES:
    ...
time.sleep(RETRY_DELAY_SECONDS)
if status == STATUS_ACTIVE:
    ...
```

Exception: `0`, `1`, `-1` in obvious mathematical context, and HTTP status codes with a
comment, are fine as-is. Don't over-extract.

---

### 7. Inconsistent code patterns

When different parts of the codebase do the same thing differently, pick the pattern the
majority uses and make it consistent.

```bash
# Mixed quote styles in Python (single vs double)
grep -rn "'" src/ --include="*.py" | wc -l
grep -rn '"' src/ --include="*.py" | wc -l

# Inconsistent error handling patterns
grep -rn "try:\|except Exception\|except:" src/ --include="*.py" | head -20

# Mixed async patterns in JS (callbacks vs promises vs async/await)
grep -rn "\.then(\|new Promise\|callback" src/ --include="*.ts"
```

Don't fix style inconsistencies by hand — configure the linter/formatter and let it run:

```bash
black src/          # Python formatting
prettier --write .  # JS/TS formatting
gofmt -w .         # Go formatting
```

---

## Workflow

### For a single file

1. Run the linter on the file and auto-fix what it catches.
2. Read the file top to bottom. Note every violation by category.
3. Fix in order: imports → dead code → naming → comments → magic numbers.
4. Run tests after each category. Commit each category separately.

### For a module or directory

1. Run the linter across the scope. Auto-fix safe issues.
2. Use `ts-prune` / `vulture` to find dead exports and functions.
3. Fix the easiest category first (unused imports) — it reduces noise for the rest.
4. Work file by file through naming, then dead code, then comments.
5. One commit per category across the module.

### For a pre-release sweep

1. Linter + formatter on the whole codebase.
2. `ts-prune` / `vulture` pass — flag, don't delete blindly.
3. Search for magic numbers in business logic.
4. Search for TODO/FIXME — triage each one.
5. Search for the vague name patterns above — spot check the worst offenders.
6. Verify tests still pass.
7. Report a summary: files touched, violations fixed, issues flagged for follow-up.

---

## Report format

```
## Hygiene sweep: <scope>  (<date>)

Auto-fixed by linter:
  - 14 unused imports (ruff F401)
  - 7 formatting issues (black)

Fixed manually:
  - 3 magic numbers extracted to constants (billing.py)
  - 5 vague variable names renamed (orders.py, users.py)
  - 11 stale comments removed across 4 files
  - 2 commented-out code blocks deleted

Flagged for follow-up (not deleted — need verification):
  - process_legacy_order() in orders.py — appears unused, but check background jobs
  - FEATURE_FLAG_V2 constant — no call sites found, may be read via getattr()

Tests: 94 passed, 0 failed. Exit 0.
```

---

## What this skill does NOT do

- Fix bugs or logic errors — that's `debug-session`.
- Restructure modules or split large files — that's `refactor`.
- Review a PR diff for correctness — that's `code-review`.
- Change public API signatures without confirmation.
- Delete code it can't fully trace.
