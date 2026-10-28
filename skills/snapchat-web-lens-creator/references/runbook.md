# Runbook: build a lightweight game and ship it as a Snapchat Web Lens

Paste this whole document as the first message of a **fresh** Claude Code session.
It is self-contained — it does not depend on any other conversation. Fill in the one
placeholder below and nothing else needs to change.

```
GAME IDEA: IDEA PUT HERE
```

(A sentence is enough — genre, theme, one mechanic. "A Breakout-style brick breaker
reskinned with bitmoji-style cartoon faces on the bricks" is the level of detail that
worked well. Vaguer is fine too; scope it down yourself in step 1.)

Everything from here is instructions for the agent carrying out the build.

---

## Ground rules

- **Keep it small.** One core mechanic, portrait mobile viewport, a handful of
  screens (title → play → game over). Reject feature creep even if it seems fun —
  three good mechanics beat eight mediocre ones in a lightweight game.
- **Zero asset pipeline by default.** Draw everything on Canvas 2D in code and
  synthesize every sound with Web Audio oscillators. No image files, no audio
  files, nothing to license, nothing to download. This is not a shortcut taken
  under time pressure — it is the house style, because it keeps the zip tiny and
  the build dependency-free.
- **Assets are the user's call.** If the user supplies real art/audio files, wire
  those in instead (a normal `AssetStore`/`Image`/`Audio` loader) and skip the
  procedural versions for that asset. If they provide nothing, generate it
  yourself — procedurally in code (preferred, zero dependencies) or through a
  connected design tool (Figma/Canva MCP, if one is available and the user wants
  that route) for a one-off icon/logo. Never ship placeholder-quality filler art.
- **Ask once, up front, then build without stopping.** Read the idea, work out
  what's genuinely ambiguous (see step 0), ask it all in a single batch of
  questions, then execute end-to-end. Do not keep checking in — the user wants
  speed; show them a working, live-tested game, not a string of questions.
- **Verify by actually running it**, not by reading the code back. Build it,
  serve it, open it in a real browser, tap/drag through it, read the console.
  "It compiled" is not "it works."
- **Zip budget: 7 MB**, not Snapchat's published 8 MB cap. The extra margin is
  deliberate — Snap's own limit checker has occasionally flagged builds that
  were technically under 8 MB but uncomfortably close, so this runbook's
  packaging script fails the build at 7 MB instead. Stay well under it; if the
  game needs real audio/image assets to feel right, that budget is tight, so
  default to procedural art and audio and only reach for files when the user
  explicitly wants a specific asset.
- **Close every dev server you start.** Never leave one running "in case," and
  never ask the user whether to leave it running — kill it once testing is done.
- **A non-zero exit code from the packaging script does not mean the zip wasn't
  created.** It writes the zip first, then runs the requirements checklist, and
  exits 1 if any check fails. Always confirm the zip's existence and size
  directly (`ls -la`) rather than trusting the exit code alone.

---

## Step 0 — Intake (ask once, in one batch)

From the idea, work out:

1. **What's the core loop and win/lose condition?** If the idea already implies
   one (a brick breaker implies paddle/ball/bricks/lives), don't ask — just state
   your understanding back to the user in one or two sentences before building, so
   they can correct it cheaply. If it's genuinely open (e.g. "make me a fun
   mobile game"), ask for a one-line concept.
2. **Where should the project live?** A fresh folder, outside any unrelated git
   repo. Ask for the exact path if the user didn't give one, or propose one
   (`E:\ProjectsWork\<game-name>` or similar, matching how their other game
   projects are laid out) and let them redirect.
3. **Assets: theirs or yours?** If they haven't said, ask once: "I'll draw
   everything in code (zero asset files) unless you want to supply art/audio —
   which do you want?"
4. **Anything that changes scope materially** — a required third-party API
   integration, a specific control scheme, 2–3 power-ups/abilities they want
   named. Don't ask about things you can reasonably decide yourself (color
   palette, exact numbers for speed/difficulty, the game's name — pick something
   playful and tell them what you picked).

Ask all of this as a *single* batch of questions (one tool call, multiple
questions), not a back-and-forth. Once answered, build straight through to a
live-tested, pushed result without further check-ins, unless something you
discover genuinely blocks you.

---

## Step 1 — Scope the idea into a minimal design

Write down (to yourself, not necessarily to the user unless asked):

- The **phases/states**: typically `TITLE → SERVE/READY → PLAYING → (LEVEL/ROUND
  transition) → GAME_OVER`, looping back to `TITLE` or restarting straight into
  `PLAYING`.
