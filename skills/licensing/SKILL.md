---
name: licensing
description: Keep a repository's licensing correct and consistent. Audits the LICENSE file, README and package manifests so they agree, picks a licence for a new project, declares it with the right SPDX identifier, and checks that copied code, fonts, icons, logos and dependencies carry the notices their licences require. Use when the user asks which licence to use, to add or change a licence, to check licensing, to audit a repo or an org for licences, to copy code or assets from another project, to add a NOTICE or third-party notices file, to ask MIT vs Apache vs GPL, or whether a dependency's licence is safe to use.
---

## licensing

Make what a repository says about its licence true, consistent and complete. This is engineering
hygiene, not legal advice: when money, a contract, a company policy or a dispute is involved, say
so and tell the user to ask a lawyer.

### Ground rules

- **Never change a licence or a copyright holder without asking.** Relicensing is the author's
  decision, and code from other contributors may need their consent.
- **Never remove or edit someone else's copyright or licence notice.** Add to notices; do not
  rewrite them.
- **Never edit the licence text itself.** Tools detect licences by matching the exact text. Fill
  in only the copyright line (`[year] [fullname]` in MIT).
- **Do not push, publish or open pull requests** unless the user asked for that exact action.
- **Report what you did not check.** A clean manifest scan says nothing about dependency licences.

### 1. Find what the repository declares

A licence is declared in three places, and they must agree:

| Where | Who reads it | What to check |
|---|---|---|
| `LICENSE` (or `LICENSE.md`, `COPYING`) | Courts, GitHub, scanners | Exists, unmodified text, a copyright line with a real name and year |
| `README.md` | People | A **License** section that names the same licence and links `LICENSE` |
| Package manifests | PyPI, npm, licence scanners | The `license` field uses the same SPDX identifier |

```bash
ls LICENSE* COPYING* NOTICE* 2>/dev/null
grep -iE '^\s*copyright' LICENSE*
grep -niE '^#+ *licen[cs]e' -A3 README.md
grep -rnE --include=package.json '"license"\s*:' . | grep -v node_modules
grep -rnE --include=pyproject.toml '^license\s*=' .
grep -rnE --include=Cargo.toml '^license\s*=' .
```

For a GitHub org, check every repo that is not a fork:

```bash
gh repo list <org> --source --limit 200 --json name --jq '.[].name' |
  while read -r r; do
    echo "$r $(gh api repos/<org>/$r/license --jq .license.spdx_id 2>/dev/null || echo NONE)"
  done
```

Skip forks: they carry their upstream's licence and are not the user's to relicense.

Flag each of these:

- **No licence file.** Public code without a licence is "all rights reserved": others may view and
  fork it on GitHub, but may not copy, change or reuse it.
- **The three places disagree** (README says MIT, `LICENSE` is Apache-2.0, manifest is empty).
- **A copyright line naming someone else**, often left over from copying another project's file.
- **A manifest with no `license` field.** Private packages too: scanners read the manifest, not
  the README.
- **A non-SPDX value** such as `"MIT License"` or `"Apache 2"`. Use `MIT`, `Apache-2.0`,
  `BSD-3-Clause`, `GPL-3.0-only`, `GPL-3.0-or-later`, `MPL-2.0`, `ISC`.
- **npm's default `"ISC"`** left in a project that is actually MIT.

### 2. Choose a licence (new projects only)

Ask the user if they have not said. Offer this default:

| Situation | Choose | Why |
|---|---|---|
| Small library, tool, tutorial or workshop | `MIT` | Short, permissive, the easiest to comply with |
| Code you want companies to adopt, or a patent concern | `Apache-2.0` | Permissive, plus an explicit patent licence and patent-retaliation clause |
| Code meant to be contributed to an existing project | **The upstream project's licence** | Reviewers can merge it as is |
| The author wants changes shared back when distributed | `GPL-3.0-or-later` | Strong copyleft |
| The same, and the software runs as a hosted service | `AGPL-3.0-or-later` | Copyleft that also covers users over a network |
| Documentation, images, course text (not code) | `CC-BY-4.0` | Creative Commons suits content, not software |

