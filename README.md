<p align="center">
  <img src="assets/logo-800.png" alt="jars-skills" width="420" />
</p>

<p align="center">
  <a href="https://skills.jishanahmed.in">skills.jishanahmed.in</a>
</p>

# jars-skills

The agent skills I use most in my day-to-day work, shared in case they help you too.

I'm Jishanahmed AR Shaikh (Mr. JARS). I build and contribute to open source with coding agents
most days, and when I notice I'm explaining the same workflow to an agent again and again, I
write it down here as a skill.

Each skill is one folder with a `SKILL.md`: a short playbook that teaches an agent to do one job
the way I do it. They follow the [Agent Skills](https://agentskills.io) format, so they work in
Claude Code, Cursor, GitHub Copilot, Codex, Gemini CLI and other agents that read it.

I add them one at a time, aiming for one a day, and only after I've used the workflow for real.

## Install

**Claude Code** (plugin marketplace):

```
/plugin marketplace add jars-demo/jars-skills
/plugin install jars-skills@jars-skills
```

Or in one step (Claude Code 2.1.275+): `/plugin install jars-skills --marketplace jars-demo/jars-skills`.

Skills then load on their own when a task matches, or run one directly, e.g.
`/jars-skills:commit-style`. Update later with `/plugin marketplace update jars-skills`.

**Any agent** (via the [skills CLI](https://skills.sh)):

```bash
npx skills add jars-demo/jars-skills                       # pick from the list
npx skills add jars-demo/jars-skills --skill commit-style  # just one
```

**By hand:** copy a folder from `skills/` into your agent's skills directory, for example
`~/.claude/skills/commit-style/`.

## Skills

| # | Skill | Use it when |
| --- | --- | --- |
| 39 | [env-config](skills/env-config/SKILL.md) | Designing a typed, validated configuration system: centralises all env var reads into one config module, validates and fails fast at startup with a clear error, distinguishes secrets from plain config, maintains a .env.example with every key documented, and prevents os.environ / process.env scattered across the codebase. |
| 38 | [code-structure](skills/code-structure/SKILL.md) | Structuring and naming a codebase for long-term navigability: enforces a 696-line file ceiling, splits files by single responsibility, applies snake_case / PascalCase / SCREAMING_SNAKE consistently, wires structured logging with full error context at every boundary, adds file-level navigation headers, and scaffolds a clean folder hierarchy where every directory has exactly one job. |
| 37 | [concurrency-and-locking](skills/concurrency-and-locking/SKILL.md) | Identifying and fixing race conditions, deadlocks, and concurrency bugs: establishes happens-before relationships, chooses the right primitive (mutex, rwlock, atomic, channel), detects and breaks deadlock cycles with lock ordering, fixes TOCTOU races, uses CAS loops and copy-on-write atomics, pads to cache lines to eliminate false sharing, and runs the race detector. |
| 36 | [query-optimization](skills/query-optimization/SKILL.md) | Diagnosing and fixing slow database queries: reads EXPLAIN ANALYZE output node by node, identifies sequential scans, cardinality misestimates, and bad join orders, creates the right index type (B-tree, partial, covering, GIN, BRIN), rewrites N+1s, correlated subqueries, implicit casts, and OFFSET pagination, and forces statistics refresh when the planner is wrong. |
| 35 | [capacity-planning](skills/capacity-planning/SKILL.md) | Modelling load, projecting resource ceilings, and deciding when to scale: derives RPS and data-volume limits from first principles, identifies the bottleneck resource (CPU, memory, DB connections, I/O) with back-of-envelope math, calculates time-to-saturation, designs load tests that reflect real traffic shape, applies Little's Law to size thread and connection pools, and translates findings into concrete scaling decisions. |
| 34 | [memory-and-allocations](skills/memory-and-allocations/SKILL.md) | Profiling and fixing memory leaks, excessive heap allocations, and GC pressure: captures heap snapshots and allocation timelines, identifies retaining paths and dominator objects, fixes event-listener accumulation, closure captures, unbounded caches, and goroutine leaks, and applies the same workflow across Node.js, Python, Go, and JVM runtimes. |
| 33 | [data-consistency](skills/data-consistency/SKILL.md) | Reasoning about and implementing data consistency in distributed systems: picks the right consistency model (linearisable, causal, eventual), chooses a replication strategy, applies the right isolation level, resolves conflicts with LWW/vector clocks/CRDTs, prevents split-brain with fencing tokens, and makes deliberate CAP and PACELC trade-offs. |
| 32 | [distributed-tracing](skills/distributed-tracing/SKILL.md) | Instrumenting services with distributed tracing end-to-end: initialises the OpenTelemetry SDK before any other import, propagates W3C TraceContext across HTTP calls, message queues, and database queries, adds meaningful span attributes, configures head-based and tail-based sampling, exports to Jaeger or Tempo, and correlates traces with logs to diagnose latency across service boundaries. |
| 31 | [background-jobs](skills/background-jobs/SKILL.md) | Designing, implementing, and operating background job queues: picks the right backend (BullMQ, Celery, Sidekiq, pg-boss), makes jobs idempotent and safe to retry, sets concurrency and back-off correctly, handles dead-letter queues, and monitors job throughput and lag. |
| 30 | [feature-flags](skills/feature-flags/SKILL.md) | Implementing, gating, and cleaning up feature flags: picks the right flag type (boolean, percentage rollout, user-targeted), wraps the SDK in a thin abstraction, gates new code without coupling business logic to the flag system, and removes stale flags safely after full rollout. |
| 29 | [secrets-audit](skills/secrets-audit/SKILL.md) | Scanning, detecting, and remediating accidentally committed secrets: runs gitleaks or trufflehog against the repo history, triages real findings from false positives, rotates the exposed credential immediately, rewrites history only when safe, and adds pre-commit hooks and CI checks to prevent recurrence. |
| 28 | [monitoring](skills/monitoring/SKILL.md) | Adding application monitoring, metrics, and alerting: instruments the app with Prometheus/OpenTelemetry, exposes `/health` and `/metrics` endpoints, defines alert rules for error rate and latency p99, wires up a Grafana dashboard, and never leaks internal topology through public probes. |
| 27 | [websockets](skills/websockets/SKILL.md) | Implementing WebSocket connections for real-time features: authenticates on the upgrade handshake, validates all incoming messages, uses Socket.IO rooms for targeted delivery, scales across instances with the Redis adapter, and handles reconnection and disconnect cleanup correctly. |
| 26 | [rate-limiting](skills/rate-limiting/SKILL.md) | Adding rate limiting to protect APIs from abuse and brute-force attacks: picks the right algorithm (sliding window, token bucket), scopes limits to user ID or IP, wires up Redis-backed counters, returns `429` with `Retry-After`, covers nginx config, and never limits health check endpoints. |
| 25 | [error-handling](skills/error-handling/SKILL.md) | Adding and improving error handling: defines a custom error class hierarchy, adds a global handler that never leaks stack traces, returns consistent error response shapes, wraps async handlers, eliminates swallowed errors, and distinguishes operational from programmer errors. |
| 24 | [caching](skills/caching/SKILL.md) | Adding caching to reduce latency and database load: picks the right strategy (cache-aside, write-through), designs scoped cache keys, chooses TTLs based on data freshness needs, invalidates on mutation, sets HTTP cache headers, prevents stampedes, and avoids stale-data bugs. |
| 23 | [auth](skills/auth/SKILL.md) | Implementing and reviewing authentication and authorization: hashes passwords with bcrypt/argon2, issues and verifies JWTs with algorithm pinning, sets up session cookies correctly, protects routes with middleware, checks resource ownership to prevent IDOR, and flags common vulnerabilities. |
| 22 | [logging](skills/logging/SKILL.md) | Adding and improving structured logging: picks the right level, replaces console.log with pino/structlog/slog, adds request middleware with trace IDs, logs errors at the handling boundary, redacts secrets and PII, and outputs JSON for log aggregators. |
| 21 | [migrate-db](skills/migrate-db/SKILL.md) | Writing and running database migrations safely: reads the current schema first, generates up/down migrations, uses expand/contract for zero-downtime renames, handles NOT NULL columns and large-table index creation without locks, and never runs destructive changes without confirmation. |
| 20 | [accessibility](skills/accessibility/SKILL.md) | Auditing and fixing web accessibility issues to meet WCAG 2.1 AA: replaces non-semantic elements, adds ARIA labels and live regions, fixes keyboard navigation and focus traps, checks color contrast, makes forms and modals screen-reader friendly, and runs axe-cli to verify. |
| 19 | [openapi](skills/openapi/SKILL.md) | Writing, validating, and maintaining OpenAPI 3.1 specs: reads route handlers before writing schemas, defines parameters/request bodies/responses correctly, reuses components, adds real examples, validates with Spectral, and keeps the spec in sync with code via generation or drift detection in CI. |
| 18 | [perf-profile](skills/perf-profile/SKILL.md) | Profiling and fixing performance bottlenecks: establishes a baseline metric, uses the right profiler for the stack (Node.js, Python, Go, Java), finds slow queries with EXPLAIN, fixes N+1s and sequential I/O, measures the improvement — never optimises without data. |
| 17 | [ci-cd](skills/ci-cd/SKILL.md) | Writing, reviewing, and fixing CI/CD pipelines for GitHub Actions and GitLab CI: sets up build, test, and deploy jobs, wires up secrets safely, fixes failing pipelines, caches dependencies correctly, and never deploys without being asked. |
| 16 | [code-hygiene](skills/code-hygiene/SKILL.md) | Auditing and cleaning up code rot: fixes naming conventions (camelCase, snake_case, PascalCase), removes unused imports and dead code, eliminates AI-generated boilerplate and stale comments, extracts magic numbers, and standardizes inconsistent patterns — without changing behaviour. |
| 15 | [docker](skills/docker/SKILL.md) | Writing, reviewing, and fixing Dockerfiles and Compose files: picks the right base image, sets up multi-stage builds, fixes layer caching, reduces image size, adds healthchecks, avoids running as root, and never leaks secrets into the image. |
| 14 | [tokenjars](skills/tokenjars/SKILL.md) | Reducing unnecessary token consumption in AI coding-agent sessions: cuts verbose output, redundant tool calls, and repeated file reads while preserving technical accuracy, implementation quality, and all the evidence needed to diagnose and verify work. Use when a session is growing expensive, an agent is repeating itself, or you want concise, efficient engineering communication. |
| 13 | [debug-infra-startup](skills/debug-infra-startup/SKILL.md) | Diagnosing service startup race conditions in containers: distinguishes "process started" from "HTTP server up" from "actually accepting traffic", probes the real write path, handles distroless image constraints, and fixes wait logic in Compose, CI, and Kubernetes. |
| 12 | [sql-query](skills/sql-query/SKILL.md) | Writing or reviewing SQL: parameterises queries, reads the schema first, picks the right JOIN, avoids NULL traps, checks query plans, adds indexes correctly, and never interpolates user input into SQL strings. |
| 11 | [api-design](skills/api-design/SKILL.md) | Designing or reviewing HTTP APIs: picks the right method and URL, defines request/response shapes, chooses status codes correctly, adds pagination, documents the contract in OpenAPI — no broken conventions, no injection holes. |
| 10 | [env-setup](skills/env-setup/SKILL.md) | Getting a project running locally: reads the repo's own docs and config, installs the pinned runtime, installs dependencies, copies the env template, runs any one-time setup steps, and confirms the baseline build and tests pass. |
| 9 | [release](skills/release/SKILL.md) | Cutting a release end-to-end: bumps the version, moves changelog entries, commits, and creates an annotated git tag — then stops and hands the user the push commands. Never pushes or publishes without being asked. |
| 8 | [dependency-update](skills/dependency-update/SKILL.md) | Upgrading dependencies safely: audits what's outdated, reads changelogs for breaking changes, updates packages one layer at a time, verifies the build, and writes a clean commit — never bumps a major version without confirmation. |
| 7 | [write-tests](skills/write-tests/SKILL.md) | Writing meaningful tests: reads the code first, covers edge cases and error paths, names tests as sentences, follows Arrange-Act-Assert, mocks only external boundaries, and never writes tests just for coverage. |
| 6 | [refactor](skills/refactor/SKILL.md) | Refactoring code safely: renames, extracts functions, splits large files (500–1200 line limits), modularises by responsibility, adds structured logging at the right level, improves comments — tests pass at every step. |
| 5 | [debug-session](skills/debug-session/SKILL.md) | Diagnosing and fixing bugs: reproduces the issue, isolates the root cause with a clear hypothesis, applies a minimal fix, verifies it, and reports honestly — no blind changes. |
| 4 | [changelog](skills/changelog/SKILL.md) | Cutting a release or updating CHANGELOG.md: reads commits and diffs since the last tag, categorises changes by section, proposes a version bump, and writes a user-facing entry in Keep a Changelog format. |
| 3 | [code-review](skills/code-review/SKILL.md) | Reviewing pull requests: reads the actual diff, flags real issues (bugs, security, performance, missing tests), groups feedback by severity, never rubber-stamps. |
| 2 | [pr-description](skills/pr-description/SKILL.md) | Opening or describing a pull request: reads the real diff, follows the repo's PR template, writes a reviewer-ready title and description with honest test notes. |
| 1 | [commit-style](skills/commit-style/SKILL.md) | Committing changes: plans small logical commits, follows the repo's conventions, writes clear Conventional Commits messages, never pushes unasked. |

## Layout

```
.claude-plugin/       marketplace + plugin manifests (Claude Code)
skills/<name>/
  SKILL.md            name, description (when to use), and the playbook
  references/         optional extra docs the skill points to
  scripts/            optional helpers the skill runs
```

## Contributing

Issues and pull requests are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for how to write a
skill, and [AGENTS.md](AGENTS.md) for the rules every skill follows.

## License

[MIT](LICENSE) © Jishanahmed AR Shaikh
