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
  recording pass — tap the page's actual `AudioContext`/`<audio>` graph (see Step 2) — rather
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
  logic (Step 2's anchors) simple.
- **Sync action to narration with anchors, not fixed sleeps.** If there's a voiceover, scripted
  actions during recording should be timed relative to *named anchors* tied to real voiceover
  timestamps (see Step 2's `mark`/`until` pattern), not guessed-at fixed delays — otherwise the
  cut and the narration drift apart the moment either one changes.
- **Everything here needs `ffmpeg` on PATH, Node with Playwright installed somewhere reachable,
  and (optionally) Python with `faster-whisper` for captions and an ElevenLabs API key for
  synthesized narration/music/SFX.** Check `ffmpeg -version` and resolve a working Playwright
  install (`require.resolve('@playwright/test')` against *some* project on disk, or install one
  fresh) before starting — don't discover these are missing halfway through a recording pass.
- **Ask the three placeholders' worth of detail once, as a batch, if anything is ambiguous**,
  then record and build straight through without further check-ins. Show a finished cut, don't
  negotiate every beat.

---

## Step 0 — Intake and shot planning

From `TARGET TO RECORD`, `WHAT IT SHOULD SHOW`, and `NARRATION SCRIPT`, work out and (if
genuinely ambiguous) ask once:

1. **Is this a live URL, a local dev server the agent needs to start, or a packaged app/game?**
   If it's a game built with the zero-asset-pipeline stack from the
   `snapchat-web-lens-creator` skill, the target is just `http://localhost:<port>` once
   `npm run serve` is running.
2. **Does the target produce its own sound that matters** (game SFX/music, a clip with
   dialogue)? If yes, Step 2's audio tap is required, not optional.
3. **Roughly how long should the final cut be**, and is there a hard size/format constraint
   (e.g. a Snapchat Lens preview video, which wants a short 5–10s vertical-friendly clip; a
   product demo might run 60–120s). This drives the shot list's total duration.
4. **Is there a real voiceover script, or is this music/SFX-only?** If there's a script, decide
   whether the user will record it themselves or wants it synthesized (Step 4).

Break `WHAT IT SHOULD SHOW` into an ordered list of **scenes** — each scene is one continuous
recording pass showing one coherent flow (e.g. "title screen → tap to start", "a level of
gameplay with a power-up", "the game-over screen and leaderboard"). This list drives Step 2.

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

and confirm an ElevenLabs API key is available (ask the user for it, or read it from wherever
they keep project secrets — never print it back).

---

## Step 2 — Record each scene with real capture (Playwright + CDP screencast)

This is the core technique: a headless/headed Chromium page, continuously captured frame by
frame over the Chrome DevTools Protocol (not periodic screenshots), with a drawn cursor so
clicks/drags read clearly on camera, and — when the target has its own audio — a tap into the
page's real audio graph recorded alongside.

One recording script per scene, structured like this (adapt the selectors/actions to the
actual target; everything else is reusable as-is):

```js
// record.mjs <outDir> — captures one continuous scene as JPEG frames + markers.json.
import { mkdirSync, writeFileSync } from 'node:fs';
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
const { chromium } = require('@playwright/test');

const out = process.argv[2];
mkdirSync(`${out}/frames`, { recursive: true });
const TARGET = 'TARGET PUT HERE';

// A drawn cursor so the recording reads clearly — injected before any page script runs.
const CURSOR = `(() => {
  const install = () => {
    if (document.getElementById('rec-cursor')) return;
    const c = document.createElement('div');
    c.id = 'rec-cursor';
    c.innerHTML = '<svg width="26" height="26" viewBox="0 0 24 24"><path d="M4 2.5l15 9.2-6.6 1.5 3.9 7.3-3 1.6-3.9-7.4L4.6 19z" fill="#141412" stroke="#fff" stroke-width="1.6" stroke-linejoin="round"/></svg>';
    Object.assign(c.style, { position: 'fixed', left: '0', top: '0', zIndex: '2147483647', pointerEvents: 'none', transform: 'translate(-100px,-100px)' });
    document.documentElement.appendChild(c);
    addEventListener('mousemove', (e) => { c.style.transform = 'translate(' + e.clientX + 'px,' + e.clientY + 'px)'; }, true);
  };
  if (document.readyState === 'loading') addEventListener('DOMContentLoaded', install); else install();
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
const markers = {};
const now = () => Date.now() / 1000;
const mark = (name) => { markers[name] = now(); console.log('mark', name); };
const until = async (anchor, rel) => { const wait = (markers[anchor] + rel - now()) * 1000; if (wait > 0) await p.waitForTimeout(wait); };

// --- Eased mouse movement so drags/clicks read as deliberate, not teleporting -------------
let pos = { x: 960, y: 540 };
const ease = (t) => (t < 0.5 ? 2 * t * t : 1 - (-2 * t + 2) ** 2 / 2);
async function glide(target, ms = 600) {
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
async function tap(target, ms) { await glide(target, ms); await p.mouse.down(); await p.waitForTimeout(70); await p.mouse.up(); }

// --- The actual scene: replace this block with the real beats for this scene --------------
mark('start');
// e.g.: await until('start', 1.2); await tap(p.getByRole('button', { name: /play/i }), 600);
// Keep each scene a single coherent flow; cut scenes together in Step 5, not here.
mark('stop');

await cdp.send('Page.stopScreencast');
await p.waitForTimeout(300);
const audioBuf = await p.evaluate(() => window.__stopCapture?.()).catch(() => null); // omit if no audio tap
if (audioBuf) writeFileSync(`${out}/audio.webm`, Buffer.from(audioBuf));
writeFileSync(`${out}/markers.json`, JSON.stringify({ markers, frames }, null, 1));
console.log('frames', frames.length);
await b.close();
```

Run it once per scene: `node record.mjs work/scene-01`, `node record.mjs work/scene-02`, ...
Watch the console for `frames N` at the end — a suspiciously low count means the capture
dropped frames (page too heavy, or the machine under load); re-record rather than ship a
jerky take.

---

## Step 3 — Convert each scene to a fixed-fps video

CDP screencast frames arrive at variable, real timestamps. Convert to a constant frame rate
so cuts and audio sync land exactly where planned:

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

Run per scene: `python -I frames2video.py work/scene-01`. Each scene directory now has a
clean `scene.mp4` (and `audio.webm` if a scene had its own captured sound).

---

## Step 4 — Narration, music, and SFX (skip anything not wanted)

**Voiceover**: if the user is recording their own narration, just collect the audio file (any
format ffmpeg reads). If it should be synthesized, use ElevenLabs:

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
        post(f"/v1/text-to-speech/{voice_id}", {"text": sys.argv[3], "model_id": "eleven_multilingual_v2"}, out)
```

Generate a short ambient music bed (or two, to crossfade across a longer cut) and any one-shot
SFX the cut needs (clicks, whooshes, chimes). Keep beds instrumental and low-key — they sit
under narration and real captured audio, not over it.

**Captions** (only if there's a voiceover and captions are wanted): get word-level timestamps
with faster-whisper, CPU mode is fine for a short video:

```python
# transcribe.py <audio> <out.json> [model] — word-level transcript for caption timing.
import json, sys
from faster_whisper import WhisperModel
src, out = sys.argv[1], sys.argv[2]
model = WhisperModel(sys.argv[3] if len(sys.argv) > 3 else "base.en", device="cpu", compute_type="int8")
segments, info = model.transcribe(src, word_timestamps=True, vad_filter=False)
data = [{"s": round(s.start, 3), "e": round(s.end, 3), "text": s.text.strip(),
         "words": [{"w": w.word.strip(), "s": round(w.start, 3), "e": round(w.end, 3)} for w in s.words]}
        for s in segments]
json.dump({"duration": info.duration, "segments": data}, open(out, "w", encoding="utf-8"), indent=1)
```

---

## Step 5 — Assemble the final cut

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
parts = []
for i, (src, a, b) in enumerate(SHOTS):
    out = f"work/seg{i:02d}.mp4"
    run(["-ss", f"{a:.3f}", "-i", f"{src}/scene.mp4", "-t", f"{b - a:.3f}", "-an",
         "-vf", f"fps={FPS},format=yuv420p", "-c:v", "libx264", "-crf", "15", "-preset", "medium", out])
    parts.append(out)
open("work/parts.txt", "w").write("\n".join(f"file '{p}'" for p in parts))
run(["-f", "concat", "-safe", "0", "-i", "work/parts.txt", "-c", "copy", "work/video-silent.mp4"])

# ---- 3. Audio mix: voiceover + captured scene audio + music beds (ducked) + SFX ----------
# inputs, in order: 0 = voiceover (or omit if none), then captured scene audio.webm files,
# then music bed(s), then each one-shot SFX file. Build the filter_complex to:
#   - trim/delay the voiceover and any captured scene audio onto the final timeline
#   - crossfade/duck music beds under the voice with sidechaincompress
#   - place each SFX at its timestamp with its own gain via adelay
#   - amix everything, then loudnorm=I=-14:TP=-1.5:LRA=11 for a consistent broadcast level
# This part is genuinely bespoke per video — see references/runbook.md's own build.py-shaped
# example above (the breakdown-video/cognee-video scripts) for a filter_complex this size done
# for real; adapt its structure (amix → sidechaincompress → amix → loudnorm) rather than
# starting from a blank filter graph.
run(["-i", "work/voiceover.mp3", "-i", "work/bed.wav",
     "-filter_complex", "[0:a]aresample=48000[vo];[1:a]volume=-16dB,aresample=48000[bed];"
                         "[bed][vo]sidechaincompress=threshold=0.03:ratio=6:attack=40:release=450:makeup=1[ducked];"
                         f"[vo][ducked]amix=inputs=2:normalize=0:duration=longest,atrim=0:{TOTAL:.2f},"
                         "loudnorm=I=-14:TP=-1.5:LRA=11[mix]",
     "-map", "[mix]", "-c:a", "pcm_s16le", "-ar", "48000", "work/mix.wav"])

# ---- 4. Final mux (burn in captions here with -vf "subtitles=work/captions.ass" if used) --
run(["-i", "work/video-silent.mp4", "-i", "work/mix.wav",
     "-c:v", "libx264", "-crf", "17", "-preset", "slow", "-pix_fmt", "yuv420p", "-r", str(FPS),
     "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-shortest", "OUT.mp4"])
print("done")
```

The shot list and audio mix are the one genuinely bespoke part of every video — fill in real
scene durations, real anchor-derived SFX timestamps (from each scene's `markers.json`), and the
actual voiceover cut points. Don't try to make this fully generic; adapt it per video the same
way the shot list in a real NLE timeline is bespoke per edit.

For captions, build a simple `.ass` file from the transcript's word timings (group words into
short on-screen lines, gate each line's start/end to its words' timestamps) and reference it
in the final mux's `-vf subtitles=...` filter.

---

## Step 6 — Verify before calling it done

1. Play the output file back in full. Check: does every beat land where the narration/music
   implies it should? Any visible frame drops or stutter from Step 2? Audio clipping or
   silence gaps?
2. `ffmpeg -i OUT.mp4 -af volumedetect -f null - 2>&1 | tail -5` — sanity-check mean/max dB
   are reasonable (no silence, no clipping at 0 dB).
3. Check the file size/format against whatever constraint prompted the video (a Snap Lens
   preview video wants a short, small clip; a product demo page wants something web-friendly).
4. Clean up scratch state: scene directories, intermediate `seg*.mp4`/`parts.txt`/`mix.wav`
   files, and any dev server started to serve the target — don't leave these lying around or
   running.

## Step 7 — Hand off

Report the output file's path, duration, and size, and what's left for the user (approving the
cut, swapping in their own voiceover if a synthesized one was a placeholder, uploading it
wherever it's going). Never upload, publish, or submit it anywhere without being asked.

---

## One-shot checklist

```
[ ] Step 0 — target, shot beats, and narration script understood; ambiguity asked once
[ ] Step 1 — ffmpeg + Playwright (+ faster-whisper/ElevenLabs if needed) confirmed working
[ ] Step 2 — each scene recorded as real CDP-captured footage (+ real audio tap if relevant)
[ ] Step 3 — each scene converted to a fixed-fps CFR scene.mp4
[ ] Step 4 — narration/music/SFX collected or generated; captions transcribed if wanted
[ ] Step 5 — shot list cut, concatenated, audio mixed+ducked+normalized, final mux done
[ ] Step 6 — played back and sanity-checked, scratch state cleaned up
[ ] Step 7 — handed back to the user, nothing published without being asked
```
