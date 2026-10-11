---
name: accessibility
description: Audit and fix web accessibility issues to meet WCAG 2.1 AA. Use when the user asks to make a component accessible, fix accessibility errors, add ARIA attributes, improve keyboard navigation, check color contrast, make a form accessible, fix screen reader issues, or audit a page for a11y problems.
---

# Accessibility

Find and fix real barriers that prevent people from using the UI — not just checklist items.
Read the actual markup before suggesting fixes. Automated tools catch ~30% of issues; the rest
require reading the code with intent.

## Ground rules

- **Read the component before suggesting changes.** Never propose ARIA attributes without
  seeing the existing HTML structure.
- **Use semantic HTML first.** A `<button>` is better than `<div role="button">`. Native
  elements bring keyboard handling, focus management, and ARIA roles for free.
- **ARIA is a patch, not a replacement.** Use it only when no semantic HTML element exists
  for the job. Wrong ARIA is worse than no ARIA.
- **Every fix must be verified.** Run the automated tool after changes and note what still
  needs manual testing.
- **Full WCAG compliance requires manual testing** with a real screen reader and keyboard.
  Automated tools and code review are not sufficient on their own.

---

## Step 0: Audit first

Run automated checks before touching code:

```bash
# axe-core CLI — best automated coverage
npx axe-cli https://localhost:3000/page --save report.json

# Or with Playwright (in CI)
npm install --save-dev @axe-core/playwright
# See: https://github.com/dequelabs/axe-core-npm/tree/develop/packages/playwright

# Lighthouse (built into Chrome DevTools → Lighthouse tab → Accessibility)
# Or CLI:
npx lighthouse https://localhost:3000/page --only-categories=accessibility --output=json
```

Triage the output: fix **critical** and **serious** violations first, then **moderate**.

---

## Keyboard navigation

Every interactive element must be reachable and operable with a keyboard alone.

### Focus management

```html
<!-- Bad — div swallows all keyboard events -->
<div onclick="handleClick()">Submit</div>

<!-- Good — native button is focusable, activates on Enter and Space -->
<button type="button" onclick="handleClick()">Submit</button>
```

If you must use a non-native element:

```html
<div
  role="button"
  tabindex="0"
  onclick="handleClick()"
  onkeydown="if(event.key==='Enter'||event.key===' ') handleClick()"
>
  Submit
</div>
```

### Focus trap in modals

When a modal opens, focus must move into it and be trapped until it closes:

```ts
// Move focus to the modal on open
modal.querySelector<HTMLElement>('[autofocus], h2, button')?.focus();

// Trap: intercept Tab and Shift+Tab to cycle within the modal
function trapFocus(event: KeyboardEvent, container: HTMLElement) {
  const focusable = Array.from(
    container.querySelectorAll<HTMLElement>(
      'a[href], button:not([disabled]), input, select, textarea, [tabindex]:not([tabindex="-1"])'
    )
  );
  const first = focusable[0];
  const last = focusable[focusable.length - 1];

  if (event.key === 'Tab') {
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }
  if (event.key === 'Escape') closeModal();
}
```

When the modal closes, return focus to the element that opened it.

### Skip link

Add a skip link as the first element in `<body>` so keyboard users can jump past navigation:

```html
<a href="#main-content" class="skip-link">Skip to main content</a>
<!-- visually hidden until focused -->

<main id="main-content" tabindex="-1">...</main>
```

```css
.skip-link {
  position: absolute;
  top: -100%;
  left: 0;
}
.skip-link:focus {
  top: 0;
}
```

---

## ARIA

Use ARIA only when a native element doesn't exist for the pattern.

### Labels

Every interactive element needs an accessible name:

```html
<!-- Icon-only button — no visible text -->
<button type="button" aria-label="Close dialog">
  <svg aria-hidden="true" focusable="false">...</svg>
</button>

<!-- Input with a visible label -->
<label for="email">Email address</label>
<input id="email" type="email" />

<!-- Input with no visible label (search bars) -->
<input type="search" aria-label="Search products" />

<!-- Labelled by another element -->
<h2 id="dialog-title">Confirm deletion</h2>
<div role="dialog" aria-labelledby="dialog-title" aria-modal="true">...</div>
```

Never use `placeholder` as the only label — it disappears when the user types and has
poor contrast in most browsers.

### Live regions

Use live regions to announce dynamic content to screen readers:

```html
<!-- Announce status messages without moving focus -->
<div role="status" aria-live="polite" aria-atomic="true">
  <!-- inject text here when something changes: "3 results found" -->
</div>

<!-- For urgent alerts (errors, destructive confirmations) -->
<div role="alert" aria-live="assertive">
  <!-- inject error messages here -->
</div>
```

Don't overuse `assertive` — it interrupts whatever the screen reader is currently saying.

### Landmark roles

Every page must have one `<main>`. Use landmarks so screen reader users can jump between sections:

```html
<header>...</header>         <!-- banner landmark -->
<nav aria-label="Primary">...</nav>
<main id="main-content">...</main>
<aside aria-label="Related articles">...</aside>
<footer>...</footer>         <!-- contentinfo landmark -->
```

