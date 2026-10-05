# Contributing

Thanks for helping. Fixes, sharper wording, real-world examples, and new skill ideas are all
welcome.

## Ways to help

- **Report a problem**: open an issue with the skill name, the agent you used, what you asked,
  and what went wrong.
- **Improve a skill**: small, focused pull requests are easiest to review.
- **Propose a new skill**: open an issue first with the job it does and when it should load,
  so we can agree on scope before you write it.

## Writing a skill

Copy this into `skills/<your-skill-name>/SKILL.md`:

```markdown
---
name: your-skill-name
description: What it does in one sentence. Use when the user asks to <real phrases>, <more phrases>.
---

# Title

One paragraph: the outcome this skill produces.

## Ground rules

- Safety and honesty rules that always apply.

## Workflow

### 1. First step
Commands and decisions, in order.

### 2. Next step
...

## Examples

| Weak | Strong |
| --- | --- |
```

A good skill:

- **Does one job**, and its `description` says exactly when to use it.
- **Contains steps that were actually tried**, not guesses.
- **Defers to the project's own rules** and never pushes, publishes, or deletes unless asked.
- **Stays short**: under about 500 lines, with longer material in `references/`.

The full rules are in [AGENTS.md](AGENTS.md); they apply to people too.

## Before you open a pull request

1. Add your skill to the **Skills** table in `README.md` (alphabetical).
2. Bump `version` in `.claude-plugin/plugin.json`: minor for a new skill, patch for a fix.
3. Run both checks:

   ```bash
   claude plugin validate --strict .
   npx skills add . --list
   ```

4. Try the skill in a real agent session, and say in the pull request what you tested it on.
5. Use a Conventional Commits title, for example `feat: Add changelog skill` or
   `fix(commit-style): Clarify DCO sign-off`.

## License

By contributing, you agree that your contributions are licensed under the [MIT License](LICENSE).
