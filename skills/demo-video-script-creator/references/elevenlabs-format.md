# The ElevenLabs script format

The narration script is pasted as-is into ElevenLabs (the website or the text-to-speech API with
the `eleven_v3` model). The format below is what makes the voice sound directed rather than
read.

## Layout

- **One beat per line, blank line between lines.** A line is a sentence or a fragment, rarely
  more than 15 words. Short lines give the voice room to breathe and give the edit clean cut
  points.
- **Fragments are fine.** "Two tools. Two tabs. One engineer." lands harder than one long
  sentence.
- **Lists as separate lines.** "Pipelines. / Tasks. / Datasets. / Owners." Each item gets its own
  beat, and the edit can reveal each one on its word.

## Delivery tags

A tag in square brackets on its own line sets the delivery for everything after it, until the
next tag. Put one at the start and one at every change of mood: usually one per act.

| Tag | Use it for |
| --- | --- |
| `[curious, conversational]` | A hook that asks the viewer a question |
| `[serious, measured]` | The problem; a cold open |
| `[serious, deliberate]` | A key question, or a list of mistakes |
| `[warm, explanatory]` / `[measured, explanatory]` | Teaching a concept; walking through a demo |
| `[confident]` | Introducing the thing that was built |
| `[slight pause]` / `[slight pause, building energy]` / `[slight pause, visual reveal]` | A beat before a turn or a reveal |
| `[confident, emphatic]` | The payoff: the answer, the result |
| `[warm, building]` / `[confident, building to close]` | The run-up to the call to action |
| `[excited, deliberate, final emphasis]` | The closing line |

Tags are spoken direction, not words. Exclude them when counting words.

## Pauses and emphasis

- `...` at the end of a line holds the beat before the next line: "Give Cognee... / the
  context... / of your data platform."
- Split a closing line across lines, one or two words each, to have it said slowly.
- A question on its own line gets a natural rising read; use it for the hook.

## Say it the way it should sound

The voice reads letters and symbols literally, so write the spoken form:

| On screen | In the script |
| --- | --- |
| MIT, GPL, AGPL, SPDX, npm, ISC, uv | M-I-T, G-P-L, A-G-P-L, S-P-D-X, N-P-M, I-S-C, U-V |
| Apache-2.0 | Apache two point oh |
| package.json | package dot json |
| README | readme |
| `docker compose up` | Docker Compose up |
| 2 a.m. | two in the morning |
| v1.4.0 | version one point four |

Words that are said as words (GitHub, Docker, Airflow, DataHub, SQL as "sequel" if that's the
house style) stay as they are. When unsure, spell it with hyphens.

## Length

- Count spoken words with the tags removed. Plan at ~2.5 words per second (measured 2.2–2.8):
  3 minutes is about 450 words and 5 minutes about 750.
- One API request has a character limit. If the script is longer, split it at an act boundary
  (never mid-act) and join the parts in the edit.

## Example

The opening of a workshop video:

```text
[curious, conversational]

You find the perfect library on GitHub.

It does exactly what you need.

So you copy it into your project... and ship it.

[slight pause]

One question.

Were you allowed to?

[serious, measured]

If that repository has no licence...

the answer is no.
```

And a close:

```text
[excited, deliberate, final emphasis]

So before you ship it...

ask the question.

Whose code...

is it anyway?
```
