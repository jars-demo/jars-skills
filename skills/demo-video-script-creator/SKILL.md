---
name: demo-video-script-creator
description: Write the voiceover script and shot plan for a narrated explainer, product demo, or workshop video, in ElevenLabs v3 format with delivery tags, sized to a 3 to 5 minute runtime. Use when the user asks for a video script, a demo script, a voiceover or narration script, an ElevenLabs script, or wants to plan a video before recording it. Hands off to demo-video-creator, which records and builds the video.
---

# Demo video script creator

Write the script a video is built on: what the voice says, how it says it, and what is on
screen while it says it. The output is two files, a narration script the user (or the
ElevenLabs API) turns into a voiceover, and a shot plan that `demo-video-creator` builds from.

The voiceover becomes the video's clock, so the script decides the runtime, the pacing and
every scene. Get it right here and the build is mechanical.

## Ground rules

- **Read the subject before writing a line.** Clone or open the project, read its README, docs
  or chapters, and run or open it. Every claim, command, output and number in the script must
  be one you saw. If a line can't be shown on screen or checked in the source, cut it.
- **Never invent facts, quotes, stats or outcomes.** Real-world framing is good; made-up
  incidents, lawsuits, company names or percentages are not. Prefer "projects get this wrong
  all the time" over a specific story you can't source.
- **Runtime: 3 to 5 minutes by default.** Go longer only when the topic needs the depth to be
  understood, and say so up front with the target length and why. Go shorter only when asked
  (a teaser, a Short).
- **Size the script by words, not feel.** Jeremy on ElevenLabs v3 has run between **2.2 and
  2.8 spoken words per second** with this format (2.23 on one script, 2.77 on another: shorter
  lines and fewer `...` read faster). Plan at **2.5**: 450 words ≈ 3:00, 625 ≈ 4:10, 750 ≈ 5:00,
  and say the range ("about 3:45 to 4:45") rather than one number. Count spoken words (tags
  excluded) before handing over. Once the `.mp3` arrives, measure the real pace and tell the user
  the actual runtime.
- **Write for the ear, in the ElevenLabs format.** Follow
  [`references/elevenlabs-format.md`](references/elevenlabs-format.md): one short line per
  beat, delivery tags at each mood change, `...` for pauses, acronyms and file names spelled the
  way they should be spoken.
- **Clean, clear, professional, hands-on.** Plain words, one idea per line, no hype words
  ("revolutionary", "game-changing"), no filler. The viewer should finish knowing one idea well
  and how to try it themselves.
- **Honest about limits.** If the subject has a disclaimer (not legal advice, read-only,
  experimental), it goes in the script.
- **Don't record or publish anything.** This skill writes files. Generating the voiceover and
  building the video belong to `demo-video-creator`; uploading belongs to the user.

## Pick the format

| Format | Use it for | Shape | Explainer vs demo |
| --- | --- | --- | --- |
| **Explainer + demo** (default for workshops and labs) | Teaching a topic, then showing the hands-on thing that teaches it | Hook → problem → the concept → real-world mistakes or uses → what I built → one worked example → try it yourself → closing line | ~60% explainer, ~40% live |
| **Product demo** | A tool, app, connector or site | Hook (a real pain) → what it is → how it works → live walkthrough → proof (evidence on screen) → how to get it → closing line | ~25% explainer, ~75% live |
| **Pure explainer** | A concept with nothing to click | Hook → why it matters → the idea in 3–5 steps → a real example → the takeaway | Animated scenes only |
| **Teaser / Short** | A trailer for a longer video, or a vertical Short | Hook → one striking moment → where to see more. 30–60 seconds | Mostly live |

Pick the format from what the user asked for and the subject. Don't ask unless it's genuinely
unclear; a workshop or lab repo means Explainer + demo.

## Workflow

1. **Gather.** Read the subject end to end: README, docs or chapters, the site, and real
   command output (run it). Note the real names, commands, outputs and links the script will use.
2. **Find the hook.** One concrete moment the viewer recognises, framed as a question or a
   pain ("You find the perfect library on GitHub… were you allowed to?"). It comes first, in
   the first ten seconds.
3. **Outline the acts** for the chosen format, with a word budget per act that adds up to the
   target runtime.
4. **Write the narration** in the ElevenLabs format. Use first person ("I built") when the user
   built the thing. End on a short closing line said slowly, ideally echoing the title.
5. **Write the shot plan**: a table of acts with the script lines each one covers, what's on
   screen, and whether it's an animated scene or live capture. Note the brand/theme source, the
   links for the end card, and the audio intent (music bed per act, transition SFX, a click on
   every real click).
6. **Check it.** Count spoken words against the runtime; read every factual line back against
   the source; confirm every live scene shows something that really exists.
7. **Hand off.** Save `inbox/narration.txt` and `plan.md` in a video work folder, give the user
   the script inline (ready to paste into ElevenLabs), the word count and expected runtime, then
   continue with `demo-video-creator`. It gets the voiceover: through the API when the key can
   use the voice, otherwise by asking the user for the `.mp3`.

## Examples

| Weak | Strong |
| --- | --- |
| "In this video, I'll show you my new project." | "You find the perfect library on GitHub. It does exactly what you need… Were you allowed to?" |
| "Studies show 80% of projects have licence issues." (unsourced) | "In the real world, projects get this wrong all the time. Not out of bad intent. Out of habit." |
| "The MIT licence is permissive." | "Permissive licences, like M-I-T and Apache two point oh, ask for very little." |
| A 1,100-word script for a "short demo" | 657 words for a 5-minute cap, counted before hand-off (it read in 3:57) |
| Shot plan: "show the app" | "Real terminal: `nest run 1` (three ✗), fix, `nest check 1` (four PASS)" |
