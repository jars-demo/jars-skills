# AGENTS.md

Guidance for AI coding agents (Claude Code, Codex, Cursor, Copilot, and others) working in this
repository. Humans: see [CONTRIBUTING.md](CONTRIBUTING.md).

## What this repo is

A collection of [Agent Skills](https://agentskills.io). Each skill is one folder under
`skills/` with a `SKILL.md`, and the repo doubles as a Claude Code plugin marketplace.

```
.claude-plugin/marketplace.json   catalogue: lists the plugin and where it lives ("./")
.claude-plugin/plugin.json        the plugin: name, version, metadata
skills/<name>/SKILL.md            one skill per folder
skills/<name>/references/         optional docs the skill links to
skills/<name>/scripts/            optional helper scripts the skill runs
README.md                         install steps and the skills table
site/                             skills.jishanahmed.in (site/build.py), rebuilt on every push to main
```

## Rules for skills

1. **One job per skill.** If a skill needs "and" to describe it, split it.
2. **Folder name = `name` in the frontmatter**: lowercase letters, digits, and hyphens, at most
   64 characters. Never rename a published skill; users rely on the name.
3. **Frontmatter has exactly `name` and `description`**, unless a feature needs more.
4. **The `description` decides when the skill loads.** Write what it does, then
   "Use when …" with the real phrases a user would say. Keep it under about 1024 characters.
5. **The body is instructions for an agent**: imperative, ordered steps, with commands it can
   run. No marketing, no history, no filler.
6. **Repository and user rules come first.** A skill must defer to the project's own
   conventions (`CONTRIBUTING.md`, `CLAUDE.md`, `AGENTS.md`, linters, templates).
7. **Safe by default.** Skills never push, publish, delete, force anything, skip hooks, or
   contact external services unless the user asks for that exact action. Say so in the skill.
8. **Honest by design.** Skills must not tell an agent to hide its involvement, fake results,
   or claim checks that did not run.
9. **No secrets, no personal data, no machine-specific paths** in skills or examples.
10. **Keep `SKILL.md` under about 500 lines.** Move long material into `references/` and link
    it, so it loads only when needed.
11. **Scripts must be safe to read before running**: dependency-free where possible, with no
    network calls unless that is the skill's purpose.

## When you add or change a skill

1. Create or edit `skills/<name>/SKILL.md`.
2. Add or update its row in the **Skills** table in `README.md`, keeping the table alphabetical.
3. Bump `version` in `.claude-plugin/plugin.json`: **minor** for a new skill (0.2.0 → 0.3.0),
   **patch** for fixes and wording (0.2.0 → 0.2.1). Without a bump, Claude Code users do not
   receive the change.
4. Validate (both must pass):

   ```bash
   claude plugin validate --strict .
   npx skills add . --list
   ```

5. Commit with Conventional Commits: `feat: Add <name> skill`, `fix(<name>): …`,
   `docs: …`. One skill per commit.

## Do not

- Edit `LICENSE`.
- Change `name` in either manifest; it would break every existing install.
- Add files outside this layout without a reason stated in the pull request.
