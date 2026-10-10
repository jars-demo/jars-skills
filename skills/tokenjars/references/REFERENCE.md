# TokenJARS — Reference

Load this file when you need per-task workflow detail, long-session context strategy,
or the full reasoning behind the safety invariants.

---

## Workflow patterns by task type

### Repository exploration

1. Read `AGENTS.md`, `CONTRIBUTING.md`, `README.md` — they describe the project layout.
2. Search directly for the symbol or path you need:
   ```bash
   grep -rn "functionName" src/ --include="*.ts" -l   # files containing the symbol
   grep -n "functionName" src/target/file.ts           # line numbers within file
   ```
3. Read only the files that match. Cache findings in a note: `<symbol>: <file>:<line>`.
4. Never: list a directory and then read every file in it.

### Debugging

1. Get the exact error, stack trace, and reproduction steps before touching code.
2. Read only files on the call path from entry to crash.
3. State a single hypothesis before making any change.
4. Verify the hypothesis (add a log or assert if needed) before writing the fix.
5. Apply the minimal fix. Re-run only the failing test first.
6. Report: root cause, fix location, verification method, what remains unverified.
7. Run the full suite after the fix to check for regressions.

### Localized code changes

1. Read the target file and its immediate interfaces (callers, types, schema).
2. Make the change. Show a focused diff — not the full file unless the change is large.
3. Run tests for the affected module:
   ```bash
   pytest tests/test_module.py -x
   npm test -- --testPathPattern module
   ```
4. Escalate to the full suite if the module is imported widely, the change is behavioral,
   or targeted tests pass but something else seems off.

### Test execution: when to run targeted vs full suite

Run **targeted tests** for localized, low-risk changes.

Run the **full suite** when:
- The change touches shared utilities, base classes, or infrastructure.
- Auth, data handling, or a public API changed.
- Pre-release or deployment-blocking confidence is required.
- Targeted tests pass but behavior seems wrong.

Always report: count passed, count failed, any skipped, relevant failure output, exit
status. Never omit failure details to keep the report short.

### Long-session handoff

When a session grows long, consolidate to a compact state note:

```
## State: <task>  (<date>)
Status: in-progress | blocked | complete
Changed files:
  - <path>: <what changed>
Current state: <what works, what does not, last action>
Hypothesis / next step: <current theory>
Key evidence: <decisive error or output — exact text>
Blockers: <stuck items or user input needed>
Unresolved: <open questions or contradictions>
```

Include: decisive error message, last failing test output, relevant branch/commit.
Exclude: full conversation replay, resolved dead ends, passing test reruns.

### Security-sensitive changes

Never compress security findings. Always write in full:
- Which file and line.
- What the attack vector is.
- What the impact is.
- The exact fix (not just "use parameterized queries" — show the code).
- What to verify after the fix.

### Dependency updates

1. Check what's outdated: `npm outdated` / `pip list --outdated`.
2. For each target, read the changelog for breaking changes.
3. Update one package (or one logical group) at a time.
4. Run the test suite after each update.
5. Report: name, old version, new version, changelog notes, test result.
Never update all packages at once — you lose the ability to isolate what broke.

---

## Context and memory management

### What to keep in context

| Keep | Drop |
|---|---|
| Decisive error and stack trace | Passing test output |
| Current hypothesis and ruled-out paths | Resolved dead ends |
| Relevant file paths and line numbers | Full files already summarized |
| Changed interfaces and call signatures | Unchanged boilerplate |
| Unresolved contradictions | Full conversation replay |

### Prompt cache preservation

Providers (Anthropic, OpenAI, Google) cache repeated prefixes at 70–90% discount.
To maximize hits: keep skill instructions and stable context at the top of the context
window. Put dynamic content (user messages, tool results) at the end. Avoid reordering
or inserting content into the stable prefix between turns.

This is a behavioral recommendation — the skill cannot enforce caching directly.

### Cross-session limitations

This skill cannot persist memory across sessions automatically. When resuming a long
task, provide the state snapshot above so the agent can reconstruct context without
replaying the full conversation history.

---

## Safety invariant reasoning

### Why negations must be preserved

A summary that inverts or drops a conditional produces a bug harder to diagnose than the
original. Test: does the summary survive if you add "not" to it? If the negated version
changes what a developer would do, the original wording must be preserved.

❌ Shortened: "The function returns early."
✅ Full: "The function returns early **only when** the user is unauthenticated."

### Why exact values are not paraphraseable

File paths, identifiers, command names, API endpoints, port numbers, HTTP status codes,
exit codes, and error messages must be reproduced exactly. A paraphrase of an error
message changes what a developer searches for.

### Why failed tests must be reported in full

The failure output is primary evidence for the next diagnostic step. Summarizing to
"some tests failed" removes the test name, assertion detail, file, line, and exit code —
everything needed to locate and fix the failure.

### Why security findings must never be abbreviated

A shortened security explanation risks the reviewer underestimating the impact or
misapplying the fix. Attack vector, impact, fix, and verification steps must all be present.

### The compression-vs-lossy distinction

| Technique | Reversible | Lossless | When appropriate |
|---|---|---|---|
| Focused inspection | Yes (original exists) | Yes (subset reported) | Standard — preferred |
| Selective output | No | Yes (excludes confirmed irrelevant) | When exclusion is confirmed safe |
| Lossy summarization | No | No | Only when original can be retrieved if needed |

This skill uses focused inspection and selective output. It does not perform automatic
lossy summarization of evidence that may be needed for diagnosis.

### When to stop optimizing entirely

- Any security finding.
- Any irreversible or destructive operation.
- A failing test or unexpected warning.
- Contradictory evidence.
- Material uncertainty about correctness.
- The user seems confused or needs clarification.
- A cryptic error where full context is needed to diagnose.