- The **one input scheme**: touch/pointer only. Drag to move something, tap to
  act (launch, jump, shoot). No keyboard-only controls — this targets a phone
  screen inside Snapchat.
- **Difficulty progression**: something simple and legible — more enemies, a
  faster ball, a smaller target — capped so it doesn't spiral out of control.
  Three small knobs (count, speed, a "tougher" chance) go a long way.
- **2–3 power-ups/abilities, if the idea calls for them** (or if the user asked
  for "something extra"). Keep each one a single clear effect with a duration or
  a one-shot use: multiply something, widen something, slow something down. Drop
  them from the thing the player just destroyed/collected, at a modest random
  chance (10–20%), so they're a bonus, not a requirement.

---

## Step 2 — Scaffold the project

Pinned dependency versions that are known to work together (reuse these exactly
unless the user asks for something else):

```json
{
  "name": "<game-name>",
  "version": "0.1.0",
  "description": "<GAME IDEA>, built as a Snapchat Web Lens",
  "type": "module",
  "private": true,
  "scripts": {
    "build": "node scripts/build.mjs",
    "dev": "node scripts/build.mjs --watch",
    "serve": "node scripts/serve.mjs dist",
    "start": "npm run build && npm run serve",
    "lens": "node scripts/lens.mjs",
    "test": "vitest --run"
  },
  "devDependencies": {
    "@snap/web-lens-api": "^0.1.2",
    "esbuild": "0.24.0",
    "typescript": "5.7.2",
    "vitest": "2.1.8"
  }
}
```

`tsconfig.json` — strict, bundler resolution, DOM lib (no framework needed):

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "module": "ESNext",
    "moduleResolution": "Bundler",
    "lib": ["ES2020", "DOM"],
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noUncheckedIndexedAccess": true,
    "noEmit": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "forceConsistentCasingInFileNames": true
  },
  "include": ["src", "tests"]
}
```

`vitest.config.ts`:

```ts
import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: { environment: 'node', include: ['tests/**/*.test.ts'] },
});
```

`.gitignore`:

```
node_modules/
dist/
dist-lens/
*.log
.DS_Store
<game-name>-lens-v*.zip
```

`index.html` — the whole static shell. Portrait-only, dark background so there's
no white flash, `touch-action: none` so drags don't scroll the page, and
`viewport-fit=cover` (a Web Lens requirement):

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no, viewport-fit=cover" />
    <title>GAME NAME</title>
    <link rel="icon" type="image/svg+xml" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E%3Crect width='64' height='64' rx='14' fill='%234a2a7a'/%3E%3C/svg%3E" />
    <style>
      :root { color-scheme: dark; }
      * { margin: 0; padding: 0; box-sizing: border-box; -webkit-tap-highlight-color: transparent; }
      html, body { width: 100%; height: 100%; overflow: hidden; background: #1a1033; touch-action: none; }
      #stage { position: fixed; inset: 0; display: flex; align-items: center; justify-content: center; background: #1a1033; }
      #game-canvas { width: 100%; height: 100%; max-width: 100vh; image-rendering: optimizeSpeed; touch-action: none; }
    </style>
  </head>
  <body>
    <div id="stage"><canvas id="game-canvas"></canvas></div>
    <script src="main.js"></script>
  </body>
</html>
```

Replace the favicon's inline SVG with something matching the game's actual icon
once step 6 produces one (see step 6).

`scripts/build.mjs` — type-checks, bundles to one unminified `dist/main.js`,
copies the shell:

```js
import { execSync } from 'node:child_process';
import { cpSync, mkdirSync, rmSync, readFileSync } from 'node:fs';
import esbuild from 'esbuild';

const watch = process.argv.includes('--watch');

rmSync('dist', { recursive: true, force: true });
mkdirSync('dist', { recursive: true });
cpSync('index.html', 'dist/index.html');

if (!watch) {
  console.log('[build] type-checking...');
  execSync('npx tsc --noEmit', { stdio: 'inherit' });
}

const opts = {
  entryPoints: ['src/main.ts'],
  outfile: 'dist/main.js',
  bundle: true,
  format: 'iife',
  target: 'es2020',
  minify: false,
  sourcemap: false,
};

if (watch) {
  const ctx = await esbuild.context(opts);
  await ctx.watch();
  console.log('[build] watching...');
} else {
  await esbuild.build(opts);
  const bytes = readFileSync('dist/main.js', 'utf8').length;
  console.log(`[build] done -> dist/main.js (${(bytes / 1024).toFixed(1)} KB)`);
}
```

