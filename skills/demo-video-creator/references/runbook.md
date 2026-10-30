# Runbook: produce a narrated demo/trailer video from real captured footage

Paste this whole document as the first message of a **fresh** Claude Code session. It is
self-contained. Fill in the placeholders below and nothing else needs to change.

```
TARGET TO RECORD: TARGET PUT HERE        (a URL to a live site/app, or a local dev server URL)
WHAT IT SHOULD SHOW: BEATS PUT HERE      (the sequence of things to click through / show off)
NARRATION SCRIPT: SCRIPT PUT HERE        (the voiceover text, or "none" for a silent/music-only cut)
```

Everything from here is instructions for the agent carrying out the production.

---

## The one rule

**If there's a voiceover, the voiceover is the clock.** The final timeline runs on voiceover
time, and the voiceover is never cut or re-timed to fit the footage. Everything else bends to
it instead: animated scenes are keyed to its word timestamps, live-app actions are scheduled
on its times, and slow parts of a live recording (page loads, an LLM response, any real wait)
are the things that get cut out of the final edit — not the narration. For a music/SFX-only
cut with no voiceover, the music bed plays this role instead: pick its length first, then fit
footage to it.

## Ground rules — read before doing anything

- **Real captured footage, always. Never a screenshot slideshow.** The picture must be genuine,
  continuous motion captured from the running site/app/game — a real cursor moving, a real page
  reacting, real animation — not a sequence of static screenshots with pans/zooms (a "Ken Burns"
  slideshow) standing in for video. This is a hard rule, not a time-pressure shortcut: a cheaper
  slideshow is **not** an acceptable fallback even under a deadline. If capturing real footage is
  genuinely impossible (no running build, no browser access), stop and tell the user why, rather
  than substituting a slideshow silently.
- **Real audio where the thing being shown has real audio.** If the target has its own sound
  (game SFX, music, a video clip with dialogue), capture that audio live during the same
  recording pass — tap the page's actual `AudioContext`/`<audio>` graph (see Step 3) — rather
  than faking it with generic stock sound.
- **Narration, music beds, and SFX layered on top are fine and expected.** The rule above is
  about the *picture* (and about audio the target itself produces) being real; a synthesized
  voiceover, a generated ambient music bed, or added one-shot SFX (clicks, whooshes, chimes) are
  a normal and expected part of a polished cut — they layer on top of, not instead of, real
  captured footage.
- **One continuous take per "scene", cut together afterward.** Don't try to record the whole
  video in one single take with every transition baked in live — record clean continuous
  footage per scene/flow, then cut, time, and mix it together in the assembly step. This keeps
  retakes cheap (re-record one broken scene, not the whole video) and keeps the timing-sync
  logic simple.
- **Sync action to narration with anchors, not fixed sleeps.** Scripted actions during
  recording are timed relative to *named anchors* tied to real voiceover timestamps (Step 3's
  `mark`/`at` pattern), not guessed-at fixed delays — otherwise the cut and the narration drift
  apart the moment either one changes.
