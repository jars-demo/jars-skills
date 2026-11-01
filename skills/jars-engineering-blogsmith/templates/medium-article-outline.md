# [Working title]

> [Optional subtitle — states the technical contribution and why it matters.
>  Should be specific enough to earn the click.]

---

**Narrative thread:** [debugging story / misconception corrected / setup guide / capability proof]
**Central argument:** [one sentence — what the reader leaves knowing that they didn't before]
**Intended reader:** [who this is written for]
**Estimated reading time:** [X min]

---

## Hook
[First 2–4 lines. Incident, failure, counterintuitive truth, or frustration the reader
recognises. Must be specific — not "AI has limitations" but "at 1:31 AM my webhook
returned 404 for the fourteenth time".]

[IMAGE: Screenshot or artifact that establishes the problem immediately.]
*Caption: What this shows and why it matters at this point.*

---

## [Section 2 — The problem or context]
[What situation led to this? Why did it matter? What gap existed?]

---

## [Section 3 — What I built / what the architecture looks like]
[High-level design. What the pieces are, how they connect, what each one does.]

[IMAGE: Architecture diagram showing components, boundaries, and data flow with labels.]
*Caption: [Describe what the diagram shows and what the most important connection is.]*

---

## [Section 4 — Implementation — the non-obvious parts]
[Not a feature tour. Focus on the decisions that were non-obvious, the trade-offs made,
and the parts that required real thought. Skip the boilerplate.]

```bash
# [A real command or code snippet from the source — not invented]
```

[DIAGRAM: Sequence or data-flow diagram showing the critical interaction.]
*Caption: [What this diagram clarifies that prose alone would not.]*

---

## [Section 5 — What broke]
[Specific failures. Real error messages. What was tried, what the error said, what it
implied, and what the root cause turned out to be.]

[IMAGE: The actual error message, log output, or before/after view.]
*Caption: [What the error was and what it indicated.]*

---

## [Section 6 — Testing and what the results actually show]
[Test scope, setup, what changed, results. Be accurate about what was tested vs inferred.
A unit test is not end-to-end proof.]

---

## [Section 7 — Limitations and trade-offs]
[What this doesn't solve. What it doesn't prove. What the next real obstacle is.
This is not optional — it's what separates an engineering article from a press release.]

---

## Run it yourself
[Prerequisites listed explicitly. Exact reproducible steps. No secrets — placeholders only.]

```bash
# Step 1
# Step 2
```

---

## What's next
[Real planned work, labelled as planned — not implemented, not promised.]

---

## Final thought
[One specific insight. One sentence. No ceremony. No motivational speech.]

---

## Resources
- Repository:
- PR / issue:
- Demo:
- Docs:
- Related reading:

---

## Claims to verify before publishing
- [ ] [specific claim that needs confirmation]
- [ ] PR status (merged / open / closed):
- [ ] Version numbers accurate:
- [ ] All commands tested:
- [ ] No secrets or private URLs exposed:
