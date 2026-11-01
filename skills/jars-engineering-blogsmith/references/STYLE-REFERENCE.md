# Style Reference — Jishanahmed's Published Articles

Annotated examples from real published work. Use these as the style baseline when
writing or editing. Do not copy sentences — use them to understand the cadence and
what makes each approach work.

---

## Article 1 — Build with Kestra: I Tried to Build an AI PR Reviewer… Everything Broke (Then It Worked)

**URL:** https://jishanahmedshaikh.medium.com/build-with-kestra-i-tried-to-build-an-ai-pr-reviewer-everything-broke-then-it-worked-c81ba4587e01

**Narrative thread:** Debugging story — tried something, broke repeatedly, eventually worked

**What makes it work:**

### The title itself sets the expectation honestly
"Everything Broke (Then It Worked)" — this is not hype. It prepares the reader for a
realistic arc, not a success story. The reader knows going in that failure is part of it.
This is the opposite of "How I Built an AI PR Reviewer in 5 Minutes".

### The timestamp as authenticity signal
> "Yes it is 1:31 AM IST"

One sentence. No justification. No "I know it's late but I was dedicated..." — just the
raw fact. The reader understands the commitment without being told about it. This works
because it's specific (1:31 AM IST, not "late at night") and because it's not made into
a virtue.

### "Classic." as a paragraph
One word, full stop, its own paragraph. This is the voice — dry, self-aware, zero
self-pity. It acknowledges the situation without dwelling on it. It trusts the reader
to recognise the feeling.

### The architecture section is honest about its source
> "Architecture: Generated using AI (Google Gemini Flash Image aka Nano Banana)"

The parenthetical is earned sarcasm. It tells you something true (the image was
AI-generated) while being funny about the model name. Never pretend a diagram is more
authoritative than it is.

### Failure is specific, not vague
> "Webhook not triggering / GitHub diff returning 404 / JSON breaking randomly / Kestra
> throwing errors I didn't understand"

Not "I had some issues" — specific failures with their own line. This is what makes
debugging stories credible.

**Cadence pattern:**
```
Problem stated → attempt described → failure named specifically → what was learned →
next attempt → (repeat) → final working state → architecture explained clean
```

---

## Article 2 — I Thought DataHub Was Just Another Data Catalog. I Was Wrong.

**URL:** https://jishanahmedshaikh.medium.com/i-thought-datahub-was-just-another-data-catalog-i-was-wrong-41ee873de013

**Narrative thread:** Misconception corrected — assumed X, discovered Y

**What makes it work:**

### The title is the entire thesis
The reader knows exactly what they're getting: someone had a wrong assumption and
corrected it. This structure (I thought X. I was wrong.) is one of the most powerful
in technical writing because it:
1. Implies the reader might have the same wrong assumption
2. Promises a correction — something will be learned
3. Does not oversell — "I was wrong" is humble and specific

### The misconception has to be real
The article only works if the wrong assumption is genuine — not manufactured for
narrative effect. The reader can tell the difference.

---

## Article 3 — Installing WLED on an ESP32 DevKit V1: A Debugging Story That Started Hundreds of Kilometres Away

**URL:** https://jishanahmedshaikh.medium.com/installing-wled-on-an-esp32-devkit-v1-a-debugging-story-that-started-hundreds-of-kilometers-away-440e0d81b5d8

**Narrative thread:** Debugging story with physical + software constraints

**What makes it work:**

### The subtitle does real work
"A Debugging Story That Started Hundreds of Kilometres Away" — this immediately signals:
- This is not a clean tutorial
- There is a physical constraint that matters
- The story has a non-obvious starting point

This type of subtitle earns the reader's patience for a longer setup before the technical content.

### Physical constraints make software debugging stories more real
Hardware debugging has an extra layer that pure software doesn't: you can't just restart
the process. The physical distance from the device is a real constraint that changes
the debugging approach. Surfacing this makes the article specific and non-generic.

---

## Article 4 — Your AI Isn't Bad at SQL. It Just Doesn't Know Your Company.

**URL:** https://jishanahmedshaikh.medium.com/your-ai-isnt-bad-at-sql-it-just-doesn-t-know-your-company-2f1e97cbe186

**Narrative thread:** Reframe — common frustration explained by a different root cause

**What makes it work:**

### The title reframes the problem without dismissing it
"Your AI isn't bad at SQL" — acknowledges the frustration without validating the
wrong conclusion. Then immediately gives the real cause. This structure:
1. Shows you understand the reader's frustration
2. Redirects to the real problem
3. Implies a solution is coming

### The thesis is specific enough to be falsifiable
"It just doesn't know your company" is a specific claim that can be tested and
disproven. Vague theses ("AI has limitations") cannot be argued with and are
therefore useless to the reader.

---

## Patterns to replicate across all articles

### Failure is always specific
Never "it didn't work" — always what the error was, what it said, what it implied.

### Timestamps and context details are used as authenticity signals
Not to prove dedication — to make the story feel real and reproducible.

### Parentheticals carry the humour
Sarcasm lives in parentheses. The main sentence stays factual. The parenthetical
is where the commentary goes. This keeps the article readable for people who don't
want the jokes while rewarding those who do.

### The architecture diagram always has a source annotation
Where did the diagram come from? Generated by AI? Hand-drawn? From the repo README?
Saying so builds credibility, not diminishes it.

### Closing insights are specific, not motivational
Not "and that's why we keep building" — a specific thing the reader now knows that
they did not know at the start. One sentence, delivered without ceremony.

---

## What not to do — anti-patterns from the published work

These never appear in Jishanahmed's articles:

- Opening with "In today's rapidly evolving landscape..."
- "Seamlessly integrates"
- "Game-changing"
- "I'm passionate about..."
- "This powerful tool..."
- Paragraphs that list features without explaining decisions
- Conclusions that restate the introduction
- Jokes about AI being "smart" or "intelligent" without qualification
- Claims like "the AI correctly understood" without evidence
- Section titles that are generic ("Introduction", "Conclusion", "Implementation")
  instead of specific ("Why the webhook kept returning 404")
