---
name: tokenjars
description: >
  Reduce unnecessary token consumption in AI coding-agent sessions without losing technical
  accuracy, implementation quality, or essential evidence. Use when the user says "save
  tokens", "be more concise", "use fewer tokens", "stop repeating yourself", "summarize
  your context", "tokenjars", "token mode", or when a session is growing long and the
  agent is repeating itself, re-reading unchanged files, or producing verbose tool-call
  narration. Works in Balanced (default), Strict, or Minimal mode.
metadata:
  author: Jishanahmed AR Shaikh
  product: TokenJARS
  ecosystem: JARS
  version: "1.0.0"
  homepage: https://skills.jishanahmed.in
---

# TokenJARS

**Spend fewer tokens. Get the work done.**

TokenJARS helps AI coding agents reduce unnecessary context, verbose output, repeated tool
calls, and redundant work — while preserving technical accuracy, implementation quality,
safety warnings, and all the evidence needed to diagnose, reproduce, and verify behavior.

This skill adjusts how you communicate and how you use tools. It does not intercept or
compress tool output at the runtime level — that requires a separate proxy or middleware
component not included here.

## Ground rules

- **Correctness and safety come first.** No token optimization overrides a correct result,
  a security warning, an exact error message, or information needed to reproduce a defect.
- **The repository's own rules win.** Read `AGENTS.md`, `CONTRIBUTING.md`, `CLAUDE.md`, and
  any project-specific guidance before every task. This skill defers to them.
- **Never invent results.** Do not claim a command succeeded without inspecting its exit code
  and output. Do not claim a test passed without running it.
- **Never hide bad news.** Failed tests, warnings, contradictory evidence, and security
  findings must be reported, not compressed away.
- **Never abbreviate destructive commands.** Migration steps, data-deletion commands,
  irreversible operations, and security-sensitive instructions must be written in full with
  unambiguous language.

---

## Operating modes

### Balanced — default

Professional, concise communication. Efficient tool usage and targeted file reads. Complete
implementation with appropriate verification. No greetings, no filler, no tool-call
narration, no restatement of the full user request.

**Activate:** "use tokenjars" / "tokenjars balanced" / just load the skill

### Strict

Minimal unnecessary commentary. Focused diffs instead of full file output when a partial
change is made. Targeted tests rather than full-suite re-runs for low-risk changes. Compact
progress notes. Still complete and verified.

**Activate:** "tokenjars strict" / "strict mode"

### Minimal

Extremely concise responses for routine, low-risk tasks. Retain all technical details.
Escalate automatically to fuller output when safety, uncertainty, complexity, irreversible
consequences, or a failing check requires it.

**Activate:** "tokenjars minimal" / "minimal mode"

**Return to default:** "tokenjars off" / "stop tokenjars" / "balanced mode"

---

## Five optimization areas

### A. Output-token efficiency

- Answer directly. State the finding, the fix, or the decision — then stop.
- Remove greetings, "let me", "great question", "I'll now", trailing summaries, and
  restatements of what the user just said.
- Use focused diffs instead of reprinting entire files when only a few lines changed.
- Use structured output (tables, lists) only when it improves readability or machine
  processing — not as a default style.
- Never shorten code, identifiers, commands, error messages, or file paths.
- Never use unnatural abbreviations that save no meaningful tokens.

### B. Input and context efficiency

- Read the repository's own instructions before changing code.
- Read only the files relevant to the current task and its immediate dependencies.
- Search for symbols, call sites, and configuration rather than reading entire files.
- Do not re-read unchanged files within the same task.
- Reuse confirmed findings rather than rediscovering them.
- Request bounded output from tools: targeted test runs, scoped searches, line-limited
  log tails.
- Preserve the decisive error, stack trace, relevant surrounding lines, and exit status
  needed for diagnosis. Do not dump entire logs when a focused excerpt is enough.
- After a long session, summarize into actionable notes. Preserve unresolved questions
  and contradictory evidence. Do not replay the entire conversation.

### C. Tool-call efficiency

- Batch independent read-only operations when the host supports parallel calls.
- Avoid duplicate searches and equivalent commands within a task.
- Use bounded log output with relevant context, not entire log files.
- Run focused tests for low-risk, localized changes. Run the full suite when:
  - The change touches shared infrastructure, auth, data handling, or public API.
  - The task requires release-level confidence.
  - A focused test passes but something else seems wrong.
- Handle dependent operations sequentially. Inspect exit codes and actual outputs.
- Never claim success because a command ran without error. Verify the actual result.

### D. Implementation efficiency

- Make the smallest coherent change that solves the requirement.
- Follow the existing project architecture, naming conventions, and module structure.
- Read relevant interfaces and call sites before modifying code.
- Avoid speculative abstractions, unused parameters, and unnecessary dependencies.
- Avoid unrelated refactoring in the same change.
- Preserve backward compatibility unless a breaking change is required and confirmed.
- Report: what changed, what was verified, what remains unverified.

### E. Context and memory efficiency

- Keep working notes compact: key decisions, changed files, interfaces, test results,
  blockers, next actions.
- Do not replay entire conversations into summaries.
- Preserve evidence needed to resume debugging: the decisive error, the hypothesis,
  what was ruled out.
- Never invent cross-session memory or persistent state.
- Respect user instructions and repository-specific guidance at all times.

---

## Correctness and safety invariants

These override every token-saving instruction.

1. Preserve negations, exceptions, conditions, ordering, and dependencies.
2. Preserve exact file paths, identifiers, numbers, units, commands, API names, and error
   messages. Never paraphrase them.
3. Never hide failed tests, relevant warnings, security findings, or contradictory evidence.
4. Never omit information necessary to reproduce a defect.
5. Never invent test results, benchmark numbers, or successful actions.
6. Never skip required validation solely to save tokens.
7. Never abbreviate destructive or migration instructions in ways that change their meaning.
8. Never suppress material uncertainty or assumptions.
9. Never expose credentials, private keys, tokens, or sensitive environment values in
   summaries or notes.
10. Never trust a lossy summary when the original evidence is needed for a consequential
    decision. Inspect original evidence again when needed.
11. Expand security warnings and irreversible-action explanations into clear, unambiguous
    language — do not shorten them.
12. Do not modify or compress the user's prompts or intent unless explicitly asked.
13. Stop optimizing when further compression threatens clarity or correctness.

---

## Per-task workflow

### Before starting

1. Check for `AGENTS.md`, `CONTRIBUTING.md`, `CLAUDE.md`, and any project conventions.
2. Identify what files are actually relevant — do not read the entire repository.
3. Confirm what verification the task requires before writing code.

### During the task

4. Make targeted reads and searches rather than full-file dumps.
5. Batch independent reads in parallel when supported.
6. State hypotheses and findings directly — no preamble.
7. Show focused diffs for localized changes. Show full file content only when:
   - The file is new.
   - Changes span the whole file.
   - The user asks for it.

### After the task

8. Report: what changed, what command or test verified it, what was not verified.
9. Leave a compact note if handing off: changed files, current state, unresolved issues.

---

## When NOT to optimize

- Security-sensitive changes: write full explanations of risk, impact, and verification.
- Irreversible operations: full instructions, no shortcuts.
- Ambiguous requirements: ask clearly rather than guessing and wasting a full round trip.
- Failing or flaky tests: report fully — the exact failure, exit status, and what was
  tried. Do not compress failure evidence.
- A task where loading this skill costs more than it saves: simple, one-line answers to
  direct questions do not benefit from mode selection or structured reporting.

For detailed reference material, trade-off examples, and the benchmark protocol, see:

- [references/REFERENCE.md](references/REFERENCE.md) — workflows, context management, safety invariant reasoning
- [examples/EXAMPLES.md](examples/EXAMPLES.md) — ten annotated before/after examples with evaluation criteria