- **Use the product's own real logos and brand colors.** Take official logos from the product
  itself (its site, its repo's assets) and build animated scenes in its own theme — never
  redraw a logo from memory and never default to a generic purple "AI gradient" look when the
  product has its own identity.
- **Never invent a claim or a number.** Every line in the narration script must be something
  that's actually true and that the recording actually demonstrates. If a claim can't be
  verified against the real app/game, cut the line rather than ship it unverified.
- **Everything here needs `ffmpeg`/`ffprobe` on PATH, Node with Playwright installed somewhere
  reachable, and (optionally) Python with `faster-whisper` for captions and an ElevenLabs API
  key for synthesized narration/music/SFX.** Check these work before starting — don't discover
  one is missing halfway through a recording pass.
- **Ask the placeholders' worth of detail once, as a batch, if anything is ambiguous**, then
  record and build straight through without further check-ins. Show a finished cut, don't
  negotiate every beat.

---

## Step 0 — Intake and shot planning

From `TARGET TO RECORD`, `WHAT IT SHOULD SHOW`, and `NARRATION SCRIPT`, work out and (if
genuinely ambiguous) ask once, as a single batch:

1. **Is this a live URL, a local dev server the agent needs to start, or a packaged app/game?**
   If it's a game built with the zero-asset-pipeline stack from the
   `snapchat-web-lens-creator` skill, the target is just `http://localhost:<port>` once
   `npm run serve` is running.
2. **Does the target produce its own sound that matters** (game SFX/music, a clip with
   dialogue)? If yes, Step 3's audio tap is required, not optional.
3. **Roughly how long should the final cut be**, and is there a hard size/format constraint
   (e.g. a Snapchat Lens preview video, which wants a short 5–10s vertical-friendly clip).
   Narrated explainers and demos default to **3 to 5 minutes**; longer only when the topic
   needs the depth, stated up front. This drives the shot list's total duration.
4. **Is there a real voiceover script, or is this music/SFX-only?** With no script yet, write
   one with the `demo-video-script-creator` skill first. If there's a script:
   - Who's recording it — the user, or should it be synthesized? Step 5 decides this from
     whether the API key can use the voice.
   - Voice/person: ask once if it matters (e.g. first-person "I built..." vs. "we built...")
     and hold to it consistently rather than drifting mid-script.
5. **Does the subject have its own brand** (a product with a logo/color scheme)? If so, pull
   its real logo and colors rather than inventing a generic look (see Ground rules).

If there's a voiceover script, write it with real structure before recording anything —
typically: the problem (why this matters), the subject itself, what it actually does, the live
demonstration (the bulk of the runtime), the close/call-to-action. A rough pacing guide for
synthesized narration: about 2.2–2.8 spoken words per second (plan at 2.5), so a 4-minute cut
needs roughly 600 words. The `demo-video-script-creator` skill has the full sizing rules.

Break `WHAT IT SHOULD SHOW` into an ordered list of **scenes**: some may be live-app capture
(Step 3), some may be animated explainer scenes with no live app in them at all (Step 2,
optional — problem statements, concept diagrams, an end card). This list drives everything
after it.

---

## Step 1 — Prerequisites check

```bash
ffmpeg -version          # must succeed; if missing, stop and tell the user to install it
node -e "require.resolve('@playwright/test')" --prefix <some/node/project/with/it/installed>
```

If no project on disk already has `@playwright/test`, install it in a scratch project
(`npm init -y && npm i -D @playwright/test && npx playwright install chromium`) rather than
polluting the target project's own `package.json`.

If captions or synthesized narration are wanted, also check:

```bash
python -c "import faster_whisper"   # for captions from a voiceover track
```

and confirm an ElevenLabs API key is available (ask the user for it, read it from an env var,
or from wherever they keep project secrets — never print it back).

---

## Step 2 — Animated explainer scenes (optional — skip if every scene is live-app capture)

For beats that aren't the live app itself (a problem statement, a concept recap, an end card),
build one HTML file with one `<section class="scene">` per scene, rendered frame-exact rather
than captured live, since there's nothing live to capture:

- **Layout**: 1920×1080 per scene. Use the subject's own theme (real colors, real font, real
  logo) — see the Ground rules on brand.
- **Timing**: every animation uses an absolute `animation-delay` in *scene-local* seconds,
  computed as `(voiceover time of the word it illustrates) − (this scene's start time on the
  voiceover clock)`. This is what makes "the one rule" work for non-live scenes: the scene's
  internal animation is pre-baked to match the narration exactly, because it's rendered to
  fixed timestamps rather than reacting live.
- **Required hooks** the render script needs:
  - `window.sceneReady` — a promise/flag that resolves once fonts and images have loaded, so
    rendering doesn't start on a half-painted frame.
  - `window.setScene(name)` — sets `document.body.dataset.scene`, selecting which section is
    visible.
  - `window.seek(t)` — pauses every `document.getAnimations()` and sets each one's
    `currentTime` to `t`, so the renderer can step to an exact timestamp rather than playing
    in real time.
- **Rendering**: a small script takes a scene name + duration, seeks through it at a fixed fps
  (typically 60) via `window.seek()`, screenshots each step with Playwright, and pipes the
  frames into `ffmpeg` to produce `work/scene-<name>.mp4`. Also support rendering just a handful
  of preview frames at specific timestamps (for reviewing before a full render).
- **Gotcha**: a keyframe animation that sets `transform` (pop, rise, slam, etc.) **overwrites**
  any `transform: translate(-50%, -50%)` used to center the element — the element visibly jumps
  off-center the instant the animation starts. Center with `left`/`top`/`margin` instead of a
  centering `transform` on anything that will later be animated with `transform`.
- **Author every timing in absolute voiceover seconds.** Put `data-in="47.28"` (and optional
  `data-out`, `data-a` for the animation name, `data-fx` + `data-fx-at` for a later state change
  such as a highlight) on each element, give each `<section>` a `data-start`, and let one small
  script turn them into `animation: <name> <dur>s <ease> <in - start>s both`. Then the word
  timestamps from the transcript paste straight in, and re-timing a scene is a find-and-replace.
  An exit animation must use `forwards`, not `both`, or its first keyframe overrides the entry
  animation before the exit starts.
- **Use the subject's own site as the design source.** Screenshot it first, take its colour
  tokens and fonts (download the font files so captions can use them too), and repeat its top
  bar in every scene so explainer scenes and live footage read as one video.