`scripts/serve.mjs` — a dependency-free static server that finds a free port
starting at 8090 (so multiple game projects can run side by side without a
port clash):

```js
import { createServer } from 'node:http';
import { readFile, stat } from 'node:fs/promises';
import { extname, join } from 'node:path';

const root = process.argv[2] ?? 'dist';
const TYPES = { '.html': 'text/html', '.js': 'text/javascript', '.json': 'application/json', '.png': 'image/png', '.mp3': 'audio/mpeg' };

function findPort(start, cb) {
  const srv = createServer();
  srv.once('error', () => findPort(start + 1, cb));
  srv.listen(start, () => srv.close(() => cb(start)));
}

findPort(8090, (port) => {
  const server = createServer(async (req, res) => {
    try {
      let path = join(root, decodeURIComponent(new URL(req.url, 'http://x').pathname));
      const s = await stat(path).catch(() => null);
      if (!s || s.isDirectory()) path = join(root, 'index.html');
      const body = await readFile(path);
      res.writeHead(200, { 'Content-Type': TYPES[extname(path)] ?? 'application/octet-stream' });
      res.end(body);
    } catch {
      res.writeHead(404);
      res.end('not found');
    }
  });
  server.listen(port, () => console.log(`[serve] http://localhost:${port}`));
});
```

`npm install` once the files above exist.

---

## Step 3 — Game architecture

One pattern, four concerns, kept in separate files:

- **`src/game/state.ts`** — every board-size/physics constant (`BOARD_W`,
  `BOARD_H` = a 9:16 portrait logical size like `720 x 1280`; speeds, sizes,
  durations), the `GameState` interface (one plain object: `phase`, score,
  lives/health, the moving pieces as arrays where multiplicity is possible —
  e.g. `balls: Ball[]` not a single `ball`, so a "multiply" power-up is just
  pushing to an array — any timed-effect multipliers/timers), `createGame()`,
  and a `resetBall`/`resetRound`-style function that clears per-life state
  (including power-up timers) back to defaults.
- **`src/game/physics.ts`** — pure functions only: collision tests, bounce/
  reflection math, clamp, a `speedForLevel(level, base, perLevel, max)` curve.
  No DOM, no canvas, nothing stateful — this file is what unit tests exercise.
- **`src/game/loop.ts`** — one `step(state, input, dt, hooks)` function that
  advances the whole simulation by one frame: read input, move things, run
  collisions, update score/lives, handle phase transitions. It takes a `hooks`
  object (`onPaddleHit`, `onBrickHit`, `onLifeLost`, `onLevelClear`,
  `onGameOver`, `onPowerup`, ...) so every "this just happened" moment is a
  single call site — `main.ts` wires those hooks to sound effects and score
  reporting, keeping `loop.ts` itself free of side effects beyond mutating
  `state`.
- **`src/game/input.ts`** — a tiny class holding the latest pointer position in
  *board* coordinates and a one-shot "tap" flag consumed once per frame
  (`consumeTap()`). It never touches the DOM; `main.ts` converts real pointer
  events into board coordinates and feeds them in.
- **`src/render/draw.ts`** — one `draw*` function per visual element, each a
  pure `(ctx, ...data) => void`. Read-only: rendering never mutates `GameState`.
- **`src/main.ts`** — the only file that touches the DOM. Canvas sizing
  (letterboxed to fit any viewport while preserving the 9:16 board), pointer
  event listeners converting client coordinates to board coordinates, the
  `requestAnimationFrame` loop calling `step()` then the `draw*` functions, and
  wiring `Profile`/`Sound` instances to the loop's hooks.

Canvas fit-to-viewport, reused verbatim across games:

```ts
function fitCanvas(): void {
  const dpr = Math.min(2, window.devicePixelRatio || 1);
  canvas.width = BOARD_W * dpr;
  canvas.height = BOARD_H * dpr;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  const scale = Math.min(window.innerWidth / BOARD_W, window.innerHeight / BOARD_H);
  canvas.style.width = `${BOARD_W * scale}px`;
  canvas.style.height = `${BOARD_H * scale}px`;
}
window.addEventListener('resize', fitCanvas);
fitCanvas();

