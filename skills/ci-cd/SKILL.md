---
name: ci-cd
description: Write, review, and fix CI/CD pipeline configurations for GitHub Actions, GitLab CI, and similar platforms. Use when the user asks to add a CI pipeline, set up GitHub Actions, write a workflow file, fix a failing pipeline, add a deploy step, set up staging or production deploys, wire up secrets, add branch protection, or speed up a slow pipeline.
---

# CI/CD

Write and fix pipeline configurations that build on every commit, test before merging, and
deploy only when things are green. Start from what the project already does, not from a
template you copied elsewhere.

## Ground rules

- **Read the project before touching the pipeline.** Check the runtime, package manager,
  build command, test command, and deploy target. A Node app and a Python app need different
  setup steps and caches.
- **Never push, deploy, or publish without being asked.** Pipelines should be written and
  committed locally. The user decides when to push.
- **Never put secrets in pipeline files.** Use the platform's secret store and reference
  secrets by name. Flag any hardcoded credential you find and tell the user to rotate it.
- **Respect the repo's existing pipeline setup.** If a workflow file already exists, read it
  before suggesting changes.
- **If the pipeline was passing and now it isn't, find the root cause.** Don't comment out
  steps or widen conditions to make a failing check go green.

---

## Step 0: Read the project first

```bash
# Runtime and tooling
cat .nvmrc || cat .node-version || cat .python-version || cat .tool-versions

# Build and test commands
cat package.json | grep -A 10 '"scripts"'    # Node
cat pyproject.toml | grep -A 5 '\[tool\.'    # Python
cat Makefile | head -40

# Existing CI config
ls .github/workflows/
ls .gitlab-ci.yml
ls Jenkinsfile
ls .circleci/config.yml

# Are there Docker or Compose files that the pipeline needs to know about?
ls Dockerfile* docker-compose*
```

Identify: the runtime version, install command, build command, test command, and whether
there is a deploy target and what environment it deploys to.

---

## GitHub Actions

### Minimal CI workflow (build + test on every push and PR)

```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Set up Node.js
        uses: actions/setup-node@v4
        with:
          node-version-file: .nvmrc     # or: node-version: "22"
          cache: npm

      - name: Install dependencies
        run: npm ci

      - name: Build
        run: npm run build

      - name: Test
        run: npm test
```

Adapt `setup-node` to `setup-python`, `setup-go`, `setup-java`, etc., depending on the
stack. Always use `node-version-file` (or the equivalent) when the project pins a version.

### Caching dependencies

Cache the package manager's store, not `node_modules`, so the cache works across OS updates:

```yaml
# Node (npm) — already handled by cache: npm in setup-node
# Node (pnpm)
- uses: pnpm/action-setup@v4
  with:
    version: 9
- uses: actions/setup-node@v4
  with:
    node-version-file: .nvmrc
    cache: pnpm

# Python (pip)
- uses: actions/setup-python@v5
  with:
    python-version-file: .python-version
    cache: pip

# Python (uv)
- name: Install uv
  uses: astral-sh/setup-uv@v5
  with:
    enable-cache: true
```

### Matrix builds (test across multiple versions)

```yaml
jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        node-version: ["20", "22"]
      fail-fast: false       # don't cancel all jobs when one version fails

    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: ${{ matrix.node-version }}
          cache: npm
      - run: npm ci
      - run: npm test
```

### Adding a deploy step

Deploy only from `main`, only after tests pass, and only when the user has set up the
required secrets.

```yaml
jobs:
  test:
    # ... (the CI job above)

  deploy:
    needs: test                  # only runs when test passes
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main' && github.event_name == 'push'
    environment: production      # enables environment protection rules in GitHub

    steps:
      - uses: actions/checkout@v4

      - name: Deploy
        env:
          DEPLOY_TOKEN: ${{ secrets.DEPLOY_TOKEN }}
        run: ./scripts/deploy.sh
```

Key points:
- `needs: test` — never deploy if tests fail.
- `if: github.ref == 'refs/heads/main'` — only deploy from the main branch.
- `environment: production` — links to a GitHub Environment so you can add required
  reviewers and environment-specific secrets.
- The secret is referenced as `${{ secrets.SECRET_NAME }}`, never hardcoded.

### Using secrets safely

```yaml
# Reference secrets from the GitHub secret store
- name: Authenticate
  env:
    API_KEY: ${{ secrets.API_KEY }}
  run: ./scripts/authenticate.sh

# For Docker Hub, AWS, GCP, etc., use the official actions
- name: Log in to Docker Hub
  uses: docker/login-action@v3
  with:
    username: ${{ secrets.DOCKERHUB_USERNAME }}
    password: ${{ secrets.DOCKERHUB_TOKEN }}
```

Tell the user which secret names the workflow expects so they can add them under
**Settings → Secrets and variables → Actions**.

### Pinning action versions

Always pin actions to a specific version tag. For security-sensitive actions (checkout,
login, deploy), pin to a commit SHA:

```yaml
# Version tag (acceptable for most actions)
- uses: actions/checkout@v4
- uses: actions/setup-node@v4

# Commit SHA (recommended for actions with write access or secret exposure)
- uses: aws-actions/configure-aws-credentials@e3dd6a429d7300a6a4c196c26e071d42e0343502
```

Never use `@main` or `@master` — third-party action code can change under you.

---

## GitLab CI

### Minimal pipeline

```yaml
# .gitlab-ci.yml
stages:
  - build
  - test
  - deploy

default:
  image: node:22-bookworm-slim
  cache:
    key:
      files:
        - package-lock.json
    paths:
      - node_modules/

build:
  stage: build
  script:
    - npm ci
    - npm run build
  artifacts:
    paths:
      - dist/
    expire_in: 1 hour

test:
  stage: test
  script:
    - npm ci
    - npm test

deploy:
  stage: deploy
  script:
    - ./scripts/deploy.sh
  environment:
    name: production
  rules:
    - if: $CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH
  variables:
    DEPLOY_TOKEN: $DEPLOY_TOKEN   # set in GitLab CI/CD settings → Variables
```

### GitLab secret variables

Secrets go in **Settings → CI/CD → Variables**. Reference them with `$VARIABLE_NAME`.
Mark sensitive variables as "Masked" and "Protected" (protected = only available on
protected branches/tags).

---

## Diagnosing a failing pipeline

### 1. Read the actual failure

```bash
# GitHub Actions: open the failing job in the Actions tab
# Look for the red step — expand it to see the full error

# GitLab CI: open the failing job in the pipeline view
```

Don't guess from the job name alone. The error message is almost always in the last 20
lines of the failing step's log.

### 2. Reproduce locally

Run the exact commands the CI job runs, in the same order:

```bash
npm ci          # not npm install — CI uses the lockfile
npm run build
npm test
```

If it passes locally but fails in CI, the cause is usually one of:
- A dependency that's in `devDependencies` but assumed in CI
- An environment variable or secret that's not set
- A file that's `.gitignore`d and not present in CI
- A platform difference (macOS vs Linux, different Node version)

### 3. Common failure patterns

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| `Cannot find module` | Dependency not installed or in wrong dep group | Move to `dependencies`, check `npm ci` ran |
| Tests pass locally, fail in CI | Missing env var | Add to repo secrets or CI variables |
| Cache hit but stale deps | Cache key doesn't include lockfile | Use `key: files: [package-lock.json]` |
| Timeout on install | No cache, or cache miss on every run | Fix the cache key |
| `Permission denied` on script | Script not executable in repo | `git update-index --chmod=+x scripts/deploy.sh` |
| Deploy runs on every branch | Missing branch condition | Add `if: github.ref == 'refs/heads/main'` |
| Old action version broken | Upstream action API changed | Pin to a newer version tag |

### 4. Checking the diff

If the pipeline was green and a recent commit broke it:

```bash
git log --oneline -10        # find the commit that broke it
git show <sha>               # what changed
git bisect start             # if the culprit isn't obvious
```

---

## Speeding up a slow pipeline

1. **Cache the right things.** Cache the package manager's store keyed on the lockfile.
   If the cache key is too broad (e.g., keyed on the branch name), it misses on most runs.

2. **Parallelize independent jobs.** Test and lint don't need each other — run them in
   parallel jobs in the same stage.

3. **Split slow test suites.** Use matrix builds or test-splitting tools
   (`jest --shard`, `pytest-split`, `go test -run`) to distribute across parallel runners.

4. **Use `npm ci` not `npm install`.** `npm ci` is faster and deterministic.

5. **Don't reinstall what you don't need.** If a deploy job only needs the built artifact,
   pass it via `artifacts` (GitLab) or `actions/upload-artifact` / `actions/download-artifact`
   (GitHub) instead of reinstalling all deps.

6. **Skip CI for non-code changes.** Add path filters to avoid running the full pipeline
   on doc-only commits:

   ```yaml
   # GitHub Actions
   on:
     push:
       paths-ignore:
         - "**.md"
         - "docs/**"
   ```

---

## Checklist before finishing

- [ ] Pipeline triggers are correct (push, PR, tag — not all three unless needed)
- [ ] Runtime version is pinned (`.nvmrc`, `node-version-file`, etc.)
- [ ] Dependencies are installed with the lockfile command (`npm ci`, `pip install -r requirements.txt`)
- [ ] Cache key includes the lockfile so it invalidates when deps change
- [ ] Tests must pass before deploy runs (`needs: test` / stage ordering)
- [ ] Deploy only runs from the intended branch
- [ ] No secrets hardcoded in the workflow file
- [ ] Secret names are documented for the user to add to the secret store
- [ ] Action versions are pinned (not `@main`)
- [ ] Pipeline runs green locally (simulate with [act](https://github.com/nektos/act) for GitHub Actions if needed)