Get the canonical text instead of typing it:

```bash
gh api licenses/mit --jq .body > LICENSE        # then fill in [year] [fullname]
gh api licenses/apache-2.0 --jq .body > LICENSE
```

### 3. Declare it everywhere

1. `LICENSE` at the repository root, canonical text, copyright line filled in.
2. README, as the last section:

   ```markdown
   ## License

   [MIT](LICENSE) © 2026 Your Name
   ```

3. Every manifest:

   ```toml
   # pyproject.toml (PEP 639: needs hatchling >= 1.27 or setuptools >= 77)
   [project]
   license = "MIT"
   ```

   ```json
   // package.json, even when "private": true
   "license": "MIT"
   ```

   Use `"UNLICENSED"` in `package.json` only for code that is genuinely not licensed to anyone.

4. Keep the line endings and formatting the files already use, so the diff is only the licence.

### 4. Copying code from another project

Before copying, read the source project's licence. Then:

| Source licence | You must |
|---|---|
| MIT, BSD, ISC | Keep its copyright line and licence text with the copied code (a header, or a third-party notices file) |
| Apache-2.0 | Do the same, **state what you changed**, and carry over the attribution lines from its `NOTICE` file into yours |
| MPL-2.0 | Keep the copied files under MPL-2.0 and their source available; the rest of your project is unaffected |
| GPL, AGPL | **Stop and ask.** Copying it into a permissive project makes the combined work GPL when you distribute it |
| No licence | **Stop.** You have no permission to copy it; ask the author or write your own |

Record each copy in a `NOTICE` file or `docs/third-party-notices.md`: what was copied, from where
(repository URL and commit), under which licence, and what you changed. See
[references/compatibility.md](references/compatibility.md) for which licences can be combined.

### 5. Fonts, icons and logos

Assets have licences too, and names and logos are also **trademarks**, which no software licence
grants.

- **Fonts**: most open fonts use the SIL Open Font License. Ship its licence file next to the font
  files (for example `fonts/OFL-Inter.txt`). Modified versions may not use the font's reserved name.
- **Icon sets**: check the set's licence (Lucide is ISC, Heroicons is MIT, Simple Icons is CC0) and
  keep it in your third-party notices.
- **Logos of other products**: use them only to identify that product. Say who owns the mark, that
  the project is not official or endorsed, and where the file came from. If the source repository
  has no licence, use the logo only for identification and offer to remove it on request.

A good NOTICE entry for a logo:

```text
app/public/logos/ contains the logos of Example DB and Example Cloud. They are
trademarks of their owners, used only to identify the systems this project
works with. This project is not official and is not endorsed by either.
```

### 6. Dependencies

Dependencies stay under their own licences. You must comply when you **distribute** them, which
includes Docker images, bundled frontends and vendored code.

```bash
npx --yes license-checker-rseidelsohn --summary          # Node
uvx pip-licenses --from=mixed --order=license             # Python (run inside the project's venv)
go-licenses report ./...                                  # Go
cargo deny check licenses                                 # Rust (needs a deny.toml)
```

Flag for the user, with the package name and version:

- `GPL-*`, `AGPL-*`, `LGPL-*` in anything you ship.
- **AGPL in a hosted service**: if you *modify* an AGPL program and let users reach it over a
  network, you must offer them its source. Running an unmodified AGPL server next to your app
  does not put your app under AGPL.
- `SSPL-1.0`, `BUSL-1.1`, `Elastic-2.0`, "Commons Clause": source-available, not open source, with
  limits on commercial or hosted use.
- `UNKNOWN`, `UNLICENSED`, or no licence at all.

### 7. Report

```text
Licensing: <repo or org>

Declared:   <licence> in LICENSE · README · <n> manifests   (or what disagrees)
Fixed:      <file>: <change>
Needs you:  <decision> - <why it is the user's call>
Not checked: <what was out of scope, e.g. dependency licences>
```
