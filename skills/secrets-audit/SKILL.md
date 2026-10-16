---
name: secrets-audit
description: Scanning, detecting, and remediating accidentally committed secrets: runs gitleaks or trufflehog against the repo history, triages real findings from false positives, rotates the exposed credential immediately, rewrites history only when safe, and adds pre-commit hooks and CI checks to prevent recurrence. Use when you want to scan for secrets, find leaked credentials, check if I committed an API key, remove a secret from git history, add a secrets scanner to CI, or prevent secret leaks.
---

## secrets-audit

Scan for committed secrets, triage findings, rotate exposed credentials, and prevent recurrence.

### 1. Understand the scope first

Before scanning, clarify:

- Is this a first-time audit (full history) or a pre-commit / pre-merge check (new commits only)?
- Is the repo public or private? Public = treat every finding as already exposed.
- Are there known false-positive patterns (test fixtures, example keys, docs)?

### 2. Scan with gitleaks

gitleaks is fast, config-driven, and scans git history without checking out every commit.

**Install:**
```bash
# macOS
brew install gitleaks

# Linux / Windows (grab the binary from releases)
# https://github.com/gitleaks/gitleaks/releases

# Or via Docker (no install needed)
docker run --rm -v "$(pwd):/repo" ghcr.io/gitleaks/gitleaks:latest detect --source /repo
```

**Full history scan:**
```bash
gitleaks detect --source . --report-format json --report-path gitleaks-report.json
```

**Staged / uncommitted files only:**
```bash
gitleaks protect --staged
```

Review `gitleaks-report.json` — each finding includes `File`, `StartLine`, `Commit`,
`RuleID`, `Secret` (masked), and `Date`.

### 3. Scan with trufflehog (alternative / second opinion)

trufflehog verifies findings against live APIs where possible, which cuts false positives.

```bash
# Full git history
trufflehog git file://. --only-verified

# A specific branch
trufflehog git file://. --branch main --only-verified
```

Use `--only-verified` to focus on credentials that are provably still active. Remove the
flag when you want every pattern match regardless of liveness.

### 4. Triage findings

For each finding decide:

| Category | Signals | Action |
|----------|---------|--------|
| **Real, active** | Verified by trufflehog, or matches a known service pattern | Rotate immediately (step 5), then remediate history |
| **Real, already rotated** | Key format matches but revoked/expired | Remediate history, no urgent rotation needed |
| **False positive** | Test fixture, example in docs, placeholder like `EXAMPLE_KEY` | Add to `.gitleaks.toml` allowlist |

Never ignore a finding without confirming it is a false positive.

### 5. Rotate the exposed credential immediately

**Do this before touching git history.** An attacker who already cloned the repo has the
secret — rewriting history does not un-expose it.

1. Go to the service's dashboard (AWS IAM, GitHub Settings, Stripe, etc.).
2. Revoke / delete the exposed key.
3. Issue a new credential.
4. Update the new value in your secrets manager or `.env` file (never hardcode the replacement).
5. Verify the service still works with the new credential.

### 6. Remove the secret from history

**Option A — BFG Repo Cleaner (recommended for simple cases):**
```bash
# Replace the literal secret value everywhere in history
echo 'ACTUAL_SECRET_VALUE' > secrets-to-remove.txt
bfg --replace-text secrets-to-remove.txt
git reflog expire --expire=now --all
git gc --prune=now --aggressive
```

**Option B — git filter-repo (more control):**
```bash
pip install git-filter-repo
git filter-repo --path path/to/file/with/secret --invert-paths  # remove the file entirely
# or to scrub a value from all files:
git filter-repo --replace-text <(echo 'ACTUAL_SECRET==>***REMOVED***')
```

**Only force-push after the credential is rotated and team members are warned.**
Coordinate with anyone who has cloned the repo — they will need to re-clone or rebase.

> If the repo is public, assume the secret is permanently compromised regardless of history
> rewrite. Rotation is the only real mitigation.

### 7. Add a .gitleaks.toml to suppress known false positives

```toml
[allowlist]
  description = "Known false positives"
  regexes = [
    '''EXAMPLE_API_KEY''',
    '''test-secret-placeholder''',
  ]
  paths = [
    '''tests/fixtures/''',
    '''docs/examples/''',
  ]
  commits = [
    "abc123def456",  # historical commit with example key in README
  ]
```

Commit this file to the repo so the team benefits from the same allowlist.

### 8. Add a pre-commit hook

Catch secrets before they ever enter history.

**With pre-commit framework:**
```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.18.2
    hooks:
      - id: gitleaks
```

```bash
pip install pre-commit
pre-commit install
```

**Without pre-commit framework (plain git hook):**
```bash
# .git/hooks/pre-commit  (make executable: chmod +x)
#!/usr/bin/env bash
gitleaks protect --staged --redact --exit-code 1
```

### 9. Add a CI check

Block PRs that introduce new secrets.

**GitHub Actions:**
```yaml
# .github/workflows/secrets-scan.yml
name: Secrets Scan
on: [pull_request, push]

jobs:
  gitleaks:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0          # full history needed for accurate scanning
      - uses: gitleaks/gitleaks-action@v2
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

**GitLab CI:**
```yaml
secrets-scan:
  image: ghcr.io/gitleaks/gitleaks:latest
  script:
    - gitleaks detect --source . --exit-code 1
```

### 10. Verify and document

1. Re-run `gitleaks detect` after the history rewrite — confirm zero findings (or only known
   allowlisted patterns).
2. Confirm the rotated credential is working in all environments.
3. Record the incident: what leaked, when it was introduced, when it was found, and what was
   rotated. Even a one-paragraph note in a private doc helps with future audits.

### Rules

- Rotate before you rewrite history. Order matters.
- Never paste the actual secret value into a ticket, PR, or chat — even when reporting it.
- Do not commit `.env` files. Add `.env` to `.gitignore` and provide a `.env.example` with
  placeholder values.
- If the repo is on a shared platform (GitHub, GitLab), contact their security team — they
  can invalidate cached views of the old content.
- A pre-commit hook only protects the developer who has it installed. CI is the safety net
  that protects everyone.
