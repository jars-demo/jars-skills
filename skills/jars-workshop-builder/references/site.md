# The site

`frontend/` is a Next.js site that renders the chapters from `workshop/`. Reuse the reference
repos' config: `package.json`, eslint, prettier, tsconfig, vitest, playwright, `next.config`,
the markdown renderer, the quiz and the back-to-top button. Keep their pinned versions.

## Home page

- A hero with the title and one line on what the learner will fix.
- The chapter list grouped by level, each with its case's real symptom.
- At least one interactive simulator or chart of the core idea. Its logic lives in a
  unit-tested lib file, and its numbers come from the lab.
- A measured-numbers section with the experiments' real results.
- A quick start.

## Chapter pages

- Contents sidebar and an "On this page" outline.
- The `run` and `check` commands, each with a copy button.
- Previous and next links.
- A "Check yourself" block: two questions, each with the reason behind the answer.
- A subtle back-to-top button.

## Mobile

- No horizontal scroll at 390px wide.
- Code blocks and tables scroll inside themselves.
- Tap targets are at least 40px.

## Theme

- New for every workshop, unless the brief continues a series (then keep the series' type
  pairing and palette family, with one new accent).
- Before choosing, read the earlier workshops' `globals.css` tokens and `next/font` imports
  if you can, and do not repeat a palette or type pairing.
- A real type pairing through `next/font`, a deliberate palette as CSS tokens, and colours that
  always mean one thing (pass is always the same colour, fail is always the same colour).
- No purple gradients, no emoji, no generic hero with three feature cards. Respect
  `prefers-reduced-motion`.
- If the topic has a well-known brand look, you may use its colours, never its logo, and add
  "not affiliated" to the footer.

## Accessibility

- Status shown with an icon or text as well as colour.
- A visible focus ring on every interactive element.
- `tokens.ts` mirrors `globals.css`, and a unit test checks every text and background pair
  for WCAG AA contrast.

## Tests

- Unit tests (vitest): the simulator lib, the tokens contrast test, and tests that tie every
  number on the site to the chapters and the lab output.
- Playwright, desktop and 390px phone, against `next start -p 3114` (never port 3000): home
  loads, every chapter renders, the simulator responds, the quiz answers, back-to-top works,
  and there is no horizontal overflow.