- **A CLI demo is real output, replayed.** Run the commands for real in a scratch copy of the
  project (never the user's working copy), capture their exact stdout, and type them into a
  terminal panel in the scenes file. Every line on screen must be output that actually printed;
  say in the hand-off that the terminal is a replay of a real run.
- **Always review preview frames before the full render.** Render a handful of PNGs at key
  timestamps, tile them into one contact-sheet image, and look at it before spending the time
  on a full 60fps render of a scene that turns out to have a layout bug.

---

## Step 3 — Record each live-app scene with real capture (Playwright + CDP screencast)

This is the core technique for anything that's actually live and interactive: a headless
Chromium page, continuously captured frame by frame over the Chrome DevTools Protocol (not
periodic screenshots), with a drawn cursor so clicks/drags read clearly on camera, and — when
the target has its own audio — a tap into the page's real audio graph recorded alongside.

One recording script per scene, structured like this (adapt the selectors/actions/`AT()`
anchors to the actual target; everything else is reusable as-is):

```js
// record.mjs <outDir> — captures one continuous scene as JPEG frames + markers.json.
import { mkdirSync, writeFileSync } from 'node:fs';
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
const { chromium } = require('@playwright/test');

const out = process.argv[2];
mkdirSync(`${out}/frames`, { recursive: true });
const TARGET = 'TARGET PUT HERE';
const ZOOM = 1.3333; // renders a 1440x810 layout crisp at a 1920x1080 capture, if useful

// A drawn cursor so the recording reads clearly — the real mouse is invisible in headless
// capture. Includes a click-ring flash and an optional "spotlight" the recorder can toggle
// on a specific element to draw the viewer's eye there — never added to the app itself.
const CURSOR = `(() => {
  const Z = ${ZOOM};
  const zoom = () => { if (document.documentElement) document.documentElement.style.zoom = String(Z); };
  zoom(); addEventListener('load', zoom);
  const install = () => {
    zoom();
    if (document.getElementById('rec-cursor')) return;
    const c = document.createElement('div');
    c.id = 'rec-cursor';
    c.innerHTML = '<svg width="26" height="26" viewBox="0 0 24 24"><path d="M4 2.5l15 9.2-6.6 1.5 3.9 7.3-3 1.6-3.9-7.4L4.6 19z" fill="#141412" stroke="#fff" stroke-width="1.6" stroke-linejoin="round"/></svg><span></span>';
    Object.assign(c.style, { position: 'fixed', left: '0', top: '0', zIndex: '2147483647', pointerEvents: 'none', transform: 'translate(-100px,-100px)' });
    const ring = c.querySelector('span');
    Object.assign(ring.style, { position: 'absolute', left: '-14px', top: '-14px', width: '36px', height: '36px', borderRadius: '50%', border: '3px solid #ff5a1f', opacity: '0', transform: 'scale(.4)' });
    document.documentElement.appendChild(c);
    addEventListener('mousemove', (e) => { c.style.transform = 'translate(' + e.clientX / Z + 'px,' + e.clientY / Z + 'px)'; }, true);
    addEventListener('mousedown', () => { ring.animate([{ opacity: .9, transform: 'scale(.4)' }, { opacity: 0, transform: 'scale(1.6)' }], { duration: 450, easing: 'ease-out' }); }, true);
  };
  if (document.readyState === 'loading') addEventListener('DOMContentLoaded', install); else install();
  // window.__spotlight(selector | null) — highlight one element, recorder-only styling.
  const style = document.createElement('style');
  style.textContent = '.__rec-spotlight{box-shadow:0 0 0 3px #ff5a1f,0 0 0 100vmax rgba(10,10,15,.35) !important;transition:box-shadow .25s}';
  document.documentElement.appendChild(style);
  window.__spotlight = (sel) => {
    document.querySelectorAll('.__rec-spotlight').forEach((el) => el.classList.remove('__rec-spotlight'));
    if (sel) document.querySelector(sel)?.classList.add('__rec-spotlight');
  };
})()`;

// Only needed when the target produces its own sound worth capturing live.
const AUDIO_TAP = `(() => {
  const Ctx = window.AudioContext || window.webkitAudioContext;
  if (!Ctx) return;
  const capCtx = new Ctx();
  const dest = capCtx.createMediaStreamDestination();
  function SharedCtx() { return capCtx; }
  SharedCtx.prototype = Ctx.prototype;
  window.AudioContext = SharedCtx;
  window.webkitAudioContext = SharedCtx;
  const OrigAudio = window.Audio;
  const tapped = new WeakSet();
  function tapEl(el) {
    if (tapped.has(el)) return;
    tapped.add(el);
    try { const src = capCtx.createMediaElementSource(el); src.connect(capCtx.destination); src.connect(dest); } catch {}
  }
  window.Audio = function (...args) { const el = new OrigAudio(...args); tapEl(el); return el; };
  window.Audio.prototype = OrigAudio.prototype;
  window.__startCapture = () => {
    const rec = new MediaRecorder(dest.stream, { mimeType: 'audio/webm;codecs=opus' });
    const chunks = [];
    rec.ondataavailable = (e) => { if (e.data.size) chunks.push(e.data); };
    window.__capRecorder = rec; window.__capChunks = chunks;
    rec.start(250);
  };
  window.__stopCapture = () => new Promise((resolve) => {
    window.__capRecorder.onstop = async () => resolve(await new Blob(window.__capChunks).arrayBuffer());
    window.__capRecorder.stop();
  });
})()`;

const b = await chromium.launch({ channel: 'chromium' });
const ctx = await b.newContext({ viewport: { width: 1920, height: 1080 } });
await ctx.addInitScript(CURSOR);
await ctx.addInitScript(AUDIO_TAP); // omit this line if the target has no relevant audio
const p = await ctx.newPage();
p.setDefaultTimeout(30000);
await p.goto(TARGET);
await p.evaluate(() => window.__startCapture?.()); // omit if no audio tap

// --- CDP screencast: real continuous frame capture, not screenshots -----------------------
const cdp = await ctx.newCDPSession(p);
const frames = [];
cdp.on('Page.screencastFrame', async ({ data, metadata, sessionId }) => {
  const i = frames.length;
  frames.push({ i, t: metadata.timestamp });
  writeFileSync(`${out}/frames/${String(i).padStart(6, '0')}.jpg`, Buffer.from(data, 'base64'));
  await cdp.send('Page.screencastFrameAck', { sessionId }).catch(() => {});
});
await cdp.send('Page.startScreencast', { format: 'jpeg', quality: 90, maxWidth: 1920, maxHeight: 1080, everyNthFrame: 1 });

// --- Anchor-timing: sync scripted actions to real voiceover timestamps --------------------
// mark(name) records when something actually happened. at(vo) waits until a given voiceover
// timestamp, counted from the most recent relevant anchor — switch which anchor it counts from
// after a planned cut (e.g. an LLM wait that gets edited out), so times after the cut are still
// expressed in the original voiceover's absolute seconds.
const markers = {};
const now = () => Date.now() / 1000;
const mark = (name) => { markers[name] = now(); console.log('mark', name); };
let anchor = 'start';
const since = (anchorName) => { anchor = anchorName; };
const at = async (vo) => {
  const wait = (markers[anchor] + vo - now()) * 1000;
  if (wait > 0) await p.waitForTimeout(wait);
  else console.log(`late by ${(-wait / 1000).toFixed(2)}s at VO ${vo}`); // give more lead time next take if this fires
};

// --- Eased mouse movement so drags/clicks read as deliberate, not teleporting -------------
let pos = { x: 960, y: 540 };
const ease = (t) => (t < 0.5 ? 2 * t * t : 1 - (-2 * t + 2) ** 2 / 2);
async function glide(target, ms = 600) {
  if (typeof target.boundingBox === 'function') {
    const seen = await target.boundingBox();
    if (seen && (seen.y + seen.height > 1080 - 70 || seen.y < 90)) {
      await target.evaluate((el) => el.scrollIntoView({ behavior: 'smooth', block: 'center' }));
      await p.waitForTimeout(650);
    }
  }
  const box = typeof target.boundingBox === 'function' ? await target.boundingBox() : target;
  const to = box.width ? { x: box.x + box.width / 2, y: box.y + box.height / 2 } : box;
  const from = { ...pos };
  const start = Date.now();
  for (;;) {
    const k = Math.min(1, (Date.now() - start) / ms);
    await p.mouse.move(from.x + (to.x - from.x) * ease(k), from.y + (to.y - from.y) * ease(k));
    if (k >= 1) break;
    await p.waitForTimeout(12);
  }
  pos = to;
}
async function tap(target, ms) { await glide(target, ms); await p.mouse.down(); await p.waitForTimeout(70); await p.mouse.up(); mark(`click@${Object.keys(markers).length}`); }

// --- The actual scene: replace this block with the real beats for this scene --------------
// Give each narration line something on screen to look at: glide/spotlight the thing being
// named, right as it's said. e.g.:
//   mark('start');
//   await at(1.2); await tap(p.getByRole('button', { name: /play/i }), 600);
mark('start');
mark('stop');

await cdp.send('Page.stopScreencast');
await p.waitForTimeout(300);
const audioBuf = await p.evaluate(() => window.__stopCapture?.()).catch(() => null); // omit if no audio tap
if (audioBuf) writeFileSync(`${out}/audio.webm`, Buffer.from(audioBuf));
writeFileSync(`${out}/markers.json`, JSON.stringify({ markers, frames }, null, 1));
console.log('frames', frames.length);
await b.close();
```

**Real-world gotchas worth knowing before you hit them:**

- **The screencast stops sending frames once the page goes still.** A quiet beat (e.g. waiting
  on a result) can make the take end a fraction early, short of the real wall-clock duration.
  The assembly step pads each live-app segment's tail
  (`tpad=stop_mode=clone:stop_duration=3`) so the concat doesn't come up short.
- **Canvas-based libraries ignore CSS zoom.** Anything rendering to `<canvas>` (force-directed
  graphs, custom charts) maps pointer events in *unzoomed* page coordinates even while `ZOOM`
  scales everything else visually. Glide the drawn cursor to the zoomed *visual* position for
  the shot, then click using the unzoomed coordinate math
  (`box.x + fractionAcross * canvas.clientWidth`, etc.) — don't assume one coordinate space
  for both.
- **A variable-latency step (an LLM call, a slow query, anything with real wait time) needs
  explicit handling, not a guessed sleep:** `mark()` the click that triggers it, wait for the
  actual result to appear (a real `waitFor`, not a timeout), then `mark()` the result landing.
  The assembly step then cuts straight from "triggered" to "result appeared," and the delivery
  notes to the user say honestly that the wait was cut (e.g. "the ~30s model response is cut").
- **Validate what actually came back against what the narration claims it will show.** If the
  app's live output doesn't match the specific claim the voiceover makes, don't ship the
  mismatch — retry the action inside the cut (a handful of attempts, invisible in the final
  edit) until it matches, and log what came back so it can be checked by eye afterward.
- **Never type secrets into the page during a recording.** If a field needs a saved credential,
  leave it empty so the app's own stored value is used, rather than typing a real key on camera.
- **Never click a destructive or irreversible control while recording** (delete, "sync again"
  on live data, anything that mutates real external state) — glide near it and narrate around
  it instead if it needs to be shown.
- **Pick selectors from the live DOM, not the repo source.** The deployed site can lag the
  source (an id that exists in the code may not be deployed yet), and section ids often sit on
  headings rather than sections. Dump the live page's ids first and target
  `xpath=ancestor::section[1]` of a heading id where needed.
- **Nothing to point at below the fold.** `glide()` doesn't scroll; scroll first (a smooth
  `scrollBy`) so the element and the spotlight sit above where captions will go.
