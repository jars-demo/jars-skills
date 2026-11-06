---
name: jars-workshop-builder
description: Build a complete, hands-on engineering workshop repo end to end in the JARS format. You get a runnable lab with one deliberate, deterministic bug per chapter, checks that reject lazy fixes, a chapter per case written from real output, and a Next.js site that renders the chapters with a simulator and a quiz. Everything is verified before it ships. Use when the user says "build a workshop on X", "make a hands-on lab about X", "create the next workshop", "turn this topic into a workshop", "workshop repo for X", or hands over a workshop brief with an IDEA line.
---

# jars-workshop-builder

Build one workshop repository: `lab/`, `workshop/`, `frontend/` and docs, all verified. The detailed
specs live in references and load only when you reach that step:

- [references/lab.md](references/lab.md): lab layout, case rules, CLI, checks, tests, experiments.
- [references/chapters.md](references/chapters.md): chapter sections and the writing style.
- [references/site.md](references/site.md): site pages, theme, accessibility and browser tests.
- [references/brief-template.md](references/brief-template.md): a one-line-IDEA brief the user can
  paste into a long, unattended agent session.

## Ground rules

1. **The user and the repo come first.** The user's brief, and any `AGENTS.md`, `CLAUDE.md` or
   `CONTRIBUTING.md` in the target repo, override this skill where they differ.
2. **Every number is real.** All output, timings and figures in chapters and on the site come
   from runs you actually did. Unit tests tie the site's numbers to the chapters and the lab.
3. **Safe by default.** Create repos, push, change repo settings, or edit any other repo (such as
   an org profile) only when the user asked for that exact action. Never force-push, never skip
   hooks, never deploy.
4. **Honest reporting.** If a check cannot run here (no Docker, no Playwright browsers, no
   network), say so plainly. Never claim a check passed if it did not run. Use the git identity
   and commit trailer rules the user and the repo give you.
5. **Lab safety.** Anything the lab creates (containers, files, ports, networks) is named after the
   lab and cleaned up. Never touch anything else on the machine. For security topics, every
   attack runs only against the lab's own service on `127.0.0.1`.
6. **No invented people.** Example users are IDs like `u_1041`, written gender-neutrally. No
   mascots, no characters, no story worlds (shops, restaurants, games).

## Inputs

Read these from the brief. If one is missing, pick a sensible default, keep going, and list
your choices in the final report. If the user said not to ask questions, do not ask.

| Input | Default |
| --- | --- |
| IDEA (the topic) | Required. Ask once if it is missing and the user allows questions. |
| Org and repo name | `<org>/<slug>-demo`, slug in lowercase kebab-case |
| Site host | Whatever pattern the user's earlier workshops use |
| License | MIT, holder and year as the user states, else ask or leave a clear TODO |
| Git identity | The repo's existing `git config`; set it only if the user gives one |
| Reference repos | One lab that drives a real tool, one that models a service in plain Python |
| Series | None. If IDEA continues a series, see step 2. |
| Looks already used | Read the earlier workshops' `globals.css` and `layout.tsx` fonts if you can |

## Steps

1. **Settle names.** Slug, repo, site host and a sharp title, for example "Make the slow query
   fast" or "Once, in order, on time". If you are already inside the target repo, use it.
2. **Study the reference repos.** Clone them into a folder outside the working tree. Read their
   lab layout, CLI, checks, tests, frontend config, markdown renderer, quiz and AGENTS.md.
   Reuse structure and tooling. Do not copy content, theme, colours or fonts.
   - Keep the exact dependency versions they pin. Any new dependency gets an exact version
     released at least 14 days ago.
   - Frameworks move fast. Read the frontend's `AGENTS.md` and the docs bundled in
     `node_modules` (for example `node_modules/next/dist/docs/`) before writing framework code.
   - **Series:** if IDEA continues a series, also study the previous stage. Keep its lab shape,
     CLI and type pairing and palette family, with one new accent. Do not repeat its cases.
3. **Plan.** Research the topic properly. Pick 8 to 12 chapters in 2 or 3 levels (for example
   foundations, intermediate, production), about 3 to 4 hours in total, from fundamentals to
   what senior engineers still get wrong. For each case write down: the bug, the symptom in
   numbers, what the check asserts, 1 or 2 plausible wrong fixes, and one valid alternative
   fix. Save the plan to a scratch file, not the repo.
4. **Scaffold** the repo: `.gitignore` (with `.env`), `.gitattributes` (`* text=auto eol=lf`),
   `.prettierrc.json`, `LICENSE`, empty `lab/`, `workshop/`, `frontend/`. Commit
   `chore: Scaffold the <title> workshop`.
5. **Build the lab** following [references/lab.md](references/lab.md). Commit the lab
   (`feat(lab): …`) and its tests (`test(lab): …`) separately.
6. **Run everything once.** Run every `run N`, `check N` (as shipped) and `try` experiment.
   Save the real output to scratch files and read it. You will quote it verbatim.
7. **Write the chapters** following [references/chapters.md](references/chapters.md). Commit
   `docs(workshop): …`.
8. **Build the site** following [references/site.md](references/site.md). Commit
   `feat(site): …`.
9. **Write the docs.** `README.md`: title, one paragraph, site link, quick start, command table,
   chapter table, layout, running the site, license. `AGENTS.md`: map, commands, rules. Commit
   `docs: …`.
10. **Verify.** Run all of the commands below. Fix and rerun until they pass, or record exactly
    which one could not run and why.
11. **Ship** only what the user asked for: push, repo description, homepage, topics, org
    profile row. If you may only push a branch, push it and open a pull request if allowed.
12. **Report** using the template at the end.

## Verify

```bash
cd lab && uv sync && uv run pytest && uv run ruff check . && uv run ruff format --check .
cd frontend && npm ci && npm run verify          # lint, typecheck, format, unit tests, build
cd frontend && npm run build && npx next start -p 3114 &   # never port 3000
E2E_BASE_URL=http://localhost:3114 npx playwright test     # desktop and 390px phone
```

Stop the server when Playwright finishes. Screenshot the home page and one chapter at desktop
and phone width, look at them, and fix anything clipped, cramped or ugly. For tool labs, also
run the lab's own tool checks (for example the real `docker` commands the checks use).

## Commits

Small Conventional Commits in this order: `chore`, `feat(lab)`, `test(lab)`, `docs(workshop)`,
`feat(site)`, `docs`. Imperative, capitalised subjects, a short body that says why. Never commit
`.env`, `node_modules`, `.next`, `test-results` or caches.

## Final report

Keep it short:

1. **What you built:** the title, each chapter with its one-line real symptom, the experiments'
   headline numbers, and the theme.
2. **Verification:** commands with pass counts, and anything that could not run.
3. **Copy-paste block:** description (one sentence, under 350 characters), website, 8 to 10
   lowercase hyphenated topics, the org profile row, and hosting steps (for example a Vercel
   import with Root Directory `frontend`).
4. **Where it landed:** the branch or pull request, and which repo settings you set yourself.
