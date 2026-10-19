---
name: claude-best-practices
description: "Work efficiently in Claude Code so usage limits last: short focused sessions, small context, lean always-on context, cheap tool use and clean hand-offs. Use at the start of every session, when a session has run for hours or the context is large, when the user mentions /usage, limits, cost or slowness, before starting a big multi-part build, and when switching to a new task."
metadata:
  author: Jishanahmed AR Shaikh
  ecosystem: JARS
  version: "1.0.0"
  homepage: https://skills.jishanahmed.in
---

# Claude best practices

**Same work, a fraction of the usage.**

Usage limits are spent per request, and every request sends the whole conversation so far plus
everything that is always loaded. So the cost of a session grows with how long it has run and
how much context it carries, not only with how hard the task is. A one-line question asked at
200k tokens of context costs far more than the same question in a fresh session.

`/usage` shows what drives your usage. The three patterns it most often reports:

| What `/usage` says | What it means | The fix |
| --- | --- | --- |
| most usage came from sessions active for 8+ hours | one long session doing many unrelated tasks | one task per session; `/clear` between tasks |
| most usage was at more than 150k context | every request resends a huge history | `/compact` mid-task, hand off and start fresh |
| a share went to always-on context over 40k tokens | CLAUDE.md, MCP tools, skills and memory ride on every request | trim them; turn off what you do not use |

## Ground rules

- **Correctness first.** Never skip a test, a check or a warning to save tokens. Saving comes
  from not repeating work, not from doing less of it.
- **The user's and the repository's rules win.** This skill changes how work is paced and
  carried, never what is required.
- **Say it once.** When a session should end, be cleared or be compacted, tell the user in one
  line with the reason. Do not nag.

---

## For the user: five habits

1. **One task per session.** Start a new session (or `/clear`) when the task changes. A finished
   feature, a new repo, "now let's do X": all are new sessions.
2. **Compact before it is big.** Run `/compact` with a focus when the context passes about half
   of the window, for example `/compact keep the plan, the open decisions and file paths`.
   Do not wait for automatic compaction at the very end.
3. **Hand off instead of dragging on.** For multi-day work, ask for a hand-off note (below),
   save it in the repo, `/clear`, and start the next session from the note.
4. **Keep always-on context lean.** Run `/context` to see what is loaded on every request.
   Keep `CLAUDE.md` files short (rules, not essays), disable MCP servers you are not using in
   `/mcp`, and uninstall plugins and skills you never call.
5. **Check `/usage` once a day.** If one pattern dominates, fix that habit first.

## For the agent: how to work

### Start of a session

- Read only what the task needs: the repo's `AGENTS.md` or `CLAUDE.md`, then the files the task
  touches. Do not tour the codebase "for context".
- If the request bundles several unrelated jobs, say so and suggest doing them in separate
  sessions, or finish one, write a hand-off, and let the user `/clear` before the next.

### Reading and searching

- Search first, then read: use grep or glob to find the place, then read that range with an
  offset and limit, not the whole file.
- Never re-read a file you just wrote or edited. The tools tell you when they fail.
- Do not paste large outputs into the conversation. Filter command output (`tail`, `grep`,
  `--quiet`, `-q`) to the lines that answer the question.
- For a broad search across many files where only the answer matters, a subagent keeps the
  main context small. It still uses tokens, so do not spawn one for a lookup that a single grep
  answers.

### Doing the work

- Batch independent tool calls in one turn. Write related files in one turn.
- Plan big builds before writing code: list the pieces, agree on them in one exchange, then
  build without back-and-forth.
- Run long commands (test suites, builds, servers) in the background and wait for the
  notification. Never poll with sleep loops.
- Verify once, at the right level: run the relevant tests after a change, the full suite before
  a commit. Do not re-run a suite that just passed when nothing changed.
- Keep replies short: what changed, what was verified, what is next. No narration of every
  step, no repeating the plan back.

### When the session gets long

Watch for these signs, and when one appears, tell the user once:

- the task the user asked for is done and a new, unrelated one starts
- the conversation has been compacted before, or holds many large outputs
- you are re-deriving facts that were settled earlier

Then offer a hand-off.

### The hand-off note

Write it to a file in the repo (for example `docs/handoff.md`, or the scratchpad) so the next
session can read it in one call:

```markdown
# Hand-off: <task>, <date>

## Goal
One or two sentences.

## Done
- What is finished, with commit hashes.

## Next
1. The next concrete step.

## Decisions
- Choices already made, and why, so they are not reopened.

## Facts
- Paths, commands, ports, versions and gotchas the next session needs.
```

Then tell the user: "Saved a hand-off to <path>. Run /clear and start the next session with:
read <path> and continue."

---

## Checklist

- [ ] One task in this session; unrelated work goes to a new one.
- [ ] Context compacted with a focus before it got huge.
- [ ] Files searched before read, read in ranges, never re-read after editing.
- [ ] Independent tool calls batched; long commands in the background.
- [ ] Tests run once at the right level; no repeated passing runs.
- [ ] Replies short; no step-by-step narration.
- [ ] Hand-off written before a long session ends.