- **Point at external links; don't actually open them** — a recording that navigates away loses
  the thread and the drawn cursor/spotlight state.

Run it once per scene: `node record.mjs work/scene-01`, `node record.mjs work/scene-02`, ...
preferably in the background with output logged to a file, since a take can run for minutes.
Watch the console for `frames N` at the end and for any `late by Xs` lines — either means the
take needs another pass with more lead time before the next scene is recorded.

---

## Step 4 — Convert each captured scene to a fixed-fps video

CDP screencast frames arrive at variable, real timestamps. Convert to a constant frame rate so
cuts and audio sync land exactly where planned:

```python
# frames2video.py <sceneDir> — turns variable-timing JPEG frames into a 60fps CFR video.
import json, subprocess, sys
rec = sys.argv[1]
d = json.load(open(f"{rec}/markers.json"))
fr = d["frames"]
lines = ["ffconcat version 1.0"]
for i, f in enumerate(fr):
    dur = (fr[i + 1]["t"] - f["t"]) if i + 1 < len(fr) else 0.1
    lines += [f"file 'frames/{f['i']:06d}.jpg'", f"duration {dur:.4f}"]
lines.append(f"file 'frames/{fr[-1]['i']:06d}.jpg'")
open(f"{rec}/frames.ffconcat", "w").write("\n".join(lines))
subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", f"{rec}/frames.ffconcat",
                "-vf", "fps=60,format=yuv420p", "-c:v", "libx264", "-preset", "medium", "-crf", "15",
                f"{rec}/scene.mp4"], check=True)
print("scene.mp4 done")
```