If there are multiple `<nav>` or `<section>` elements, distinguish them with `aria-label`.

### State

Reflect interactive state in ARIA when CSS alone doesn't convey it:

```html
<!-- Accordion -->
<button aria-expanded="false" aria-controls="section-1">Section 1</button>
<div id="section-1" hidden>...</div>

<!-- Toggle button -->
<button aria-pressed="false">Mute</button>

<!-- Disabled (prefer native disabled attribute on form elements) -->
<button disabled>Save</button>
<!-- For non-native elements: -->
<div role="button" aria-disabled="true" tabindex="-1">Save</div>
```

---

## Forms

```html
<!-- Every input must have a label -->
<div>
  <label for="name">Full name <span aria-hidden="true">*</span></label>
  <input
    id="name"
    type="text"
    autocomplete="name"
    required
    aria-required="true"
    aria-describedby="name-error"
  />
  <!-- Error — only rendered when invalid -->
  <span id="name-error" role="alert" aria-live="polite">
    Full name is required.
  </span>
</div>

<!-- Group related inputs -->
<fieldset>
  <legend>Notification preferences</legend>
  <label><input type="checkbox" name="email-notif" /> Email</label>
  <label><input type="checkbox" name="sms-notif" /> SMS</label>
</fieldset>
```

Error messages must be:
- Programmatically associated with the field (`aria-describedby`)
- Injected into a live region or announced via `role="alert"`
- Descriptive: "Email is required" not just "Required"

---

## Color and contrast

WCAG 2.1 AA minimums:

| Text type | Minimum contrast ratio |
| --- | --- |
| Normal text (< 18pt / 14pt bold) | 4.5 : 1 |
| Large text (≥ 18pt / 14pt bold) | 3 : 1 |
| UI components and icons | 3 : 1 |
| Decorative elements | No requirement |

Check contrast without writing code:

```bash
# CLI check (give it a foreground and background hex)
npx color-contrast-checker "#1a1a1a" "#f5f5f5"

# Or use the browser DevTools → Accessibility panel → inspect element contrast
```

Never convey information with color alone — add a pattern, icon, or text label alongside.

---

## Images and media

```html
<!-- Informative image — describe what it conveys -->
<img src="chart.png" alt="Bar chart showing monthly sales growth of 12% in Q4 2024" />

<!-- Decorative image — hide from assistive technology -->
<img src="divider.png" alt="" role="presentation" />

<!-- SVG inline — title + desc for complex graphics -->
<svg role="img" aria-labelledby="chart-title chart-desc">
  <title id="chart-title">Monthly revenue</title>
  <desc id="chart-desc">A line chart showing revenue growing from $10k to $45k over 6 months.</desc>
  ...
</svg>

<!-- Video — captions required, audio description if visuals convey meaning -->
<video controls>
  <source src="demo.mp4" type="video/mp4" />
  <track kind="captions" src="demo.vtt" srclang="en" label="English" default />
</video>
```

---

## Common violations and fixes

| Violation | Fix |
| --- | --- |
| Interactive `<div>` or `<span>` | Replace with `<button>` or `<a href>` |
| `<img>` missing `alt` | Add `alt=""` for decorative, descriptive text for informative |
| Form input with no label | Add `<label for="id">` or `aria-label` |
| Color contrast below 4.5:1 | Darken text or lighten/darken background |
| Modal doesn't trap focus | Implement focus trap; return focus on close |
| No skip link | Add `<a href="#main-content">Skip to main content</a>` |
| `aria-label` on a non-interactive element | Remove it; ARIA labels are for interactive elements |
| Multiple `<h1>` elements | One `<h1>` per page; use `<h2>`–`<h6>` for hierarchy |
| Heading levels skipped (`<h1>` → `<h3>`) | Fix the hierarchy; headings must not skip levels |
| `<table>` without `<th>` | Add `<th scope="col">` or `<th scope="row">` headers |
| `role="button"` missing keyboard handler | Add `onkeydown` for Enter and Space |
| `aria-hidden="true"` on focusable content | Remove `aria-hidden` or add `tabindex="-1"` |
| Focus indicator removed with `outline: none` | Restore `:focus-visible` styles |

---

## Checklist

- [ ] Automated scan run (`axe-cli` or Lighthouse) with no critical/serious violations
- [ ] All images have `alt` text (descriptive or empty `alt=""` for decorative)
- [ ] All form inputs have a visible, associated `<label>`
- [ ] Error messages are associated with inputs via `aria-describedby`
- [ ] Every interactive element is reachable and operable by keyboard
- [ ] Modals trap focus and return it on close
- [ ] Skip link present as the first focusable element
- [ ] Heading hierarchy is sequential with no skipped levels
- [ ] Color contrast meets 4.5:1 for text, 3:1 for UI components
- [ ] No information conveyed by color alone
- [ ] Dynamic content updates announced via live regions
- [ ] Focus indicator visible (`:focus-visible` not suppressed)
- [ ] Note to user: full WCAG compliance requires manual testing with a screen reader (NVDA, VoiceOver, or JAWS)
