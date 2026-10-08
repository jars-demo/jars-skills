"""Build the skills landing page: reads skills/*/SKILL.md, writes _site/index.html.

Standard library only. Run from the repo root: python site/build.py
"""

import html
import json
import re
import shutil
import subprocess
from datetime import date
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


def added_on(path: Path) -> str:
    """Date the file was first committed (ISO), or today for a skill not committed yet."""
    try:
        out = subprocess.run(
            [
                "git",
                "log",
                "--diff-filter=A",
                "--follow",
                "--format=%as",
                "--",
                str(path),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.split()
    except (OSError, subprocess.CalledProcessError):
        out = []
    return out[-1] if out else date.today().isoformat()


def load_skills() -> list[dict[str, str]]:
    skills = []
    for path in (ROOT / "skills").glob("*/SKILL.md"):
        meta = frontmatter(path.read_text(encoding="utf-8"))
        name = meta.get("name") or path.parent.name
        what, when = split_description(meta.get("description", ""))
        skills.append(
            {"name": name, "what": what, "when": when, "added": added_on(path)}
        )
    return sorted(skills, key=lambda skill: (skill["added"], skill["name"]))


def ticker_items(skills: list[dict[str, str]], repo: str) -> str:
    """Build the repeating ticker message string."""
    static = [
        ("JARS SKILLS", f"{len(skills)} skills published and counting"),
        ("INSTALL", f"npx skills add {repo}"),
        ("WORKS WITH", "Claude Code, Cursor, GitHub Copilot, Codex, Gemini CLI and more"),
        ("OPEN SOURCE", "MIT licence, contributions welcome"),
        ("FORMAT", "One skill per job, one file, under 500 lines"),
    ]
    # 3 most recent skills as news items
    recent = sorted(skills, key=lambda s: (s["added"], s["name"]), reverse=True)[:3]
    dynamic = [
        ("NEW SKILL", f"{s['name']}: {s['what'][:90].rstrip().rstrip('.')}")
        for s in recent
    ]
    all_messages = dynamic + static
    sep = '<span class="ticker-sep">|</span>'
    items = []
    for tag, msg in all_messages:
        items.append(
            f'<span class="ticker-item"><strong>{html.escape(tag)}</strong>{html.escape(msg)}</span>{sep}'
        )
    return "".join(items)


def pretty_date(iso: str) -> str:
    return date.fromisoformat(iso).strftime("%d %b %Y")


def row(number: int, skill: dict[str, str]) -> str:
    name = html.escape(skill["name"])
    command = f"npx skills add {REPO} --skill {name}"
    when = f'<p class="when">{html.escape(skill["when"])}</p>' if skill["when"] else ""
    return f"""
            <tr id="{name}" data-name="{name}" data-date="{skill["added"]}">
              <td class="num">{number}</td>
              <td class="name"><a href="https://github.com/{REPO}/blob/main/skills/{name}/SKILL.md">{name}</a></td>
              <td class="desc"><p>{html.escape(skill["what"])}</p>{when}</td>
              <td class="install-cell"><div class="cmd"><code>npx skills add <span>{REPO}</span> <span>--skill {name}</span></code><button type="button" data-copy="{command}">Copy</button></div></td>
              <td class="date"><time datetime="{skill["added"]}">{pretty_date(skill["added"])}</time></td>
            </tr>"""


def main() -> None:
    skills = load_skills()
    today = date.today().isoformat()
    today_skills = [s for s in skills if s["added"] == today]
    today_count = len(today_skills)
    today_label = today_skills[-1]["name"] if today_skills else "none yet"
    latest = sorted(skills, key=lambda s: (s["added"], s["name"]), reverse=True)[0] if skills else None
    latest_name = latest["name"] if latest else "—"

    version = json.loads(
        (ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
    )["version"]
    build_date = date.today().strftime("%d %b %Y").upper()
    page = (ROOT / "site" / "template.html").read_text(encoding="utf-8")
    page = (
        page.replace("{{REPO}}", REPO)
        .replace("{{COUNT}}", str(len(skills)))
        .replace("{{VERSION}}", html.escape(version))
        .replace("{{TODAY_COUNT}}", str(today_count))
        .replace("{{TODAY_LABEL}}", html.escape(today_label))
        .replace("{{LATEST_SKILL}}", html.escape(latest_name))
        .replace("{{BUILD_DATE}}", html.escape(build_date))
        .replace("{{TICKER_ITEMS}}", ticker_items(skills, REPO))
        .replace(
            "{{SKILLS}}", "".join(row(i, skill) for i, skill in enumerate(skills, 1))
        )
    )
    OUT.mkdir(exist_ok=True)
    for name in ("logo-800.png", "icon.png"):
        (OUT / "assets").mkdir(exist_ok=True)
        shutil.copy2(ROOT / "assets" / name, OUT / "assets" / name)
    (OUT / "index.html").write_text(page, encoding="utf-8")
    print(f"Built _site/index.html with {len(skills)} skills (v{version})")


if __name__ == "__main__":
    main()
