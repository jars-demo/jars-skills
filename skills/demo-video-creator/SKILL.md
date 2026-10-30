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

- **Script first.** With no narration script yet, write one with the
  `demo-video-script-creator` skill (script + shot plan, 3 to 5 minutes by default) before
  recording anything.
- **Get the voiceover the seamless way, and say plainly when you can't.** Look for
  `ELEVENLABS_API_KEY` in the environment or a local `.env` (never print it; make sure `.env` is
  git-ignored). If it's missing, ask the user for one. With a key, check it can use the chosen
  voice (default: Jeremy, `bkWmSiLbVbuhntmf2Kw7`) and has enough characters left for the script,
  then generate the voiceover. If there's no key, or the key can't use the voice (the free plan
  refuses library voices through the API with `402 paid_plan_required`), give the user the
  script and tell them clearly: "Your ElevenLabs API key isn't available or can't use this
  voice, so please record this script in ElevenLabs and send me the .mp3." Then wait for it.
  The runbook's Step 5 has the checks.
- **If there's a voiceover, the voiceover is the clock.** The timeline runs on voiceover time
  and the voiceover is never cut or re-timed to fit the footage — animated scenes, live-app
  actions, and all editing decisions bend to it instead. See the runbook's "The one rule".
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
- **Every video gets a sound design, by default.** A subtle instrumental music bed ducked under
  the voice, a soft SFX on act changes and reveals, and a real click sound on every recorded
  click, placed at the click's logged timestamp so it lands on the frame the cursor presses.
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
   not a restatement of every step taken — plus the YouTube package from the runbook's Step 8
   (title, description with links and chapters, tags, captions file, thumbnail).

## Examples

| Weak | Strong |
| --- | --- |
| A slideshow of screenshots with a Ken Burns pan and narration over it | Real CDP-screencast-captured continuous footage of the actual running target |
| Guessing fixed sleep delays to time actions to narration | A `mark`/`until` anchor system synced to real voiceover timestamps |
| Faking a game's sound effects with generic stock SFX | Tapping the page's real `AudioContext`/`<audio>` graph during capture |
| Mixing audio by ear with raw volume levels | Sidechain ducking under the voice track, finished with `loudnorm` to a consistent level |
