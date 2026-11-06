# Chapters

One file per case: `workshop/NN-slug.md`, numbered from `01`.

## Shape

```markdown
# <Chapter title>

> <One-line summary.>

**Time:** <N> minutes

## Goal
## The idea
## The case
## Reasoning towards the fix
## Check your fix
## In production
## Key points
```

- **Goal:** what the learner can do after this chapter, in one or two sentences.
- **The idea:** the depth lives here. Why it matters, how it works, the trade-offs, and when
  the usual advice is wrong.
- **The case:** the real `run N` output, pasted verbatim from a run you did.
- **Reasoning towards the fix:** guide the learner to the fix without pasting the solution.
- **Check your fix:** the real `check N` output as shipped (failing), pasted verbatim.
- **In production:** what changes at scale, what to monitor, what to alert on.
- **Key points:** 3 to 5 bullets.

The last chapter ends with a 10-point production checklist.

## Writing style

- Plain English, short sentences, no em dashes.
- Gender-neutral wording for example users.
- Quote only output that really printed. If you change the lab, rerun and repaste.
- Do not mention other projects by the same author unless the brief says the workshop
  continues a series, and then only the series and its previous stage.