function toBoard(clientX: number, clientY: number) {
  const rect = canvas.getBoundingClientRect();
  const scale = rect.width / BOARD_W;
  return { x: (clientX - rect.left) / scale, y: (clientY - rect.top) / scale };
}
```

Write real unit tests for `physics.ts` and any pure generation logic (layout
builders, difficulty curves) with Vitest — these are cheap to test and catch
real bugs. Don't bother unit-testing `loop.ts`/`draw.ts`/`main.ts`; verify those
by actually playing the game (step 8). Aim for genuine coverage of the math, not
a test count for its own sake — a dozen focused tests beats a hundred shallow
ones.

---

## Step 4 — Procedural art

No image files. A small set of canvas helpers, reused for everything:

```ts
function roundRect(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, r: number): void {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
}
```

Build a small cast of simple "face" expressions (happy, wink, surprised, angry,
sad, cool...) as a `face(ctx, cx, cy, size, expression)` function, driven off
proportions of a `w` parameter rather than magic pixel numbers, so the same
function draws a tiny HUD icon or a huge title-screen logo. Use a short, curated
flat color palette (5–6 colors) rather than random RGB — pick colors that read
well on a dark background, reuse them for bricks/enemies/UI accents/HUD so the
whole game feels like one palette.

For "liveliness" (the kind of polish that makes a game feel finished rather than
static): give the main interactive elements a brief reaction on impact — a
`hitTimer` field that starts at ~0.2s, counts down each frame, and while >0
swaps the element's expression (e.g. to "angry"/"shocked") and applies a quick
squash scale transform:

```ts
const reacting = element.hitTimer / 0.22; // 1 → 0 as it decays
const squash = 1 - reacting * 0.12;
ctx.save();
ctx.translate(cx, cy);
ctx.scale(1 / squash, squash);
ctx.translate(-cx, -cy);
// ...draw the element...
ctx.restore();
```

Decay `hitTimer` once per frame inside `step()` for every live element, alongside
the main simulation.

For the **title screen**: a logo mark (described in step 6), a shadowed title in
a bold system font (no external font files — `system-ui, -apple-system, Segoe UI,
sans-serif`, bold weight does the job), and a pill-shaped "TAP TO START" button
with its own drop shadow, not just bare text — a button-shaped hit target reads
as more production-ready than plain centered text. Leave real vertical gap
between the logo and the title text (measure the logo's actual drawn bounds, not
a guess) so nothing overlaps — this is the single most common first-draft mistake,
catch it in step 8's live screenshot before calling the UI done.

---

## Step 5 — Procedural audio

No audio files either — every sound is a synthesized Web Audio tone. One
reusable class:

```ts
export class Sound {
  private ctx: AudioContext | null = null;

  private ensure(): AudioContext | null {
    if (this.ctx) return this.ctx;
    const Ctx = window.AudioContext ?? (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
    if (!Ctx) return null;
    this.ctx = new Ctx();
    return this.ctx;
  }

  /** Must run inside a real user gesture — browsers block audio otherwise. */
  unlock(): void {
    const ctx = this.ensure();
    if (ctx && ctx.state === 'suspended') void ctx.resume();
  }

  private tone(freq: number, duration: number, opts: { type?: OscillatorType; gain?: number; glideTo?: number } = {}): void {
    const ctx = this.ensure();
    if (!ctx) return;
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = opts.type ?? 'sine';
    osc.frequency.setValueAtTime(freq, ctx.currentTime);
    if (opts.glideTo) osc.frequency.linearRampToValueAtTime(opts.glideTo, ctx.currentTime + duration);
    const peak = opts.gain ?? 0.12;
    gain.gain.setValueAtTime(0, ctx.currentTime);
    gain.gain.linearRampToValueAtTime(peak, ctx.currentTime + 0.01);
    gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + duration);
    osc.connect(gain).connect(ctx.destination);
    osc.start();
    osc.stop(ctx.currentTime + duration + 0.02);
  }

  // One short method per game event, each just a tone() call with hand-picked
  // frequency/duration/type — e.g. hit() is a short square blip, success() is
  // a quick ascending arpeggio (several tone() calls on a setTimeout stagger),
  // fail() is a sawtooth that glides down. Keep each one-liner-ish.

