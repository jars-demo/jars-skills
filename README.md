<p align="center">
  <img src="assets/logo-800.png" alt="jars-skills" width="420" />
</p>

<p align="center">
  <a href="https://skills.jishanahmed.in">skills.jishanahmed.in</a>
</p>

# jars-skills

The agent skills I use most in my day-to-day work, shared in case they help you too.

I'm Jishanahmed AR Shaikh (Mr. JARS). I build and contribute to open source with coding agents
most days, and when I notice I'm explaining the same workflow to an agent again and again, I
write it down here as a skill.

Each skill is one folder with a `SKILL.md`: a short playbook that teaches an agent to do one job
the way I do it. They follow the [Agent Skills](https://agentskills.io) format, so they work in
Claude Code, Cursor, GitHub Copilot, Codex, Gemini CLI and other agents that read it.

I add them one at a time, aiming for one a day, and only after I've used the workflow for real.

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
| [pr-description](skills/pr-description/SKILL.md) | Opening or describing a pull request: reads the real diff, follows the repo's PR template, writes a reviewer-ready title and description with honest test notes. |

## Layout

```
.claude-plugin/       marketplace + plugin manifests (Claude Code)
skills/<name>/
  SKILL.md            name, description (when to use), and the playbook
  references/         optional extra docs the skill points to
  scripts/            optional helpers the skill runs
```

## Contributing

Issues and pull requests are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for how to write a
skill, and [AGENTS.md](AGENTS.md) for the rules every skill follows.

## License

[MIT](LICENSE) © Jishanahmed AR Shaikh
