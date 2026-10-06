---
name: changelog
description: Write a changelog entry for a release from commits, tags, and diffs. Use when the user asks to update CHANGELOG.md, write release notes, cut a version, or summarise what changed since the last tag. Follows Keep a Changelog format by default, respects the repo's own format when it exists, and never bumps the version or publishes without being asked.
---

# Changelog

Turn a set of commits into a clear, honest changelog entry that tells users what changed,
what broke, and what was fixed. Write for a reader upgrading their dependency, not for a
developer reading the commit log.

## Ground rules

- **The repository's format wins.** If a `CHANGELOG.md` already exists, match its structure,
  heading style, date format, and link style exactly. Read it before writing anything.
- **Write for users, not authors.** "Adds retry on upload timeout" beats "Implement exponential
  back-off loop in `uploader.ts`".
- **Never invent entries.** Every line comes from a commit, a diff, or something you ran.
  If you are unsure what a commit did, read the diff.
- **Never bump the version or publish** unless the user asks for that exact action.
- **Keep secrets and internal details out**: no internal URLs, customer names, stack traces,
  or log output.

## Workflow

### 1. Find what changed

```bash
git tag --sort=-version:refname | head -10   # recent tags
git log <last-tag>..HEAD --oneline           # commits since last release
git diff <last-tag>...HEAD --stat            # files touched
git diff <last-tag>...HEAD                   # full diff when needed
```

If there is no previous tag, use the first commit:

```bash
git rev-list --max-parents=0 HEAD
git log <first-commit>..HEAD --oneline
```

Also check:

- `package.json`, `pyproject.toml`, `Cargo.toml`, `build.gradle` — current version number
- `CHANGELOG.md` — existing format, last entry, link style
- `CONTRIBUTING.md` — any release process or changelog rules

### 2. Decide the version number

Use [Semantic Versioning](https://semver.org/) unless the repository uses something else:

| Change type | Version bump |
| --- | --- |
| Breaking change (removes API, changes behaviour) | Major: `2.0.0` |
| New feature, backwards-compatible | Minor: `1.3.0` |
| Bug fix, patch, internal change | Patch: `1.2.4` |

If the user gives you a version, use it. If not, propose one based on what you found and
explain why. Never change the version in any file unless the user confirms it.

### 3. Categorise the commits

Map commits to changelog sections. Use the repository's sections when they exist; otherwise
use [Keep a Changelog](https://keepachangelog.com/) categories:

| Section | What goes here |
| --- | --- |
| **Added** | New features, endpoints, commands, config options |
| **Changed** | Behaviour changes, renamed things, updated defaults |
| **Deprecated** | Features that still work but will be removed |
| **Removed** | Deleted features, endpoints, options, files |
| **Fixed** | Bug fixes |
| **Security** | Security fixes (always put these first if present) |

Ignore commits that are invisible to users:
- `chore:`, `ci:`, `style:`, `refactor:` (unless they change behaviour)
- Version bumps and lockfile updates
- Merge commits and `WIP` squashes

When a commit is unclear, read its diff to decide which section it belongs to.

### 4. Write the entry

Keep a Changelog format (default when no existing format):

```markdown
## [1.3.0] - 2026-10-06

### Security
- Fix path traversal in file upload endpoint (#88)

### Added
- Retry failed uploads up to three times with exponential back-off (#74)
- `--output-format` flag for `export` command: `json`, `csv`, `tsv` (#79)

### Changed
- `createUser` now requires an email address; username alone is no longer valid (#81)

### Fixed
- Dashboard fails to load when the user has no projects (#85)
- Export hangs on files larger than 100 MB (#83)

[1.3.0]: https://github.com/owner/repo/compare/v1.2.3...v1.3.0
```

**Style**

- Imperative, present tense: "Fix", "Add", "Remove" — not "Fixed", "Added".
- Lead with the user-visible outcome: "Retry failed uploads" not "Add retry loop".
- Include the PR or issue number in parentheses when one exists.
- One line per change. Split a big commit into multiple lines if it did multiple things.
- For breaking changes, add a **⚠ Breaking** prefix and describe the migration:
  `⚠ Breaking: \`createUser\` now requires \`email\`. Pass \`email\` alongside \`username\`.`

### 5. Insert into CHANGELOG.md

Place the new entry at the top, just below the `# Changelog` heading and any intro paragraph.
Keep all previous entries untouched.

```markdown
# Changelog

All notable changes to this project will be documented in this file.
See [Keep a Changelog](https://keepachangelog.com/) for format,
and [Semantic Versioning](https://semver.org/) for version numbers.

## [Unreleased]

## [1.3.0] - 2026-10-06
...previous entries...
```

Use `[Unreleased]` as a holding section if the project tracks unreleased work there.

### 6. Add comparison links

At the bottom of `CHANGELOG.md`, add or update the version links:

```markdown
[Unreleased]: https://github.com/owner/repo/compare/v1.3.0...HEAD
[1.3.0]: https://github.com/owner/repo/compare/v1.2.3...v1.3.0
[1.2.3]: https://github.com/owner/repo/compare/v1.2.2...v1.2.3
```

Find the remote URL with `git remote get-url origin`.

### 7. Hand it over

Show the user the new entry as ready-to-paste markdown. Point out:

- The proposed version number and why
- Any breaking changes you found
- Commits you skipped and why
- Anything you were unsure about

Wait for confirmation before writing to `CHANGELOG.md` or touching any version file.
When the user confirms, write the entry and stop. Do not tag, publish, or push unless asked.

## If CHANGELOG.md does not exist

Create it with this header, then add the first entry:

```markdown
# Changelog

All notable changes to this project will be documented in this file.
See [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) for format,
and [Semantic Versioning](https://semver.org/) for version numbers.

## [Unreleased]

## [x.y.z] - YYYY-MM-DD
...
```

## Examples

| Weak | Strong |
| --- | --- |
| `- Updated auth code` | `- Fix token refresh loop that logged users out after 15 minutes (#62)` |
| `- Changes to API` | `⚠ Breaking: \`GET /users\` no longer returns \`password_hash\`. Remove any client code that reads this field.` |
| `- Misc fixes` | `- Fix: dashboard crash on empty project list (#85)` |
| Listing every chore and CI commit | Only user-visible changes; skip infra noise |

## Anti-patterns to avoid

- **Copying commit subjects verbatim.** Commits are for authors; changelog entries are for
  users. Rewrite them.
- **Leaving `[Unreleased]` empty forever.** If the user is cutting a release, move those
  entries into the versioned section.
- **One giant entry per release.** Group by section, one line per logical change.
- **Guessing version numbers.** Propose and explain; let the user confirm.
