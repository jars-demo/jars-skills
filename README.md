# jars-skills

Practical [agent skills](https://agentskills.io): small, focused playbooks that teach a coding
agent how to do one job well. A new skill lands regularly; each one is a single folder with a
`SKILL.md` and works in Claude Code, Cursor, GitHub Copilot, Codex, Gemini CLI and other agents
that read the Agent Skills format.

## Install

**Claude Code** (plugin marketplace):

```
/plugin marketplace add jars-demo/jars-skills
/plugin install jars-skills@jars-skills
```

Or in one step (Claude Code 2.1.275+): `/plugin install jars-skills --marketplace jars-demo/jars-skills`.

Skills then load on their own when a task matches, or run one directly, e.g.
`/jars-skills:commit-style`. Update later with `/plugin marketplace update jars-skills`.

**Any agent** (via the [skills CLI](https://skills.sh)):

```bash
npx skills add jars-demo/jars-skills                       # pick from the list
npx skills add jars-demo/jars-skills --skill commit-style  # just one
```

**By hand:** copy a folder from `skills/` into your agent's skills directory, for example
`~/.claude/skills/commit-style/`.

## Skills

| Skill | Use it when |
| --- | --- |
| [commit-style](skills/commit-style/SKILL.md) | Committing changes: plans small logical commits, follows the repo's conventions, writes clear Conventional Commits messages, never pushes unasked. |

## Layout

```
.claude-plugin/       marketplace + plugin manifests (Claude Code)
skills/<name>/
  SKILL.md            name, description (when to use), and the playbook
  references/         optional extra docs the skill points to
  scripts/            optional helpers the skill runs
```

## Contributing

Issues and pull requests are welcome: fixes, sharper wording, or ideas for new skills.
A skill should do one job, say in its `description` exactly when to use it, and only contain
steps that were actually tried.

## License

[MIT](LICENSE) © Jishanahmed AR Shaikh
