---
name: pr-description
description: Write a clear pull request title and description from the branch's actual changes. Use when the user asks to open, draft, or describe a pull request, fill in a PR template, or summarise a branch for review. Follows the repository's PR template and title rules, and never opens a PR without being asked.
---

# Pull request description

Give a reviewer everything they need to understand, trust, and test a change in a couple of
minutes: what changed, why, how it was verified, and what to look at closely. Every claim comes
from the diff, the commits, or something you actually ran.

## Ground rules

- **The repository's rules win.** Use its PR template, title format, issue-link style, and any
  required sections or checkboxes. Read `CONTRIBUTING.md`, `CLAUDE.md` / `AGENTS.md`, and
  `.github/pull_request_template.md` (or `.github/PULL_REQUEST_TEMPLATE/`) first.
- **Never open, push, or update a pull request** unless the user asks for that action. Drafting
  the text is the default deliverable.
- **Never claim something you did not do.** If tests were not run, say so. Do not tick a
  checklist box that is not true.
- **Keep secrets and private data out**: no tokens, internal URLs, customer names, or log lines
  with personal data.

## Workflow

### 1. Find the base and read the change

```bash
git branch --show-current
git remote -v
gh repo view --json defaultBranchRef -q .defaultBranchRef.name   # when gh is available
git log --oneline <base>..HEAD
git diff --stat <base>...HEAD
git diff <base>...HEAD
```

Use the base branch the repository expects. Some projects merge into `dev` or `develop`, not
the default branch. `CONTRIBUTING.md` usually says which.

Read the full diff, not only the commit messages. Commits describe intent; the diff is the
truth. Note anything the commits do not mention.

### 2. Check that the branch is ready

Before writing, look for things that would make the description dishonest or the review
painful:

| Check | If it fails |
| --- | --- |
| Uncommitted changes (`git status --short`) | Ask whether they belong in this PR. |
| Unrelated changes mixed in | Suggest splitting them into another PR. |
| Debug code, secrets, generated files | Flag them before anything else. |
| Tests and linters | Run the project's fast checks when possible, and record the result. |
| Branch behind the base | Mention it. Do not rebase or merge unless asked. |

### 3. Write the title

- Follow the repository's convention; check recently merged PRs with
  `gh pr list --state merged --limit 10`.
- Without a convention, use the same format as a good commit subject:
  `<type>(<scope>): <Summary>`, imperative, under about 70 characters.
- Include a required ticket key (for example `COG-123`) where the repository asks for one.

### 4. Write the description

Fill in the repository's template when it has one: keep its headings and order, and delete
nothing it requires. Otherwise use this structure:

```markdown
## Summary
One or two sentences: what this PR does and why it matters.

## Changes
- The meaningful changes, grouped by area, written for a reviewer.
- Mention behaviour changes, new config or env vars, migrations, and dependency bumps.

## Why
The problem or motivation. Link the issue. Mention alternatives you rejected when that
helps the reviewer.

## How to test
1. Exact steps or commands a reviewer can copy.
2. The expected result.

## Verification
- `pytest tests/unit` – 128 passed
- Checked manually: <what, where>
- Not tested: <anything you could not verify, and why>

## Notes for reviewers
Risky areas, follow-ups left out on purpose, screenshots for UI changes.

Fixes #123
```

**Style**

- Lead with the outcome, not the process. "Uploads now retry on 503" beats "I looked into the
  upload code and…".
- Be specific. Name files, functions, flags, and numbers where they help.
- Scale to the change: a one-line fix needs a two-line description. Drop empty sections
  instead of writing "N/A".
- For a breaking change, put a **Breaking change** section near the top, with the migration
  steps.
- For UI changes, ask the user for screenshots or a short recording; never invent them.

### 5. Hand it over

Show the title and description to the user as ready-to-paste text. When the user asks you to
open the PR, pass the body through a file or heredoc so the formatting survives:

```bash
gh pr create --base <base> --title "<title>" --body-file - <<'EOF'
<description>
EOF
```

Add `--draft` when the work is not ready for review, and only add reviewers, labels, or
assignees the user names.

## Updating an existing PR

When new commits land, update the description so it still matches the code: refresh
**Changes** and **Verification**, and do not silently drop earlier reviewer context. With
permission: `gh pr edit <number> --body-file -`.

## Examples

| Weak | Strong |
| --- | --- |
| Title: `Updates` | Title: `fix(api): Return 400 for writes on read-only queries` |
| "Fixed some bugs and cleaned up code." | "Write queries on the read-only endpoint returned a 500 with the raw database error. They now return a 400 that tells the user to enable writes." |
| "Tested." | "`pytest tests/test_api.py`: 15 passed. Ran a CREATE query from the UI with writes off and saw the new message." |
| A wall of text that retells each commit | A summary, grouped changes, steps to test, and what to look at closely |
