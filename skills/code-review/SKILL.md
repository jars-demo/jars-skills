---
name: code-review
description: Review pull requests and diffs like a senior engineer. Use when the user asks to review a PR, check code quality, analyze changes, or provide feedback on a branch or diff. Reads the actual code changes, flags real issues, groups feedback by severity, and never rubber-stamps.
---

# Code review

Give constructive, actionable feedback on a pull request or diff. Catch real problems — bugs,
security flaws, missing tests, unclear names — and explain why they matter and how to fix them.
Skip nitpicks unless they hide a real issue.

## Ground rules

- **The repository's rules win.** Check `CONTRIBUTING.md`, `CLAUDE.md`, `AGENTS.md`, linting
  configs, and the PR template for what the project cares about.
- **Read the actual code.** The PR description is the author's intent; the diff is the truth.
- **Flag real issues only.** A comment should prevent a bug, improve clarity, or catch a
  standard violation. Personal style preferences are not blockers.
- **Be specific and kind.** Point to the file, line, and function. Explain the problem and
  suggest a fix. Write for a peer, not a subordinate.
- **Never approve or merge** unless the user explicitly asks you to do so.

## Workflow

### 1. Read the context

```bash
gh pr view <number>                    # title, description, status, checks
gh pr diff <number>                    # the full diff
gh pr view <number> --json files -q '.files[].path'   # changed files list
```

Or for a local branch:

```bash
git diff <base>...<branch>
git log <base>..<branch> --oneline
```

Read the **full diff**, not just the file list. Know what actually changed before you comment.

Also check:

- **CI status**: failing tests, lint errors, build issues
- **PR size**: >500 lines often means multiple concerns mixed
- **Description quality**: does it explain the why and how to test?

### 2. Check for critical issues first

Review in priority order. Stop and flag the high-severity issues before commenting on style.

| Priority | What to catch |
| --- | --- |
| **Critical** | Security: SQL injection, XSS, exposed secrets, broken auth/authz, unsafe deserialization, path traversal |
| **High** | Logic bugs, null/undefined crashes, off-by-one errors, race conditions, data loss, incorrect error handling |
| **Medium** | Missing tests for new logic, untested edge cases, poor error messages, performance regressions (O(n²) in a loop) |
| **Low** | Confusing names, missing docs for public APIs, code duplication, inconsistent style (when no linter catches it) |

### 3. Analyze by area

Look at each change through these lenses:

**Correctness**

- Does the code do what the PR says it does?
- Are edge cases handled? (empty input, null, zero, max values, concurrent access)
- Are errors caught and surfaced clearly?
- Does it break existing behaviour? (Check call sites if unclear.)

**Security**

- User input: validated, sanitized, parameterized?
- Authentication/authorization checks in place?
- Secrets: are they hardcoded, logged, or returned in responses?
- File/path operations: are they safely bounded?

**Testing**

- Is new logic covered by tests?
- Are tests meaningful, or do they just call the code and assert `true`?
- Do failing test names clearly describe what broke?

**Maintainability**

- Are function and variable names clear without needing a comment?
- Is the code in the right place, or does it increase coupling?
- Does it follow the existing pattern, or introduce a new style for no reason?
- Are comments present only when the code cannot be made obvious?

**Performance**

- New O(n²) or O(n³) loops where n can be large?
- Unnecessary database queries inside loops?
- Large data loaded into memory when streaming would work?

### 4. Structure your feedback

Group comments by file, then by severity. Use this format:

```markdown
## Summary
One or two sentences: the overall quality, what's strong, and the main concern if any.

## Critical
- **file.py:42** — SQL injection risk: user input flows into raw query. Use parameterized queries.
- **auth.ts:15** — Missing permission check. Any user can delete any post. Add `requireOwner()`.

## High
- **api.py:88** — `result` can be `None` when the query fails, but line 92 calls `result.id` without a check. Wrap in `if result:` or return early.

## Medium
- **service.ts:120** — New `processItems()` has no tests. Add a test that covers the empty array case and the success path.
- **utils.py:200** — Iterating `get_user(id)` in a loop (O(n) queries). Fetch all users in one query before the loop.

## Low / Suggestions
- **README.md** — Deployment steps are missing the new `FEATURE_FLAG` env var.
- **api.ts:56** — `data` is vague. Rename to `requestPayload` or `userData`.

## Positive notes
- Clean separation between validation and business logic.
- Error messages are actionable.
- Tests cover the happy path and the two edge cases.
```

Skip sections with no findings. Scale the review to the change: a 10-line fix does not need
six paragraphs.

### 5. Decide: approve, request changes, or comment

| Verdict | When to use |
| --- | --- |
| **Request changes** | Critical or high-severity issues that must be fixed before merge. |
| **Comment** | Suggestions, questions, or low-priority feedback. The PR could merge as-is. |
| **Approve** | No issues, or only minor suggestions. The code is ready. |

**Do not approve by default.** If you found a critical or high issue, say "Request changes" and
explain what blocks the merge.

When the user asks you to post the review:

```bash
gh pr review <number> --comment --body-file - <<'EOF'
<your review markdown>
EOF

# or to request changes:
gh pr review <number> --request-changes --body-file - <<'EOF'
<your review markdown>
EOF

# or to approve:
gh pr review <number> --approve --body-file - <<'EOF'
<your review markdown>
EOF
```

Only post a review when the user explicitly asks. Drafting the review text is the default.

### 6. Suggest, don't rewrite

Your job is to **review**, not to implement the fix. Point out the issue, explain why it
matters, and describe or sketch the fix. Let the author write the code.

Exception: if the user asks you to apply a fix ("make that change"), then do it on a new branch
or commit.

## Examples

| Weak feedback | Strong feedback |
| --- | --- |
| "This looks bad." | "`user_input` is interpolated directly into the SQL string on line 42, allowing injection. Use a parameterized query: `cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))`." |
| "Add tests." | "`calculateDiscount()` has no tests. Add a test for the 0% case and the 100% case, since the function divides by `price` and could fail on zero." |
| "Naming could be better." | "`data` on line 88 is vague. Rename to `invoiceData` or `customerPayload` to match the other functions in this module." |
| "LGTM 🚀" (when there are real issues) | (Don't approve when problems exist. Be honest.) |

## Anti-patterns to avoid

- **Rubber-stamping**: approving without reading the diff.
- **Nitpicking style** when a linter should catch it: let the tools do that job.
- **Rewriting the PR**: reviewing is not the same as implementing.
- **Being vague**: "This could be better" does not help. Say what and why.
- **Bike-shedding**: long debates on subjective preferences (tabs vs spaces, names) when the
  code works and follows the repository's style.

## When the PR is too large

If the diff is >500 lines and mixes multiple concerns (refactor + feature + dependency bump),
suggest splitting it:

> This PR changes the auth system, adds the dashboard, and bumps three dependencies. Reviewing
> all of this together is hard. Could you split it into three PRs: (1) the auth refactor,
> (2) the dependency bumps, (3) the dashboard? That way each one is easier to test and approve.

## Notes

- If CI is red, check whether the failure is related to the change. If so, mention it in the
  review. If not, ask whether it's a known flaky test.
- When the PR description says "Tested manually" but provides no steps, ask for them. You need
  to know how to verify the fix.
- Screenshots and recordings for UI changes are often more useful than prose. Ask for them when
  they are missing.
