# Brief template

A brief the user can paste into a long, unattended agent session. They change only the IDEA
line and fill the angle-bracket values once. When the user hands you a brief like this, treat
it as the full request, including any actions it asks for (creating the repo, pushing).

```markdown
IDEA: <topic, and optionally "continues <series>, after <previous repo>">

(Change only the line above. Everything below stays the same.)

Build a complete, production-grade, hands-on workshop about IDEA for the <org> GitHub org, end
to end, and push it. Decide everything yourself. Do not ask questions and do not stop halfway.
I will only read your final report.

Follow the jars-workshop-builder skill. Where it gives a default, use these values:

- Repo: <org>/<slug>-demo. Create it with `gh repo create <org>/<slug>-demo --public` if you
  can; otherwise build in a local folder and give me the commands.
- Site: https://<slug without hyphens>.<domain>
- License: MIT, <holder>, current year.
- Git identity: user.name "<name>", user.email "<email>", set in the repo.
- Reference repos: <tool lab repo URL> and <plain-Python lab repo URL>.
- Looks already used: <list, or "read them from the org's other repos">.

Push to main. Never force-push. Do not deploy.

If you have GitHub access, set the repo's description, homepage and 8 to 10 topics, and add the
workshop row to <org profile README path>. Otherwise put them in the report.
```

Notes for the agent:

- A brief that says "push" or "create the repo" is the user asking for that exact action.
- If the brief has rules about commit trailers or attribution, follow them as the user's
  instruction. Never misreport what ran.
