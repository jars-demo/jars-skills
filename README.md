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
| 62 | [demo-video-creator](skills/demo-video-creator/SKILL.md) | Producing a narrated demo, trailer, or preview video from a real running site, app, or game: captures continuous footage via Playwright + CDP screencast (never a screenshot slideshow), taps real in-app audio when it matters, generates narration/music/SFX with ElevenLabs and captions with faster-whisper, and assembles the final cut with ffmpeg including sidechain ducking and loudness normalization. |
| 61 | [snapchat-web-lens-creator](skills/snapchat-web-lens-creator/SKILL.md) | Building a lightweight Snapchat Web Lens game or interactive experience: scopes the idea down to one core mechanic, scaffolds a zero-asset-pipeline TypeScript + Canvas 2D + Web Audio stack, wires in Snap leaderboard and Bitmoji integration, packages the build into a Lens zip under a 7MB cap with automated requirement checks, and verifies everything live before handing off for the My Lenses submission. |
| 60 | [runbook-writer](skills/runbook-writer/SKILL.md) | Turning a workflow you just carried out, or know well, into a portable, placeholder-driven runbook document that a fresh agent session can execute end-to-end from a single pasted message: finds the one real variable input, captures the working path (including fixes for dead ends hit along the way), and shapes ground rules, numbered steps, verification, and hand-off into one self-contained Markdown file. |
| 59 | [dependency-injection](skills/dependency-injection/SKILL.md) | Designing and wiring dependencies through constructor injection so classes are testable and loosely coupled: defines protocols/interfaces before implementations, injects all dependencies at construction time, wires the object graph at the composition root, tests with hand-rolled fakes instead of mocking frameworks, uses a DI container only when the graph is large, and avoids service locators and hidden globals. |
| 58 | [testing-strategy](skills/testing-strategy/SKILL.md) | Designing a test suite that catches real bugs without becoming a maintenance burden: applies the test pyramid, decides what belongs at unit vs integration vs contract vs E2E layer, tests behaviour not implementation, uses real databases in integration tests, avoids over-mocking, keeps the suite fast with parallel runs and transaction rollback, and names tests as sentences. |
| 57 | [notifications](skills/notifications/SKILL.md) | Designing a multi-channel notification system: routes through email, push, SMS, and in-app channels based on user preferences, deduplicates within time windows to prevent spam, renders templates with autoescape, tracks delivery per channel, respects opt-outs, and always dispatches through the background queue so business logic never blocks on delivery. |
| 56 | [file-storage](skills/file-storage/SKILL.md) | Designing and implementing file upload, storage, and delivery: generates presigned S3 PUT URLs for direct client uploads so bytes never transit the app server, validates files by content type after upload, confirms uploads by checking S3 directly, scans for malware asynchronously, serves files via CDN or presigned GET URLs, and sets lifecycle policies to control storage costs. |
| 55 | [api-versioning](skills/api-versioning/SKILL.md) | Designing and evolving APIs without breaking clients: distinguishes breaking from non-breaking changes, implements URL path versioning with versioned schemas frozen per release, adds RFC 8594 Sunset and Deprecation headers, follows a 4-phase deprecation lifecycle, returns 410 Gone for retired endpoints, and monitors version traffic before retiring. |
| 54 | [search](skills/search/SKILL.md) | Implementing search that works at scale: chooses between PostgreSQL full-text search and Elasticsearch, builds tsvector generated columns with weighted fields and GIN indexes, queries with plainto_tsquery and ts_rank, adds trigram fuzzy matching for typo tolerance, designs Elasticsearch mappings with custom analyzers and multi-match queries, and keeps the index in sync via the outbox pattern. |
| 53 | [database-transactions](skills/database-transactions/SKILL.md) | Writing correct database transactions: keeps transactions short, chooses isolation levels deliberately, uses SELECT FOR UPDATE and optimistic locking with version columns, prevents deadlocks with consistent lock ordering, retries on serialization and deadlock errors, uses savepoints for partial rollback in batches, and monitors pg_stat_activity for long-running transactions. |
| 52 | [event-driven-architecture](skills/event-driven-architecture/SKILL.md) | Designing event-driven systems: defines versioned integration event schemas, separates domain from integration events, implements the transactional outbox to guarantee publication without dual writes, builds idempotent consumers with event_id deduplication, handles schema versioning with backward-compatible rules, and partitions events for ordering guarantees. |
| 51 | [multi-tenancy](skills/multi-tenancy/SKILL.md) | Designing and implementing multi-tenant data isolation: chooses between row-level, schema-per-tenant, and database-per-tenant strategies, propagates tenant context via middleware through the request lifecycle, enforces tenant scoping in a base repository class, applies PostgreSQL Row Level Security as a second defence, and audits for cross-tenant leakage bugs in cache keys, background jobs, and aggregate queries. |
| 50 | [circuit-breaker](skills/circuit-breaker/SKILL.md) | Implementing the circuit breaker pattern to stop cascading failures: builds the three-state machine (closed, open, half-open), wires it around outbound HTTP calls using opossum (Node.js) or a hand-rolled async implementation (Python), tunes failure thresholds and recovery timeouts, wires a fallback, and exposes circuit state as a Prometheus metric with an alert. |
| 49 | [pagination](skills/pagination/SKILL.md) | Designing and implementing pagination that stays fast at scale: chooses cursor/keyset over OFFSET for large datasets, encodes opaque cursors, returns consistent page metadata, handles the total-count tradeoff, creates the right composite index for the sort order, and avoids duplicate or missing records when data changes between pages. |
| 48 | [webhook-handling](skills/webhook-handling/SKILL.md) | Receiving, verifying, and processing webhooks reliably: verifies HMAC-SHA256 signatures with timing-safe comparison before touching the payload, returns 200 immediately and processes in the background, makes handlers idempotent with a deduplication table, handles retries by distinguishing retriable from non-retriable failures, and protects against replay attacks. |
| 47 | [type-safety](skills/type-safety/SKILL.md) | Eliminating type errors and unsafe holes in TypeScript and Python: enables strict mode, removes every any and unsafe cast, narrows with type guards and discriminated unions, uses branded types for domain correctness, validates external data at runtime with Zod or Pydantic, and uses exhaustiveness checking so adding a new variant causes a compile error. |
| 46 | [idempotency](skills/idempotency/SKILL.md) | Designing operations safe to retry without side effects: idempotency keys on POST/PATCH endpoints, Redis-backed deduplication store, database upserts with ON CONFLICT, idempotent background job handlers, at-least-once vs exactly-once delivery semantics, and client-side key generation. |
| 45 | [claude-best-practices](skills/claude-best-practices/SKILL.md) | Working efficiently in Claude Code so usage limits last: one task per session, compacting before context gets huge, a lean CLAUDE.md and MCP setup, searching before reading, batching tool calls, background commands, and clean hand-off notes between sessions. Use at the start of every session and whenever /usage shows long sessions or large context. |
| 44 | [input-validation](skills/input-validation/SKILL.md) | Validating and sanitising all external input at the boundary before it reaches business logic: schema validation with Pydantic/Zod/Joi, type coercion traps, allow-lists over block-lists, rejecting unexpected fields, URL and file upload validation, preventing injection through input shape, and returning precise error messages that help callers fix their request without leaking internals. |
| 43 | [simplify](skills/simplify/SKILL.md) | Reducing code to its simplest correct form: replaces verbose imperative loops with built-in expressions, collapses redundant conditionals, applies early returns to flatten nesting, removes unnecessary abstraction layers, and spots where a standard library function already does what 40 lines of custom code is doing — without changing behaviour. |
| 42 | [code-comments](skills/code-comments/SKILL.md) | Reading an unfamiliar codebase and adding comments that help the next engineer: explains why decisions were made, documents non-obvious behaviour, adds contract comments on public functions, writes file-level navigation headers, and removes stale and misleading comments — without documenting the obvious. |
| 41 | [chaos-engineering](skills/chaos-engineering/SKILL.md) | Running controlled chaos experiments to find resilience weaknesses before production does: defines a steady-state hypothesis, injects realistic faults (latency, pod kill, disk fill, dependency failure) with Toxiproxy, tc/netem, Litmus, and stress-ng, limits blast radius, observes system behaviour against the hypothesis, runs a GameDay, and turns findings into hardening tasks. |
| 40 | [graceful-shutdown](skills/graceful-shutdown/SKILL.md) | Implementing graceful shutdown so a service drains cleanly on SIGTERM: stops accepting new requests, waits for in-flight requests to complete, closes database and cache connections in the correct order, configures Kubernetes terminationGracePeriodSeconds correctly, and returns 503 from the health check immediately so the load balancer stops routing before the drain starts. |
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
