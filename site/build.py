"""Build the skills landing page: reads skills/*/SKILL.md, writes _site/index.html.

Standard library only. Run from the repo root: python site/build.py
"""

import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = "jars-demo/jars-skills"
OUT = ROOT / "_site"


def frontmatter(text: str) -> dict[str, str]:
    """Return the simple `key: value` pairs between the leading --- lines."""
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.S)
    if not match:
        return {}
    fields = {}
    for line in match.group(1).splitlines():
        key, sep, value = line.partition(":")
        if sep and not line.startswith((" ", "\t")):
            fields[key.strip()] = value.strip().strip("'\"")
    return fields


def split_description(description: str) -> tuple[str, str]:
    """Split a description into what the skill does and its 'Use when ...' part."""
    what, sep, when = description.partition("Use when")
    return what.strip(), (sep + when).strip() if sep else ""


def load_skills() -> list[dict[str, str]]:
    skills = []
    for path in sorted((ROOT / "skills").glob("*/SKILL.md")):
        meta = frontmatter(path.read_text(encoding="utf-8"))
        name = meta.get("name") or path.parent.name
        what, when = split_description(meta.get("description", ""))
        skills.append({"name": name, "what": what, "when": when})
    return skills


def card(skill: dict[str, str]) -> str:
    name = html.escape(skill["name"])
    command = f"npx skills add {REPO} --skill {name}"
    when = f'<p class="when">{html.escape(skill["when"])}</p>' if skill["when"] else ""
    return f"""
      <article class="skill" id="{name}">
        <h3><a href="https://github.com/{REPO}/blob/main/skills/{name}/SKILL.md">{name}</a></h3>
        <p>{html.escape(skill["what"])}</p>
        {when}
        <div class="cmd"><code>{command}</code><button type="button" data-copy="{command}">Copy</button></div>
      </article>"""


def main() -> None:
    skills = load_skills()
    version = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))["version"]
    page = (ROOT / "site" / "template.html").read_text(encoding="utf-8")
    page = (
        page.replace("{{REPO}}", REPO)
        .replace("{{COUNT}}", str(len(skills)))
        .replace("{{VERSION}}", html.escape(version))
        .replace("{{SKILLS}}", "".join(card(skill) for skill in skills))
    )
    OUT.mkdir(exist_ok=True)
    (OUT / "index.html").write_text(page, encoding="utf-8")
    (OUT / "CNAME").write_text("skills.jishanahmed.in\n", encoding="utf-8")
    print(f"Built _site/index.html with {len(skills)} skills (v{version})")


if __name__ == "__main__":
    main()
