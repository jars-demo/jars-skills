---
name: runbook-writer
description: Turn a workflow you (or the user) just carried out, or know well, into a portable, placeholder-driven runbook document that a fresh agent session can execute from a single pasted message. Use when the user asks for a runbook, a repeatable playbook, a "paste this and it does X" document, a process write-up they can hand to another Claude session, or wants to capture "how we just did that" so it can be redone with one input swapped.
---

# Runbook writer

Produce a single, self-contained Markdown document that lets a **fresh agent session with
no prior context** carry out a known workflow end-to-end, after the user fills in one or a
few placeholders. The runbook is the deliverable — not a summary of the workflow, a literal
script for redoing it.

## Ground rules

- **Self-contained means self-contained.** The reader is a new session. It has not seen this
  conversation, this codebase, or any prior decisions. Every path, command, config value, and
  piece of reasoning the workflow depends on must be *in* the document, not referenced from
  outside it.
- **One real input point, clearly marked.** Find the one or two things that actually vary
  between runs (an idea, a name, a target path) and surface each as a single, unmistakable
  placeholder — `IDEA PUT HERE`-style: uppercase, bracket-free, easy to find-and-replace, named
  for what it holds. Do not scatter five subtly different placeholders for the same concept.
  Everything else in the runbook is fixed and should not need editing per run.
- **Capture what actually happened, not an idealized version.** If the real workflow hit a
  dead end and recovered (a tool that doesn't exist on this OS, a wrong assumption that got
  corrected), the runbook should encode the *fix*, not silently repeat the dead end. Steps are
  "what to do", written from the working path, with real fallbacks inlined where the original
  workflow needed one (see the "Windows zip tool" style pattern: try X, fall back to Y, fall
  back to Z).
- **Ground rules before steps.** Lead the document with a short "ground rules" section stating
  the non-negotiables (scope limits, budgets, safety constraints, what never to do without
  asking) — these get followed even if a later step is skimmed.
- **Ask-once discipline, if the source workflow had one.** If the original process involved
  clarifying questions up front followed by uninterrupted execution, preserve that shape in the
  runbook explicitly: "ask these, once, as a batch — then proceed without further check-ins."
  Don't let the runbook silently turn into a back-and-forth.
- **Concrete over abstract.** Prefer an exact code snippet, exact config file content, or an
  exact shell command the reader can paste, over a prose description of what to write. A
  runbook a reader has to reverse-engineer into working code has failed its one job.
- **Stay a runbook, not a tutorial.** Skip the "why this technology" explanations and the
  background theory. State what to do and the one or two sentence reason only when the reason
  changes what the reader should do (a gotcha, a constraint, a "don't bother trying X, it
  doesn't work here").
- **Never assume write access to anywhere specific.** End with a step that tells the reader
  what "done" looks like and what to hand back to the user — don't bake in an assumption that
  the runbook's own output gets committed, pushed, or published without the user in that future
  session confirming it.

## Workflow

### 1. Identify the real workflow

If you just did the thing yourself in this conversation, that's your source material — pull
from what actually happened, including the detours that got corrected, not a cleaned-up
mental model of it. If the user is describing a workflow you haven't just performed, ask them
to walk through it once (or point you at the repo/transcript where it happened) rather than
guessing at steps.

### 2. Find the variable and the invariants

For each candidate input, ask: does this change between runs, or is it something this
workflow always does the same way? Keep the variable set as small as possible — usually one,
sometimes two or three. Everything else becomes a fixed instruction in the runbook, often
including exact code/config templates pulled from the real, working implementation.

### 3. Shape the document

A runbook document is typically, in this order:

1. **A short intake block** — how to paste this runbook, and the placeholder(s) to fill in
   before pasting.
2. **Ground rules** — the handful of constraints that govern every step (budgets, scope,
   safety, "ask once then don't stop").
3. **An intake/scoping step**, if the workflow needs the reader to clarify anything about the
   variable input before starting — written as "ask this, once, in a batch" if that matches
   the source workflow.
4. **The numbered steps themselves**, each one concrete enough to execute without guessing,
   embedding exact commands/config/code where the real workflow produced them.
5. **A verification step** — how the reader proves to themselves (and the user) that it
   actually worked, not just that it compiled/ran without error.
6. **A hand-off step** — what to report back to the user, and what (if anything) is explicitly
   reserved for the user's own action (a push, a publish, a human-only step like recording a
   video or approving a submission).
7. **A short checklist** at the end — one line per step, for fast re-runs once the reader
   already knows the document.

### 4. Write it, then stress-test it mentally

Read the draft as if you really were a fresh session with zero memory of the source
conversation. For each step, ask: is there anything here that only makes sense because I
remember the original context? If yes, make it explicit. Check that the placeholder(s) are
named clearly and appear exactly where they're meant to be filled in — usually right at the
top, in a one-line "fill this in" block.

### 5. Save and report

Save the runbook to the path the user asked for (or propose one and confirm if they didn't
say). Tell them in one or two sentences what the single swappable input is and roughly how
many steps the document walks through — don't restate the whole document back to them in
chat.

## Examples

| Weak | Strong |
| --- | --- |
| "Step 3: set up the project the way we usually do" | Step 3 embeds the actual `package.json`/config file contents, verbatim, ready to paste |
| A runbook with six slightly different `{{name}}`, `{{game}}`, `{{title}}` placeholders all meaning the same thing | One placeholder, named for what it holds, used consistently |
| "Make sure it's lightweight" as the only guidance | A ground rule stating the actual budget/limit that was used in the real run (a byte cap, a time box, a dependency count) |
| Steps that assume the reader remembers an earlier mistake and its fix | The fix is written into the step itself, with the dead end mentioned only as a one-line "don't bother trying X" |
