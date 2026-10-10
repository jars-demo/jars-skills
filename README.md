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

| Skill | Use it when |
| --- | --- |
| [api-design](skills/api-design/SKILL.md) | Designing or reviewing HTTP APIs: picks the right method and URL, defines request/response shapes, chooses status codes correctly, adds pagination, documents the contract in OpenAPI — no broken conventions, no injection holes. |
| [changelog](skills/changelog/SKILL.md) | Cutting a release or updating CHANGELOG.md: reads commits and diffs since the last tag, categorises changes by section, proposes a version bump, and writes a user-facing entry in Keep a Changelog format. |
| [code-review](skills/code-review/SKILL.md) | Reviewing pull requests: reads the actual diff, flags real issues (bugs, security, performance, missing tests), groups feedback by severity, never rubber-stamps. |
| [commit-style](skills/commit-style/SKILL.md) | Committing changes: plans small logical commits, follows the repo's conventions, writes clear Conventional Commits messages, never pushes unasked. |
| [debug-infra-startup](skills/debug-infra-startup/SKILL.md) | Diagnosing service startup race conditions in containers: distinguishes "process started" from "HTTP server up" from "actually accepting traffic", probes the real write path, handles distroless image constraints, and fixes wait logic in Compose, CI, and Kubernetes. |
| [debug-session](skills/debug-session/SKILL.md) | Diagnosing and fixing bugs: reproduces the issue, isolates the root cause with a clear hypothesis, applies a minimal fix, verifies it, and reports honestly — no blind changes. |
| [dependency-update](skills/dependency-update/SKILL.md) | Upgrading dependencies safely: audits what's outdated, reads changelogs for breaking changes, updates packages one layer at a time, verifies the build, and writes a clean commit — never bumps a major version without confirmation. |
| [docker](skills/docker/SKILL.md) | Writing, reviewing, and fixing Dockerfiles and Compose files: picks the right base image, sets up multi-stage builds, fixes layer caching, reduces image size, adds healthchecks, avoids running as root, and never leaks secrets into the image. |
| [env-setup](skills/env-setup/SKILL.md) | Getting a project running locally: reads the repo's own docs and config, installs the pinned runtime, installs dependencies, copies the env template, runs any one-time setup steps, and confirms the baseline build and tests pass. |
| [pr-description](skills/pr-description/SKILL.md) | Opening or describing a pull request: reads the real diff, follows the repo's PR template, writes a reviewer-ready title and description with honest test notes. |
| [refactor](skills/refactor/SKILL.md) | Refactoring code safely: renames, extracts functions, splits large files (500–1200 line limits), modularises by responsibility, adds structured logging at the right level, improves comments — tests pass at every step. |
| [release](skills/release/SKILL.md) | Cutting a release end-to-end: bumps the version, moves changelog entries, commits, and creates an annotated git tag — then stops and hands the user the push commands. Never pushes or publishes without being asked. |
| [sql-query](skills/sql-query/SKILL.md) | Writing or reviewing SQL: parameterises queries, reads the schema first, picks the right JOIN, avoids NULL traps, checks query plans, adds indexes correctly, and never interpolates user input into SQL strings. |
| [tokenjars](skills/tokenjars/SKILL.md) | Reducing unnecessary token consumption in AI coding-agent sessions: cuts verbose output, redundant tool calls, and repeated file reads while preserving technical accuracy, implementation quality, and all the evidence needed to diagnose and verify work. Use when a session is growing expensive, an agent is repeating itself, or you want concise, efficient engineering communication. |
| [write-tests](skills/write-tests/SKILL.md) | Writing meaningful tests: reads the code first, covers edge cases and error paths, names tests as sentences, follows Arrange-Act-Assert, mocks only external boundaries, and never writes tests just for coverage. |

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