Run per scene: `python -I frames2video.py work/scene-01`. Each scene directory now has a clean
`scene.mp4` (and `audio.webm` if a scene had its own captured sound).

---

## Step 5 — Narration, music, SFX, and captions (skip anything not wanted)

**Voiceover**: decide who makes it, in this order, and tell the user which path you took:

1. Find the key: `ELEVENLABS_API_KEY` in the environment, else in a local `.env` (load it
   without printing it, and check `git check-ignore .env` — add it to `.gitignore` if not). No
   key: ask the user for one once.
2. Check the voice: `GET /v1/voices/<voice_id>` must return 200. Default voice is Jeremy
   (`bkWmSiLbVbuhntmf2Kw7`, Young, Confident, American Male) unless the user names another.
3. Check the quota: `GET /v1/user/subscription` gives `character_count` / `character_limit`;
   the script's character count (tags included) must fit in what's left.
4. Prove access with a tiny generation (a two-word line, `eleven_v3`). On the free plan, library
   voices fail here with `402 paid_plan_required` even though step 2 passed.
5. All four pass: generate the voiceover (below). Any fails, or the user gives no key: hand over
   the script and say plainly — "Your ElevenLabs API key isn't available or can't use this
   voice, so please record this script in ElevenLabs (voice: Jeremy, model v3) and send me the
   .mp3." Then wait for the file.