  // A soft, subtle ambient pad — two low sustained sine oscillators at very
  // low gain with a slow LFO breathing the volume — started once on the
  // player's first tap, never loud enough to compete with the SFX above:
  startPad(): void {
    const ctx = this.ensure();
    if (!ctx) return;
    const master = ctx.createGain();
    master.gain.value = 0;
    master.gain.linearRampToValueAtTime(0.02, ctx.currentTime + 2);
    master.connect(ctx.destination);
    for (const freq of [130.81, 196.0]) {
      const osc = ctx.createOscillator();
      osc.type = 'sine';
      osc.frequency.value = freq;
      osc.connect(master);
      osc.start();
    }
    const lfo = ctx.createOscillator();
    const lfoGain = ctx.createGain();
    lfo.frequency.value = 0.08;
    lfoGain.gain.value = 0.012;
    lfo.connect(lfoGain).connect(master.gain);
    lfo.start();
  }
}
```

In `main.ts`, call `sound.unlock()` and `sound.startPad()` together, once, on
the very first `pointerdown` — gate it with a boolean so it only fires once.

---

## Step 6 — Icon, logo, and favicon

**Default (no assets supplied): draw them, don't fetch them.**

1. Design one simple mark — typically the same "face" shape used for the game's
   characters/pieces, on a rounded-square or circular background in the game's
   palette. Icons read badly with text at small sizes, so keep it symbol-only
   (no game name baked into the icon itself).
2. To rasterize it to a PNG for the Lens Icon upload (Snap's portal wants a real
   PNG file, not an SVG): write a tiny standalone HTML page with a `<canvas
   width=512 height=512>` and the same drawing code as the in-game logo, copy it
   into `dist/` (so it's servable), open it via `claude-in-chrome`'s `navigate`
   against the already-running local server (not a `file://` URL — the
   extension blocks those), then use the `computer` tool's `zoom` action with
   `region: [0,0,512,512]` and `save_to_disk: true` to capture a pixel-perfect
   PNG crop. Copy the saved screenshot into `assets/icon.png`, then delete the
   temporary HTML file from both `assets/` and `dist/`.
   - If a connected design tool is available and the user would rather use it
     (Figma/Canva MCP tools), that's a fine alternative path for a one-off
     icon — generate or export a PNG there instead and save it to
     `assets/icon.png`. Either path is fine; procedural is the zero-dependency
     default.
3. For the browser-tab **favicon**, inline a small SVG as a `data:` URI directly
   in `index.html`'s `<link rel="icon">` — no extra file, no extra request, and
   it stays inside the Lens's self-contained/no-external-URL requirement for
   free:
   ```html
   <link rel="icon" type="image/svg+xml" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E%3Crect width='64' height='64' rx='14' fill='%234a2a7a'/%3E%3Crect x='14' y='16' width='36' height='30' rx='8' fill='%23ffd36b'/%3E%3Ccircle cx='25' cy='30' r='3.2' fill='%231a1033'/%3E%3Ccircle cx='39' cy='30' r='3.2' fill='%231a1033'/%3E%3Cpath d='M23 37 Q32 44 41 37' stroke='%231a1033' stroke-width='3.2' fill='none' stroke-linecap='round'/%3E%3C/svg%3E" />
   ```
   (`#` must be percent-encoded as `%23` inside the data URI; use single quotes
   inside the SVG's own attributes so they don't collide with the surrounding
   double-quoted HTML attribute.) Match its colors/shape to the real icon.

