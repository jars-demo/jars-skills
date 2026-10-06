---
name: debug-session
description: Diagnose and fix bugs systematically. Use when the user reports an error, unexpected behaviour, a failing test, or a crash. Reads logs and code, reproduces the issue, isolates the root cause, fixes it, and verifies the fix — without guessing or changing code blindly.
---

# Debug session

Work through a bug methodically: understand what is broken, reproduce it, find the root cause,
fix only what needs fixing, and confirm it stays fixed. No blind changes, no guessing.

## Ground rules

- **Understand before touching code.** Read the error, the logs, and the relevant code first.
  A fix written without understanding the cause often creates a new bug.
- **One hypothesis at a time.** Form a theory, test it, confirm or rule it out, then move on.
- **Minimal fix.** Change only what the root cause requires. Do not refactor unrelated code
  while fixing a bug.
- **Verify the fix.** Run the failing test or reproduce the original steps after the fix.
  "It looks right" is not verification.
- **Never suppress an error to make it disappear.** Swallowing exceptions or adding
  `try/except: pass` is not a fix.
- **Report honestly.** Say what you found, what you changed, and what you could not verify.

## Workflow

### 1. Understand the symptom

Ask the user (or find in context):

- What is the exact error message, stack trace, or wrong behaviour?
- How do you reproduce it? (steps, command, request, input)
- When did it start? (after a deploy, a dependency bump, a code change?)
- Is it consistent or intermittent?

Read the full error. The last line of a stack trace is rarely the root cause — trace back up
to the first frame in your own code.

### 2. Reproduce it

Before changing anything, reproduce the issue:

```bash
# Run the failing test
pytest path/to/test_file.py::test_name -x
# or
npm test -- --testNamePattern "failing test name"

# Run the application and trigger the error
# Follow the exact steps the user described
```

If you cannot reproduce it, say so. An unreproducible bug needs more information before
any fix is attempted.

### 3. Read the relevant code

```bash
# Find where the error originates
grep -rn "FunctionName\|ErrorMessage" src/

# Read the file and the call chain around the error
```

Trace the execution path from the entry point to the crash:

- What inputs trigger it?
- What state or data does the code depend on?
- Where does the value come from that causes the problem?

Do not skim. Read the actual lines involved, not just the function signature.

### 4. Form a hypothesis

State your theory in one sentence before acting:

> "The crash happens because `user.profile` can be `None` when the user skips onboarding,
> but line 42 accesses `user.profile.avatar_url` without a null check."

A good hypothesis names:
- The specific condition that triggers the bug
- The specific line or function where it fails
- Why the code does the wrong thing there

If your hypothesis does not explain every symptom, keep looking.

### 5. Verify the hypothesis

Before writing a fix, confirm the theory:

- Add a temporary log or assertion to confirm the bad value is what you think it is
- Check whether the condition you identified actually occurs in the reproduction steps
- Read the git log for this file — was this code recently changed?

```bash
git log --oneline -10 -- path/to/file.py
git show <commit> -- path/to/file.py
```

If the hypothesis is wrong, go back to step 3. Do not skip this step and jump straight to
a fix.

### 6. Fix it

Write the minimal change that addresses the root cause:

| Root cause type | Fix approach |
| --- | --- |
| Null / undefined access | Guard with a check, return early, or ensure the value is always set |
| Wrong assumption about input | Validate input at the entry point; add a clear error for bad input |
| Off-by-one | Trace the index arithmetic; fix the boundary condition |
| Race condition | Add a lock, use an atomic operation, or remove the shared mutable state |
| Wrong error handling | Catch the right exception; surface it clearly; do not swallow |
| Stale cache / state | Invalidate at the right time, or remove the cache if it is not worth it |
| Dependency bug | Pin the last good version; add a comment; open an issue upstream |

Stage only the fix. Do not bundle unrelated changes into the same commit.

### 7. Verify the fix

```bash
# Re-run the exact reproduction steps
# Re-run the failing test
pytest path/to/test_file.py::test_name -x

# Run the full test suite for the affected area
pytest path/to/
```

Confirm:

- The original error no longer occurs
- Existing tests still pass
- No new errors or warnings appeared

If you added a temporary log or assertion in step 5, remove it now.

### 8. Write a regression test

If a test for this case does not exist, write one:

```python
def test_profile_access_when_onboarding_skipped():
    user = User(profile=None)
    # Should return a default, not raise AttributeError
    assert get_avatar_url(user) == DEFAULT_AVATAR
```

The test name should describe the bug scenario, not the implementation. If adding a test is
out of scope, say so and leave a `# TODO:` comment with the scenario.

### 9. Report

Summarise what you found and did:

```
Root cause: `user.profile` was None for users who skipped onboarding.
            Line 42 accessed `.avatar_url` without a guard.

Fix: Added an early return in `get_avatar_url()` that returns DEFAULT_AVATAR
     when `profile` is None.

Verified: `test_profile_access_when_onboarding_skipped` passes.
          Full unit suite: 94 passed, 0 failed.

Not verified: behaviour in production with real onboarding-skip users
              (no staging environment available).
```

## Intermittent bugs

For bugs that do not reproduce reliably:

- Ask for logs from multiple occurrences — look for a pattern (time of day, load, specific
  input, specific user)
- Check for shared mutable state, race conditions, or time-dependent logic
- Add structured logging around the suspect area and ask the user to capture the next
  occurrence
- Do not guess a fix for a bug you cannot reproduce

## When you are stuck

If after two hypotheses you have not found the cause:

1. Widen the search — read one level up in the call stack
2. Check recent changes: `git log --oneline -20 -- <affected area>`
3. Check for known issues: search the issue tracker or changelog for similar symptoms
4. Tell the user what you have ruled out and ask for more information (more logs, a
   minimal reproduction case, or access to the environment)

Do not keep making changes hoping something sticks.

## Examples

| Shortcut | Correct approach |
| --- | --- |
| Change the code until the error goes away | Reproduce → hypothesise → verify → fix |
| `except Exception: pass` | Catch the specific exception; handle or re-raise it |
| "It works on my machine" | Add logging; ask for the exact environment and inputs |
| Fix the symptom (hide the `None`) | Find why `None` is there; fix the upstream cause |
| Refactor the whole function while fixing a bug | Minimal fix first; refactor in a separate commit |