If the user records their own narration, just collect the audio file (any format ffmpeg reads)
and follow it exactly as recorded, even where it drifted slightly from the written script — the
recorded audio is the real source of truth, not the draft text. If it should be synthesized,
use ElevenLabs:

```python
# eleven.py <music|sfx|tts> <out-file> ...args — minimal ElevenLabs client, key never printed.
import json, sys, urllib.request, urllib.error

def key():
    import os
    k = os.environ.get("ELEVENLABS_API_KEY")
    if not k:
        raise SystemExit("ELEVENLABS_API_KEY not set")
    return k

def post(path, body, out, accept="audio/mpeg"):
    req = urllib.request.Request(
        "https://api.elevenlabs.io" + path, data=json.dumps(body).encode(),
        headers={"xi-api-key": key(), "Content-Type": "application/json", "Accept": accept}, method="POST")
    with urllib.request.urlopen(req, timeout=600) as r:
        open(out, "wb").write(r.read())
    print("ok", out)

if __name__ == "__main__":
    kind, out = sys.argv[1], sys.argv[2]
    if kind == "music":
        post("/v1/music", {"prompt": sys.argv[3], "music_length_ms": int(sys.argv[4])}, out)
    elif kind == "sfx":
        post("/v1/sound-generation", {"text": sys.argv[3], "duration_seconds": float(sys.argv[4]), "prompt_influence": 0.6}, out)
    elif kind == "tts":
        voice_id = sys.argv[4]
        # Delivery tags ([serious], [confident], [excited]) and "..." pauses only work with the
        # v3 model. Keep paragraphs short; one beat per paragraph.
        post(f"/v1/text-to-speech/{voice_id}", {"text": sys.argv[3], "model_id": "eleven_v3"}, out)
```

For a series (one channel, many videos), reuse the same set of beds and SFX across videos so
the channel has one recognisable sound; generate new ones only when a mood is missing.

Generate one or more short ambient music beds — for a longer cut, several beds matched to each
act (e.g. tense under a problem statement, bright under the product, light under the ending),
crossfaded between acts — plus any one-shot SFX the cut needs (whoosh at transitions, pop on
reveals, tick on list items, click at every logged recorder click, a hit on the final line).
Keep beds instrumental and low-key; they sit under the voice, never over it.

**Getting the music level right — measure it, don't guess:**

1. Render the ducked bed on its own (silence the voice) and compare it against the voiceover
   with `ffmpeg -i <file> -af ebur128 -f null -`.
2. Target roughly **12 LU under the voice** (e.g. voice around -19 LUFS, bed around -31 LUFS,
   both measured before the final `loudnorm` pass).
   Measure the ducked bed on its own for one act, keyed by the voice:
   `ffmpeg -ss A -t D -i vo.mp3 -t D -i bed.wav -filter_complex "[0:a]asplit=2[v][k];[1:a]volume=-16dB[b];[b][k]sidechaincompress=threshold=0.05:ratio=3:attack=40:release=450:makeup=1[d];[v]anullsink;[d]ebur128[o]" -map "[o]" -f null -`
   and compare with the voice's own `ebur128` over the same span. Beds generated around
   -11 LUFS land ~11 LU under a -19 LUFS voice at `volume=-16dB`; `-12dB` was only ~7 LU under,
   which is not "subtle".
3. If a first attempt comes out inaudible in the pauses, that's usually too much gain
   reduction from the ducking compressor, not too little bed volume — loosen the
   `sidechaincompress` ratio (e.g. from `ratio=6` to `ratio=3`) before raising the bed's raw
   volume further.

