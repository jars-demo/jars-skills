---
name: commit-style
description: Write clean, reviewable git commits. Use when the user asks to commit, stage changes, split work into commits, write or fix a commit message, or prepare a branch for a pull request. Follows the repository's own conventions first, then Conventional Commits.
---

# Commit style

Turn a working tree into a short series of small, honest commits that a reviewer can read
top to bottom. Every commit does one thing, builds on its own, and says why it exists.

## Ground rules

- **The repository's rules win.** A `CONTRIBUTING.md`, `CLAUDE.md`, `AGENTS.md`, commitlint
  config, or PR template overrides anything in this skill. Read them before the first commit.
- **The user's rules win over the repository's defaults** for things the repository leaves open
  (identity, attribution lines, sign-off, whether to push).
- **Never push, force-push, amend a pushed commit, or rewrite history** unless the user asks for
  that exact action in this session.
- **Never skip hooks** (`--no-verify`) or signing. If a hook fails, fix the cause and commit
  again as a new attempt.
- **Never commit secrets.** Stop and tell the user if a staged file looks like one.

## Workflow

### 1. Learn the house style

```bash
git log --oneline -20                 # the format people actually use
git log -5 --format='%an <%ae>%n%B---' # bodies, trailers, sign-offs
git config user.name; git config user.email
```

Also check for `CONTRIBUTING.md`, `commitlint.config.*`, `.commitlintrc*`, `.czrc`,
`.pre-commit-config.yaml`, and `.github/pull_request_template.md`.

Note: the type list, whether scopes are used, the subject's capitalisation, issue-reference
style (`Fixes #12`, `COG-123`, `(SDK-898)`), and any required trailers (`Signed-off-by` for DCO).

If `user.name` / `user.email` are unset or look wrong for this repository, ask before committing.
Never change git config on your own.

### 2. Read the whole change

```bash
git status --short
git diff            # unstaged
git diff --staged   # already staged
```

Before staging anything, check for:

| Look for | Action |
| --- | --- |
| `.env`, keys, tokens, `*.pem`, credentials in code | Do not stage. Tell the user. |
| Build output, caches, `node_modules/`, `__pycache__/`, `dist/` | Do not stage. Suggest a `.gitignore` entry. |
| Large binaries or datasets | Ask first. |
| Debug prints, commented-out code, stray TODOs you added | Remove, or ask. |
| Unrelated edits mixed into one file | Stage by hunk (step 3). |

### 3. Plan the commits

Group the changes by **intent**, not by file. One commit equals one reason to change:

- a bug fix and the test that proves it: **one** commit
- a refactor and a feature built on it: **two** commits, the refactor first
- formatting-only changes: their **own** commit, so the real diff stays readable
- dependency bumps: their own commit, with lockfiles included

Order the commits so each one leaves the project working: the foundation first, then the
features, then the docs.

Tell the user the plan in one line per commit before you start, when there are more than two.

Stage precisely. Never use `git add -A` / `git add .` blindly on a mixed tree:

```bash
git add path/to/file another/file
git add -p path/to/file      # interactive; not available to agents without a TTY
```

When interactive staging is not available, write the intended version of a mixed file with only
one change applied, commit it, then restore the rest. Or ask the user to split it.

### 4. Write the message

Use the repository's format. When it has none, use
[Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<optional scope>): <Summary>

<Body: what changed and why. Wrap at 72 characters.>

<Footers: issue references, BREAKING CHANGE, trailers>
```

**Subject line**

- Imperative mood, as an instruction: "Add retry to upload", not "Added" or "Adds".
- 50 characters or fewer (hard limit 72), with no trailing period.
- Capitalise the summary unless the log shows lowercase is the convention.
- Say what the commit does, not how: "Fix timezone drift in reports", not "Change line 40".

**Types**

| Type | Use for |
| --- | --- |
| `feat` | New behaviour a user can notice |
| `fix` | Wrong behaviour made right |
| `docs` | Documentation only |
| `refactor` | Code change with no behaviour change |
| `perf` | Faster or leaner, same behaviour |
| `test` | Adding or fixing tests only |
| `build` | Build system, packaging, dependencies |
| `ci` | CI configuration and scripts |
| `style` | Formatting, whitespace, lint fixes |
| `chore` | Maintenance that fits nowhere else |
| `revert` | Reverting an earlier commit |

**Body** (skip it for a truly trivial change)

- Explain the **why**: the problem, the motivation, the trade-off you chose.
- Mention what a reviewer cannot see in the diff: a root cause, a measurement, a rejected
  alternative.
- Do not narrate the diff line by line. The code already shows how.

**Footers**

- Issue links in the repository's style: `Fixes #123`, `Refs COG-42`.
- `BREAKING CHANGE: <what breaks and how to migrate>` (also add `!` after the type: `feat!:`).
- Trailers only when the repository or the user requires them, e.g. `Signed-off-by:` (use
  `git commit -s`), or `Co-authored-by:` for real co-authors.

Pass multi-line messages safely, with a heredoc or a file, never with escaped `\n`:

```bash
git commit -F - <<'EOF'
fix(api): Return 400 for read-only query violations

Write queries sent to the read-only endpoint surfaced as a 500 with the
database's raw message. Map the error to a 400 that tells the user to
enable writes, so the UI can show a helpful hint.

Fixes #31
EOF
```

### 5. Verify each commit

```bash
git show --stat HEAD     # the right files, nothing extra
git log --oneline -5     # the series reads well
```

Run the project's fast checks (lint, format, unit tests) when they exist, so a commit never
breaks the build on its own. If a pre-commit hook rewrote files, stage those changes and commit
again. Do not bypass the hook.

### 6. Report

Finish with the list of commits made (`hash subject`), anything you deliberately left
unstaged and why, and whether anything was pushed (by default, nothing).

## Examples

| Bad | Good |
| --- | --- |
| `update stuff` | `fix(auth): Refresh expired tokens before retrying` |
| `Fixed the bug.` | `fix: Prevent double submit on slow networks` |
| `feat: added new dashboard page and also fixed lint and bumped deps` | Three commits: `build: Bump vite to 8.3.2`, `style: Apply lint fixes`, `feat(ui): Add usage dashboard page` |
| `WIP` | Squash the work-in-progress commits before review, if the user agrees |

## Splitting an existing messy commit (only when asked)

For an unpushed last commit:

```bash
git reset --soft HEAD~1   # keep the changes, staged
git reset                  # unstage everything
# then stage and commit in logical groups, as in steps 3 and 4
```

Never do this to commits that are already pushed or shared, unless the user explicitly asks
and understands that a force-push follows.
