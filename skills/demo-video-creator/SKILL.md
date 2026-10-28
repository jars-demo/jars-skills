---
name: demo-video-creator
description: Produce a narrated demo, trailer, or preview video built from real, continuously-captured app/game/site footage — never a screenshot slideshow. Use when the user asks for a demo video, trailer, product video, Snap Lens preview video, app walkthrough, or a screen recording with narration, music, or sound effects added.
---

# Demo video creator

Turn a running site, app, or game into a polished, narrated video — real captured motion and
real in-app audio as the picture, with narration, music beds, SFX, and captions layered on top
in the edit.

The full step-by-step process — the Playwright + CDP screencast capture technique, the
fixed-fps conversion, ElevenLabs narration/music/SFX generation, faster-whisper captions, and
the final ffmpeg assembly with ducking and loudness normalization — lives in
**[`references/runbook.md`](references/runbook.md)**. Read it in full before recording
anything; it is the primary reference for this skill, carrying real working script templates
distilled from shipped videos, not guesses.

## Ground rules

- **Real captured footage, always.** The picture is genuine continuous motion captured from
  the running target (a real cursor moving, a real page/game reacting) — never a slideshow of
  static screenshots with pans/zooms standing in for video. This is non-negotiable, including
  under time pressure: if real capture genuinely isn't possible, say so rather than falling
  back to a slideshow silently.
- **Real audio for anything the target itself produces sound for.** Tap the live
  `AudioContext`/`<audio>` graph during capture (the runbook has the exact technique) rather
  than faking a game's or app's own sound with generic stock audio.
- **Narration, music, and SFX on top are expected and good** — the rule above is about the
  picture (and the target's own sound) being real, not about refusing any synthesized layer.
- **Read the runbook before writing any recording script.** It has working, previously-shipped
  templates for the capture script, the fixed-fps conversion, the ElevenLabs client, the
  transcript step, and the final assembly script — adapt these rather than starting from a
  blank script.
- **Record scene by scene, cut together after.** Don't attempt one unbroken take covering the
  whole video; record clean continuous footage per scene/flow so a bad scene is a cheap retake.
- **Never publish, upload, or submit the finished video anywhere without being asked.** Building
  it and handing back the file is the default; distribution is a separate ask.
- **Clean up afterward** — scratch recording/intermediate files and any dev server started to
  serve the target.

## Workflow

1. Load `references/runbook.md` in full.
2. Follow its Step 0 (intake/shot planning) through Step 7 (hand-off) for the target and script
   the user described.
3. Report back what was captured, assembled, and verified, and hand over the output file path —
   not a restatement of every step taken.

## Examples

| Weak | Strong |
| --- | --- |
| A slideshow of screenshots with a Ken Burns pan and narration over it | Real CDP-screencast-captured continuous footage of the actual running target |
| Guessing fixed sleep delays to time actions to narration | A `mark`/`until` anchor system synced to real voiceover timestamps |
| Faking a game's sound effects with generic stock SFX | Tapping the page's real `AudioContext`/`<audio>` graph during capture |
| Mixing audio by ear with raw volume levels | Sidechain ducking under the voice track, finished with `loudnorm` to a consistent level |