**Captions** (only if there's a voiceover and captions are wanted): get word-level timestamps
with faster-whisper — CPU mode (`int8`) is fine for a short video, and giving the model an
`initial_prompt` with the subject's own proper nouns/jargon fixes most spelling mistakes before
they happen:

```python
# transcribe.py <audio> <out.json> [model] — word-level transcript for caption timing.
import json, sys
from faster_whisper import WhisperModel
src, out = sys.argv[1], sys.argv[2]
model = WhisperModel(sys.argv[3] if len(sys.argv) > 3 else "base.en", device="cpu", compute_type="int8")
prompt = "SUBJECT PUT HERE, and any proper nouns, product names, or jargon the voiceover uses."
segments, info = model.transcribe(src, word_timestamps=True, initial_prompt=prompt, vad_filter=False)
data = [{"s": round(s.start, 3), "e": round(s.end, 3), "text": s.text.strip(),
         "words": [{"w": w.word.strip(), "s": round(w.start, 3), "e": round(w.end, 3)} for w in s.words]}
        for s in segments]
json.dump({"duration": info.duration, "segments": data}, open(out, "w", encoding="utf-8"), indent=1)
```

Even with a good prompt, keep a small manual `FIX` dict in the captioning step for known
transcription slips (a mis-heard product name, a split compound word) — cheaper than re-running
transcription and catches things a prompt alone won't.

---

## Step 6 — Assemble the final cut

One script does the real work: cut each scene to length, concat them in order, mix all the
audio layers with ducking and loudness normalization, burn in captions if there are any, and
mux to a delivery file.

```python
# build.py <out.mp4> — edit the SHOTS list and AUDIO section for the actual cut, then run.
import json, subprocess

FPS = 60
def run(args): subprocess.run(["ffmpeg", "-v", "error", "-y", *args], check=True)

# ---- 1. Shot list: (sceneDir, src_start_s, src_end_s), in final order --------------------
SHOTS = [
    ("work/scene-01", 0.0, 6.0),
    ("work/scene-02", 0.0, 8.5),
    ("work/scene-03", 0.5, 7.0),
]
starts, t = [], 0.0
for src, a, b in SHOTS:
    starts.append(t); t += b - a
TOTAL = t
print(f"total {TOTAL:.2f}s")

# ---- 2. Cut and re-encode each shot to a consistent fps/pix_fmt, then concat -------------
# A live-app shot gets its tail padded so a screencast that went quiet near the cut point
# doesn't come up short of the planned duration (see Step 3's screencast-idle gotcha).
parts = []
for i, (src, a, b) in enumerate(SHOTS):
    out = f"work/seg{i:02d}.mp4"
    run(["-ss", f"{a:.3f}", "-i", f"{src}/scene.mp4", "-t", f"{b - a:.3f}", "-an",
         "-vf", f"fps={FPS},format=yuv420p,tpad=stop_mode=clone:stop_duration=3",
         "-c:v", "libx264", "-crf", "15", "-preset", "medium", out])
    parts.append(out)
open("work/parts.txt", "w").write("\n".join(f"file '{p}'" for p in parts))
run(["-f", "concat", "-safe", "0", "-i", "work/parts.txt", "-c", "copy", "work/video-silent.mp4"])

# ---- 3. Captions: build an .ass from word timings, lines of up to ~8 words, broken at ----
# punctuation once a line has 4+ words. Write a plain .vtt alongside it too, for platforms
# that want a sidecar caption file rather than burned-in text.

# ---- 4. Audio mix: voiceover + captured scene audio + music beds (ducked) + SFX ----------
# inputs, in order: 0 = voiceover (uncut — see "the one rule"), then captured scene audio.webm
# files, then each music bed, then each one-shot SFX file. Build the filter_complex to:
#   - trim/delay the voiceover and any captured scene audio onto the final timeline
#   - crossfade music beds between acts with afade/adelay, duck them under the voice with
#     sidechaincompress keyed by the voiceover
#   - place each SFX at its timestamp with its own gain via adelay (use the real click
#     timestamps logged in each scene's markers.json, mapped through the shot list's offsets)
#   - amix everything, then loudnorm=I=-14:TP=-1.5:LRA=11 for a consistent final level
run(["-i", "work/voiceover.mp3", "-i", "work/bed.wav",
     "-filter_complex", "[0:a]aresample=48000[vo];[1:a]volume=-16dB,aresample=48000[bed];"
                         "[bed][vo]sidechaincompress=threshold=0.05:ratio=3:attack=40:release=450:makeup=1[ducked];"
                         f"[vo][ducked]amix=inputs=2:normalize=0:duration=longest,atrim=0:{TOTAL:.2f},"
                         "loudnorm=I=-14:TP=-1.5:LRA=11[mix]",
     "-map", "[mix]", "-c:a", "pcm_s16le", "-ar", "48000", "work/mix.wav"])

# ---- 5. Final mux (burn in captions here with -vf "subtitles=work/captions.ass" if used) --
run(["-i", "work/video-silent.mp4", "-i", "work/mix.wav",
     "-c:v", "libx264", "-crf", "17", "-preset", "slow", "-pix_fmt", "yuv420p", "-r", str(FPS),
     "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-shortest", "OUT.mp4"])
print("done")
```

The shot list and audio mix are the one genuinely bespoke part of every video — fill in real
scene durations, real anchor-derived SFX timestamps (from each scene's `markers.json`), and the
actual voiceover cut points. Don't try to make this fully generic; adapt it per video the same
way a shot list in a real NLE timeline is bespoke per edit.

---

## Step 7 — QA before calling it done

- [ ] `ffprobe` confirms the resolution, frame rate, and total duration match what was planned
      (within ~0.1s).
- [ ] A contact sheet of the whole video (sample a frame every few seconds, tile into a grid)
      shows no broken frames, no layout glitches, nothing unintended on screen.
- [ ] Full-size frames at every transition and every key beat look right individually, not just
      in the contact sheet thumbnail.
- [ ] Whatever the narration claims the app/game shows is actually what's on screen at that
      timestamp — read back the logged values from Step 3's live recording, don't assume.
- [ ] Integrated loudness is around -14 LUFS; the music bed is audible in pauses and sits under
      the voice, not over it (re-check with `ebur128` if in doubt).
- [ ] Captions (if any) are spelled correctly and never cover the thing being pointed at.
- [ ] **Nothing secret is visible on screen** — keys, tokens, personal data, internal URLs.
- [ ] Clean up scratch state: scene directories, intermediate `seg*.mp4`/`parts.txt`/`mix.wav`
      files, and any dev server started to serve the target.

## Step 8 — Hand off

Report the output file's path, duration, and size. State plainly anything that was cut or
staged (a long LLM wait edited out, a retried action) and any known imperfection — don't let
the user discover a cut wait on their own. Note what's left for them (approving the cut,
swapping in their own voiceover if a placeholder was synthesized, where it gets uploaded).
Never upload, publish, or submit it anywhere without being asked.

Also write `out/youtube.md`, ready to paste into YouTube Studio:

- **Files:** the video (duration, resolution), `thumbnail.png` (1280x720, rendered from an HTML
  page in the video's own theme), and the `.vtt` captions.
- **Title:** one recommended, under ~70 characters, the topic's search words first; plus two
  alternatives.
- **Description:** the hook in one or two sentences, what the video covers, what was built and
  how to try it, then links (repo, site, related issues/posts; a `<add after publishing>`
  placeholder for anything not public yet), then **Chapters** with `0:00`-style timestamps taken
  from the final timeline's act starts, then 4–6 hashtags.
- **Tags:** 12–20 comma-separated search terms, specific to general.
- **Settings:** category (Science & Technology), language and captions file, not made for kids,
  visibility left to the user.

---

## Windows gotchas

- Git Bash-style paths (`/e/...`) don't resolve in Windows Python — use `E:/...` forward-slash
  paths throughout, and set `PYTHONIOENCODING=utf-8` before printing anything non-ASCII.
- Write Python/JS file edits via a **quoted** heredoc (`<<'EOF'`); an unquoted heredoc lets the
  shell mangle `\n` escapes inside the script.
- A missing input file (wrong extension, typo'd path) makes `ffmpeg` exit with an unhelpful
  large status code rather than a clear error — check every input path exists before blaming
  the filter graph.
- To free a port a leftover dev server left open: find and stop the process bound to it rather
  than guessing a PID (e.g. via `netstat`/`Get-NetTCPConnection`-style lookup, then stop that
  specific process).
- Run long renders, recordings, and builds in the background and wait for them to finish rather
  than blocking the session on a multi-minute `ffmpeg`/Playwright run.

---

## One-shot checklist

```
[ ] Step 0 — target, shot beats, narration script/voice understood; ambiguity asked once
[ ] Step 1 — ffmpeg + Playwright (+ faster-whisper/ElevenLabs if needed) confirmed working
[ ] Step 2 — animated explainer scenes built and frame-exact rendered (skip if none needed)
[ ] Step 3 — each live-app scene recorded as real CDP-captured footage (+ real audio if relevant)
[ ] Step 4 — each captured scene converted to a fixed-fps CFR scene.mp4
[ ] Step 5 — narration/music/SFX collected or generated, levels measured; captions transcribed
[ ] Step 6 — shot list cut, concatenated, audio mixed+ducked+normalized, final mux done
[ ] Step 7 — QA checklist run in full, scratch state cleaned up
[ ] Step 8 — handed back with any cuts/imperfections disclosed, youtube.md + thumbnail written;
              nothing published
```