**If the user supplies assets instead:** skip the procedural icon, use their
file directly for `assets/icon.png`, and for any in-game art, load it the
normal way (`new Image()`, a small `AssetStore`/manifest, or inline it as a
`data:` URI if it's small enough to keep the zip under budget) instead of
drawing it in code.

---

## Step 7 — Snapchat Web Lens integration

Install `@snap/web-lens-api` (already in the devDependencies from step 2). One
class wraps it, with a complete fallback to `localStorage` for everywhere that
isn't actually Snapchat:

```ts
const KEY = '<game-name>.best.v1';
const INIT_TIMEOUT_MS = 2000;

interface SnapApi {
  isStub?: boolean;
  init(): Promise<unknown>;
  isSupported(name: string): boolean;
  leaderboards: { submitScore(o: { score: number }): Promise<{ bestScore?: number } | undefined>; show(): Promise<unknown> };
  bitmoji: { getAvatarInfo(): Promise<{ hasAvatar: boolean }>; get2DAvatar(o: { size: string }): Promise<{ url: string }> };
  storage: { get(key: string): Promise<{ found: boolean; value?: unknown }>; set(key: string, value: unknown): Promise<unknown> };
}

export class Profile {
  best = 0;
  leaderboards = false;
  avatar: HTMLImageElement | null = null;
  private snap: SnapApi | null = null;
  private snapStorage = false;

  async load(): Promise<void> {
    const snap = (globalThis as unknown as { snapchat?: SnapApi }).snapchat;
    if (snap) {
      try {
        await Promise.race([snap.init(), new Promise((r) => setTimeout(r, INIT_TIMEOUT_MS))]);
        this.snap = snap;
        this.leaderboards = snap.isSupported('leaderboards');
        this.snapStorage = snap.isSupported('storage');
        if (snap.isSupported('bitmoji') && !snap.isStub) void this.loadAvatar(snap);
        if (this.snapStorage) {
          const got = await snap.storage.get(KEY);
          this.best = typeof got.value === 'number' ? got.value : 0;
          return;
        }
      } catch {
        this.snapStorage = false;
      }
    }
    try { this.best = Number(globalThis.localStorage?.getItem(KEY) ?? 0) || 0; } catch { this.best = 0; }
  }

  /** A run ended with `score`. Returns true if it's a new best. */
  reportScore(score: number): boolean {
    const isBest = score > this.best;
    if (isBest) this.best = score;
    this.save();
    if (this.leaderboards && this.snap) {
      const snap = this.snap;
      void snap.leaderboards.submitScore({ score: Math.max(0, Math.round(score)) })
        .then((r) => {
          if (typeof r?.bestScore === 'number' && r.bestScore > this.best) { this.best = Math.floor(r.bestScore); this.save(); }
        }).catch(() => {});
    }
    return isBest;
  }

  showLeaderboard(): void {
    if (this.leaderboards && this.snap) void this.snap.leaderboards.show().catch(() => {});
  }

  private async loadAvatar(snap: SnapApi): Promise<void> {
    try {
      if (!(await snap.bitmoji.getAvatarInfo()).hasAvatar) return;
      const { url } = await snap.bitmoji.get2DAvatar({ size: 'medium' });
      const img = new Image();
      img.onload = () => (this.avatar = img);
      img.src = url;
    } catch { /* no Bitmoji — the screens draw a cartoon face instead */ }
  }

  private save(): void {
    const value = this.best;
    if (this.snapStorage && this.snap) { void this.snap.storage.set(KEY, value).catch(() => {}); return; }
    try { globalThis.localStorage?.setItem(KEY, String(value)); } catch { /* private window */ }
  }
}
```

**On the title screen**: draw `profile.avatar` (the real Bitmoji) in a clipped
circle when it has loaded; otherwise draw the procedural logo mark from step 6
as the placeholder — never a broken image or empty space.

**On game over**: call `profile.reportScore(score)` once, and make the score
(or a dedicated row) tappable to call `profile.showLeaderboard()` — that opens
Snapchat's own native leaderboard panel. There is no "challenge a friend"
method to call yourself: once `leaderboards.show()` opens the native panel,
surfacing/challenging friends is handled entirely by the Snapchat platform, not
something the Lens's code controls.

**Important realism check**: `isSupported('leaderboards')`/`isSupported('bitmoji')`
are only ever `true` two ways — (a) inside real Snapchat, or (b) the SDK's
built-in desktop stub, which **only activates when `vendor/snap-api.js` is
actually present on the page** (i.e. only in the packaged Lens build served
locally, not the plain `dist/` dev build). To prove the leaderboard wiring
actually works before telling the user it does, serve `dist-lens/` (produced by
step 9's packaging script) in a normal browser and run this in the page
console:

```js
await window.snapchat.init();
await window.snapchat.leaderboards.submitScore({ score: 123 });
// → { bestScore: 123 } once { isStub: true, leaderboardsSupported: true } checks out
```

---

## Step 8 — Package as a Snapchat Web Lens zip

`scripts/lens.mjs` — zips `dist/`, injects the Snap API script so it loads
*before* the game code, and validates the result against Snap's actual Web
Lens requirements. Note the **7 MB** cap (`MAX_ZIP`), stricter than Snap's
published 8 MB, per this runbook's safety margin — and the Windows fallback
chain for creating the zip, because `zip`/`unzip` are frequently missing on
Windows even inside Git Bash:

```js
import { execSync } from 'node:child_process';
import { cpSync, existsSync, mkdirSync, readFileSync, rmSync, statSync, writeFileSync } from 'node:fs';
import { join, resolve } from 'node:path';

const SRC = 'dist';
const STAGE = 'dist-lens';
const version = process.argv[2] ?? '1';
const ZIP = `<game-name>-lens-v${version}.zip`;
const MAX_ZIP = 7_000_000; // 7 MB — a safety margin under Snap's published 8 MB cap
const MAX_INDEX = 1_000_000;

if (!existsSync(`${SRC}/index.html`)) {
  console.error(`No ${SRC}/index.html — run "npm run build" first.`);
  process.exit(1);
}

rmSync(STAGE, { recursive: true, force: true });
cpSync(SRC, STAGE, { recursive: true });

const SNAP_API = 'node_modules/@snap/web-lens-api';
mkdirSync(join(STAGE, 'vendor'), { recursive: true });
cpSync(`${SNAP_API}/dist/snap-api.js`, join(STAGE, 'vendor', 'snap-api.js'));
cpSync(`${SNAP_API}/LICENSE`, join(STAGE, 'vendor', 'snap-api.LICENSE'));
const stagedHtml = join(STAGE, 'index.html');
writeFileSync(stagedHtml, readFileSync(stagedHtml, 'utf8').replace(
  '<script src="main.js"></script>',
  '<!-- Snapchat Web Lens API (MIT, Snap Inc.), Lens build only. -->\n    <script src="vendor/snap-api.js"></script>\n    <script src="main.js"></script>',
));

// `zip` first; then bsdtar (bundled in Windows 10+, writes proper "/" paths);
// Compress-Archive is the last resort.
function makeZip(outDir, zipPath) {
  const dst = resolve(zipPath).replace(/\\/g, '/');
  const attempts = [
    { name: 'zip', cmd: `cd "${outDir}" && zip -r -q -X -9 "${dst}" .` },
    { name: 'bsdtar', cmd: process.platform === 'win32'
        ? `cd "${outDir}" && "%SystemRoot%\\System32\\tar.exe" -a -c -f "${dst}" -- *`
        : `cd "${outDir}" && tar -a -c -f "${dst}" -- *` },
    { name: 'Compress-Archive', cmd: `powershell -NoProfile -Command "Compress-Archive -Path '${resolve(outDir)}\\*' -DestinationPath '${resolve(zipPath)}' -Force"` },
  ];
  for (const a of attempts) {
    rmSync(zipPath, { force: true });
    try {
      execSync(a.cmd, { stdio: 'pipe', shell: true });
      if (existsSync(zipPath) && statSync(zipPath).size > 0) return a.name;
    } catch { /* tool missing or failed — try the next one */ }
  }
  throw new Error('could not create the zip — install `zip`, or run on Windows 10+ (bsdtar)');
}

function zipEntries(zipPath) {
  try {
    return execSync(`unzip -Z1 "${zipPath}"`, { encoding: 'utf8' }).trim().split(/\r?\n/);
  } catch {
    const ps = `Add-Type -A System.IO.Compression.FileSystem; [IO.Compression.ZipFile]::OpenRead('${resolve(zipPath)}').Entries | ForEach-Object { $_.FullName }`;
    return execSync(`powershell -NoProfile -Command "${ps}"`, { encoding: 'utf8' }).trim().split(/\r?\n/).map((e) => e.replace(/\\/g, '/'));
  }
}

const zipTool = makeZip(STAGE, ZIP);

const failures = [];
function check(label, ok, detail = '') { console.log(`  ${ok ? 'PASS' : 'FAIL'}  ${label}${detail ? ` — ${detail}` : ''}`); if (!ok) failures.push(label); }

const entries = zipEntries(ZIP);
const html = readFileSync(join(STAGE, 'index.html'), 'utf8');
const zipBytes = statSync(ZIP).size;
const mb = (n) => `${(n / 1_000_000).toFixed(2)} MB`;

console.log(`\nChecking ${ZIP} against the Web Lens requirements:\n`);
check('index.html at the root of the zip', entries.includes('index.html'));
check('every entry uses forward slashes', entries.every((e) => !e.includes('\\')));
check('zip is 7 MB or smaller', zipBytes <= MAX_ZIP, mb(zipBytes));
check('index.html is 1 MB or smaller', Buffer.byteLength(html) <= MAX_INDEX, mb(Buffer.byteLength(html)));
check('no absolute paths in index.html', !/(?:src|href)\s*=\s*["']\//.test(html));
check('no external URLs in index.html', !/(?:src|href)\s*=\s*["'](https?:)?\/\//i.test(html));
check('no <base> element', !/<base[\s>]/i.test(html));
check('viewport-fit=cover (safe-area insets read as 0 without it)', /viewport-fit=cover/.test(html));
check('no source maps shipped', entries.every((e) => !e.endsWith('.map')));
check('Web Lens API is in the zip and loaded first', entries.includes('vendor/snap-api.js') && html.indexOf('vendor/snap-api.js') < html.indexOf('main.js'));

if (failures.length) {
  console.error(`\n${failures.length} check(s) failed. Fix them before uploading to My Lenses.`);
  process.exit(1); // the zip still exists — this just means don't ship it yet
}
console.log(`\n${ZIP} is ready (${mb(zipBytes)}, archived with ${zipTool}). Upload it at My Lenses as a Web Lens.`);
```

Run `npm run build && npm run lens -- 1`. Confirm the zip with `ls -la`
regardless of the script's exit code (see the ground rules above).

---

## Step 9 — Verify it for real before calling it done

1. `npm test` — the physics/logic unit tests pass.
2. `npm run build` — clean type-check, no errors.
3. `npm run serve` (background), note the printed port.
4. Open it with `claude-in-chrome`: navigate to the local URL, screenshot the
   title screen (check logo/text don't overlap — see step 4), tap through to
   start, tap/drag to play for a few seconds, screenshot mid-game, check
   `read_console_messages` with `onlyErrors: true` comes back clean.
5. Build the Lens package (step 8), serve `dist-lens/` on a *different* port,
   and run the leaderboard stub check from step 7 to prove the Snapchat
   integration actually fires, not just that it compiles.
6. **Kill every server you started** before finishing. Check with `netstat` (or
   equivalent) that nothing is still listening on the ports you used.

---

## Step 10 — Git and GitHub

- If the user gave you a repo path, use it; if it's already a git repo with a
  remote (`git remote -v`), that remote is where this is going — don't assume
  it's unset.
- Ask for the commit message rather than inventing one, unless the user has
  told you (in this session or a durable preference) that you should just pick
  one — conventions vary per project/person, and a wrong guess on attribution
  or co-author lines is the kind of mistake that's annoying to unwind.
- Only push when asked, or when the user's request already implies it ("push
  this", "get it on GitHub").
- If asked to set the repo's About section: `gh repo edit <owner>/<repo>
  --description "..." --homepage "<url>" --add-topic <topic> ...` (repeat
  `--add-topic` per tag). Verify with `gh repo view <owner>/<repo> --json
  description,homepageUrl,repositoryTopics`.

---

## Step 11 — Deploy to Vercel (if asked)

The build is fully static (`dist/`), so Vercel needs no framework detection.
Add `vercel.json` so the dashboard picks up the right settings automatically:

```json
{
  "buildCommand": "npm run build",
  "outputDirectory": "dist",
  "cleanUrls": true
}
```

Then tell the user the dashboard steps (this part is on them — it needs their
Vercel login): **vercel.com → Add New → Project → Import** the GitHub repo
→ Framework Preset **Other** → **Deploy**. Every push to the default branch
auto-redeploys after that. If they want a custom domain, that's **Project →
Settings → Domains** on their end too.

---

## Step 12 — Hand off for Snapchat submission

At **My Lenses** on Snapchat's Web Lens developer portal, same four things
every time:

1. **Package** — upload the zip from step 8.
2. **Lens Icon** — upload `assets/icon.png` from step 6.
3. **Lens Name** — short, under the portal's character limit (18 last seen).
4. **5–10s video preview** — the one step a human has to do: either the user
   records themselves playing it, or you can generate one with a Playwright +
   Chrome DevTools Protocol screencast script that drives real pointer input
   against the running game and captures real frames + real audio (tap an
   `AudioContext`, wrap `Audio`/`MediaElementSource`, record via
   `MediaRecorder`) — this is a separate, heavier task than the rest of this
   runbook; offer it, don't assume it's wanted, and don't attempt it under
   time pressure.

Submit once all four show "Ready" in the portal.

---

## One-shot checklist (for re-running this fast)

```
[ ] Step 0  — idea understood, questions asked once, answered
[ ] Step 2  — project scaffolded, npm install clean
[ ] Step 3  — state/physics/loop/input/draw/main written
[ ] Step 4  — procedural art, no overlap on title screen
[ ] Step 5  — procedural SFX + ambient pad wired to loop hooks
[ ] Step 6  — icon.png + favicon made (or user assets wired in)
[ ] Step 7  — Profile class wired: leaderboard, Bitmoji, localStorage fallback
[ ] Step 8  — lens.mjs packaged, zip ≤ 7 MB, all checks PASS
[ ] Step 9  — tested live in a real browser, console clean, servers killed
[ ] Step 10 — committed (message from the user), pushed if asked
[ ] Step 11 — vercel.json added if a Vercel deploy was asked for
[ ] Step 12 — handed back to the user for icon/video/submission
```
