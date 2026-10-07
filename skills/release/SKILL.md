---
name: release
description: Orchestrate a full release: bump the version, update the changelog, create a git tag, and draft release notes — ready to push when the user says so. Use when the user asks to cut a release, tag a version, ship a release, or publish a new version. Never pushes, publishes, or deploys without being explicitly asked.
---

# Release

Take a project from "changelog and version files up to date" to "tagged, release notes drafted,
ready to ship" in a single structured pass. Every step is shown to the user before it runs;
nothing is pushed or published until they say so.

## Ground rules

- **Read before writing.** Read `CHANGELOG.md`, version files, and recent commits before
  changing anything. Never guess the current version or what changed.
- **Propose the version; let the user confirm.** Derive a semver bump from the commit types
  found, explain the reasoning, and wait for approval before writing any file.
- **One commit for the release.** All version bumps and the changelog entry go in a single
  `chore(release): vX.Y.Z` commit. Don't mix release changes with feature work.
- **Never push or publish without being asked.** Create the tag locally and stop. Pushing,
  creating GitHub releases, running `npm publish`, or uploading artifacts are separate actions
  the user must explicitly request.
- **Never skip hooks.** Run `git tag` the normal way; don't use `--no-verify` or force flags.
- **If CI or pre-commit hooks fail, stop and report.** Don't work around them.

## Workflow

### 1. Confirm the baseline is clean

```bash
git status                            # must be clean before proceeding
git log --oneline -10                 # recent commits at a glance
git tag --sort=-version:refname | head -5   # last few tags
```

If there are uncommitted changes, stop and tell the user. A release must start from a clean tree.

### 2. Determine the new version

Read the version from the project's source of truth:

```bash
# Node
node -p "require('./package.json').version"

# Python
grep -E '^version' pyproject.toml | head -1
# or
grep '__version__' src/<package>/__init__.py

# Rust
grep '^version' Cargo.toml | head -1

# Generic
cat VERSION
```

Then read commits since the last tag to decide the bump:

```bash
git log <last-tag>..HEAD --oneline
```

Apply [Semantic Versioning](https://semver.org/):

| Commits contain | Bump |
| --- | --- |
| `feat!:`, `fix!:`, `BREAKING CHANGE:` | **Major** |
| Any `feat:` | **Minor** |
| Only `fix:`, `chore:`, `docs:`, `refactor:`, `perf:` | **Patch** |

Present the proposed version and reasoning. Wait for the user to confirm before writing files.

### 3. Update version files

Write the confirmed version to every file that owns it:

```bash
# Node — update package.json (and package-lock.json / yarn.lock)
npm version <new-version> --no-git-tag-version
# or pnpm / yarn equivalent
```

For non-Node projects, edit the version field in:
- `pyproject.toml` (`version = "x.y.z"`)
- `Cargo.toml` (`version = "x.y.z"`)
- `VERSION` file
- `__init__.py` or wherever the project declares `__version__`

Read each file first, make a targeted edit, and verify the change looks correct.

### 4. Update CHANGELOG.md

If the project has a `CHANGELOG.md`, move the `[Unreleased]` section into a versioned entry:

```markdown
## [X.Y.Z] - YYYY-MM-DD
```

Use today's date. Add the comparison link at the bottom:

```markdown
[X.Y.Z]: https://github.com/owner/repo/compare/vA.B.C...vX.Y.Z
```

If no `CHANGELOG.md` exists, skip this step but note it to the user. If the project uses
the `changelog` skill, call on it for the full categorised entry before running this step.

### 5. Show the full diff before committing

Display all staged changes so the user can review:

```bash
git diff HEAD
```

Point out:
- Which files were changed and why
- The proposed commit message
- The tag name that will be created

Wait for explicit confirmation before committing.

### 6. Commit and tag

Once the user confirms:

```bash
git add <version files> CHANGELOG.md
git commit -m "chore(release): vX.Y.Z"
git tag -a vX.Y.Z -m "Release vX.Y.Z"
```

Verify the tag was created:

```bash
git log --oneline -3
git tag --sort=-version:refname | head -3
```

### 7. Draft release notes

Prepare release notes the user can paste into GitHub Releases, PyPI, npm, or wherever they publish.
Pull the content from the changelog entry you just wrote (or from step 2 commits if there's no changelog):

```markdown
## What's changed in vX.Y.Z

### Added
- ...

### Fixed
- ...

### Breaking changes
- ...

**Full changelog:** https://github.com/owner/repo/compare/vA.B.C...vX.Y.Z
```

### 8. Stop and hand over

Tell the user:
- What was committed and tagged
- The exact commands to push when ready:

```bash
git push origin <branch>
git push origin vX.Y.Z
```

- Any extra publish steps for their ecosystem (e.g., `npm publish`, `cargo publish`, `uv publish`)

Do not run any of these unless the user asks.

## If the project has no tags yet

Treat the initial version as `0.1.0` (or `1.0.0` if the project is already used in production — ask the user). Use the first commit as the range base:

```bash
git rev-list --max-parents=0 HEAD
git log <first-commit>..HEAD --oneline
```

## Examples

| Weak | Strong |
| --- | --- |
| Bump version and push in one step | Bump → show diff → wait for confirm → commit + tag → tell user how to push |
| `git commit -m "release 1.4.0"` | `git commit -m "chore(release): v1.4.0"` |
| Skip changelog update | Move `[Unreleased]` entries into the versioned section before tagging |
| Create an annotated tag with an empty message | `git tag -a v1.4.0 -m "Release v1.4.0"` |
| Push tags silently | State the push command and wait for the user to run it |
