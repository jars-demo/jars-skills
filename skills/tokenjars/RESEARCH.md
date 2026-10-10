# TokenJARS — Research and Build Notes

**By:** Jishanahmed AR Shaikh (JARS) and AI Tools  
**Date:** 2026-10-10 · **Skill version:** 1.0.0

Research sources studied before finalizing the skill architecture. Not loaded by the agent
during normal skill use — this is maintainer reference material.

---

## Sources

### Caveman — github.com/JuliusBrussee/caveman (Apache-2.0)

Skill + optional CLI proxy by Julius Brussee. Key distinction: the **skill** controls
output style; the **proxy** intercepts and compresses tool output at runtime. These are
separate components. The skill alone does not compress tool output.

Principles extracted (not copied):
- Answer first. One idea per sentence. Active voice.
- Negations (`not`, `never`, `no`, `only`) are never dropped.
- Exact values — paths, error messages, numbers — reproduced verbatim.
- Small changes: show the diff, not the whole file again.
- Security warnings and irreversible actions always get full sentences.
- Never rewrite user prompts (Adobe Research: makes answers longer and worse).

Benchmark methodology observations: token counts use `tiktoken o200k`, stated explicitly.
The 33.2% input reduction is skill + proxy combined — skill alone is substantially less.
JetBrains A/B (86 tasks): no measurable quality loss (p = 0.82), 8.5% fewer output tokens.
Adobe Research CAVEWOMAN (arXiv June 2026): cost cut 1.4–2.4× across 8 models, 5 datasets.
Red rows (HTML compressor missing, 9.9% worse) are reported — honest methodology.

TokenJARS differs: professional engineering style (not a caveman persona), five optimization
areas instead of one voice rule, explicit session handoff format, deeper safety invariants.

### Headroom — docs.headroomlabs.ai (commercial, architecture studied for reference only)

Runtime context optimization layer — proxy, Python lib, TypeScript SDK, or framework
integration. Compresses tool outputs, DB results, file reads, RAG results before the LLM.
Stores originals via CCR (Compress-Cache-Retrieve); agent gets a `headroom_retrieve` tool.

Reported savings on generated test data (tokenizer: gpt-5.6, reproducible with `--seed`):

| Scenario | Before | After | Savings |
|---|---|---|---|
| Code search (100 results) | 17,199 | 13,597 | 21% |
| SRE incident debugging | 55,957 | 24,340 | 57% |
| Codebase exploration | 58,801 | 33,895 | 42% |
| GitHub issue triage | 46,067 | 32,429 | 30% |

Per source: "treat these as a shape, not a promise."

TokenJARS v1 makes none of these claims — no proxy, no runtime compression. Input token
savings come only from behavioral changes: targeted reads, fewer redundant calls, less
verbose output. CCR is the right architecture for a future v2 proxy.

### Agent Skills Specification — agentskills.io/specification

Confirmed: `name` lowercase max 64 chars, matches directory. `description` max 1024 chars.
SKILL.md recommended under 500 lines. Progressive disclosure: metadata loads at startup,
body on activation, references on demand. Validation: `npx skills add . --list`.

### Prompt caching (Anthropic, OpenAI docs; arXiv:2606.17016)

Cached tokens bill at 70–90% discount. Cache hits require an identical prefix — inserting
or reordering the stable prefix invalidates it. Anthropic requires ~1,024 tokens minimum.
Design implication: skill instructions stay at the top of context; dynamic content at end.

### ASD-STE100 — asd-ste100.org (open standard)

Aircraft maintenance writing standard. Core rules: one instruction per sentence, active
voice, ~20 words max, one term per concept. Produces shorter, less ambiguous text that
tokenizes efficiently. Applied selectively — not to code, error messages, or security
findings that need exact reproduction.

---

## Design decisions

| Decision | Rationale |
|---|---|
| Skill only, no proxy in v1 | Proxy needs Node.js install, per-provider integration. Out of scope. Skill is portable, zero-dependency. |
| Three modes | Gradual adoption. Balanced default doesn't change existing workflows. |
| Five optimization areas | Each has distinct failure modes and distinct rules. |
| Safety invariants as explicit section | Prevents misapplication — token optimization is new to many teams. |
| SKILL.md under 200 lines | ~1,000-token overhead. Pays back in any session with multiple tool calls. |
| No slash commands | Not universally supported per the spec. Natural-language activation is portable. |
| No fabricated benchmarks | Results table ships empty with methodology — not invented percentages. |

---

## Validation

- `npx skills add . --list` → 13 skills, tokenjars listed ✅ (run 2026-10-10)
- SKILL.md: 199 lines, description 496 chars — within spec limits ✅
- `claude plugin validate --strict .` — run before opening the pull request

## Known limitations

- No live benchmark results — requires API access not available during this build.
- Token footprint (~1,000) is a tiktoken approximation, not a live measurement.
- Mode switching is natural-language only — no slash commands.
- Savings depend on how verbose the baseline agent already is.
- Cache hit behavior is provider-specific and version-dependent.

## Publication steps

1. `claude plugin validate --strict .` — must pass.
2. `npx skills add . --list` — already confirmed ✅.
3. `plugin.json` version is `1.5.0` ✅, `README.md` tokenjars row added ✅.
4. Open PR: `feat: Add tokenjars skill`.
5. Site rebuilds automatically on push to main via `site/build.py`.

## License

Caveman (Apache-2.0): principles studied, no prose copied. Headroom: commercial,
architecture studied for reference. ASD-STE100: open standard. TokenJARS: MIT.
