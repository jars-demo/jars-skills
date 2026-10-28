---
name: snapchat-web-lens-creator
description: Build a lightweight game or interactive experience and package it as a Snapchat Web Lens. Use when the user asks to build a Snapchat game, a Snap Lens, a Web Lens, something to submit on Snap's "My Lenses" portal, or describes a simple/lightweight mobile game they want to ship with Snapchat leaderboard and/or Bitmoji integration.
---

# Snapchat Web Lens creator

Build a small, zero-asset-pipeline, TypeScript + Canvas 2D + Web Audio game and package it
as a Snapchat Web Lens zip ready for Snap's My Lenses portal — leaderboard and Bitmoji
wired in, tested live, nothing left running when it's done.

The full step-by-step process — project scaffold, architecture pattern, procedural art/audio
techniques, the Snap API wrapper, the zip packaging script with its size checks, and the
My Lenses hand-off — lives in **[`references/runbook.md`](references/runbook.md)**. Read it
in full before writing any code; it is the primary reference for this skill, not optional
background reading. Everything below is the trigger condition and the constraints specific
to this skill; the runbook has the actual recipe.

## Ground rules

- **Read the runbook before building anything.** It has exact, working config file contents,
  code templates, and a packaging script — don't reinvent these from scratch or from
  memory of other projects.
- **Scope it small.** One core mechanic, portrait mobile viewport, a title/play/game-over
  flow. This is explicitly a lightweight-game skill, not a general game-engineering skill —
  push back (gently, by proposing a smaller version) on requests that would turn into a large,
  multi-system build.
- **Zero asset pipeline by default.** Draw art on Canvas 2D, synthesize audio with Web Audio.
  No image/audio files unless the user supplies their own — see the runbook's asset policy.
  If they don't supply assets, generate them yourself: procedurally in code (the default) or
  via a connected design tool if one is available and preferred for a one-off asset. Never
  ship placeholder-quality filler art.
- **Zip budget is 7 MB, not Snap's published 8 MB.** This is a deliberate safety margin — bake
  the 7 MB (`7_000_000` byte) cap into the packaging script exactly as the runbook specifies,
  not Snap's 8 MB limit.
- **Ask the scoping questions once, as a single batch, then build straight through.** Don't
  check in step by step — the point of this skill is a fast, mostly uninterrupted build to a
  live-tested result.
- **Verify live, not by reading code back.** Serve the build, open it in a real browser, play
  through it, check the console is clean, and prove the Snap leaderboard/Bitmoji wiring
  actually responds (the runbook has the exact stub-mode check) before calling it done.
- **Close every dev server you start.** Don't leave one running, and don't ask whether to
  leave it running.
- **Never push, publish, or submit without being asked.** Committing, pushing to GitHub,
  deploying, and submitting to the My Lenses portal are all separate, explicit asks — building
  the game is not implicit permission to ship it anywhere.
- **The preview video and final portal submission are the user's step.** Offer to help script
  an automated recording if useful, but don't assume it's wanted, and never submit on the
  user's behalf.

## Workflow

1. Load `references/runbook.md` in full.
2. Follow its Step 0 (intake) through Step 12 (hand-off) in order, for the game idea the user
   described.
3. Report back the way the runbook's Step 9/10 describe: what was verified live, what's
   committed (if anything), and what's left for the user (icon approval, video, portal
   submission) — not a restatement of every step taken.

## Examples

| Weak | Strong |
| --- | --- |
| Jumping straight into `npm init` from memory of a past project | Reading `references/runbook.md` first, then scaffolding from its exact templates |
| Shipping with the actual 8 MB Snap limit as the target | Enforcing the 7 MB cap from the runbook's packaging script |
| "The leaderboard code looks right" as the verification | Serving the packaged Lens build and calling `window.snapchat.leaderboards.submitScore(...)` live to confirm the stub actually responds |
| Using a stock image/icon pack to save time | Drawing a procedural icon/logo in code (or using the user's own supplied assets) |
