---
name: env-setup
description: Get a project running locally from a clean clone — installs the right runtime, dependencies, and config, then confirms the baseline build and tests pass. Use when the user asks to set up a project, get it running, onboard to a repo, or fix a broken local environment. Reads the project's own docs and config files first; never assumes a stack without checking.
---

# Environment Setup

Take a freshly cloned (or broken) repository from zero to a working local environment: right
runtime version, dependencies installed, environment variables configured, and a passing
baseline build. Every step comes from what the project actually says, not from assumptions
about the stack.

## Ground rules

- **Read before running.** Check `README.md`, `CONTRIBUTING.md`, and any `docs/` setup guide
  before issuing commands. The project may have non-obvious steps or known gotchas.
- **Match the pinned versions.** Use whatever runtime version the project specifies
  (`.nvmrc`, `.python-version`, `.tool-versions`, `Volta` fields in `package.json`, etc.).
  Do not silently fall back to "latest".
- **Never write secrets into source files.** Copy `.env.example` → `.env`; fill in placeholders
  only with values the user explicitly provides. Stop and ask if secrets are required and none
  were given.
- **Report failures honestly.** If a setup step fails, say so. Do not skip a failing step and
  call the environment "set up".
- **Don't modify project files to work around setup problems.** Fix the environment; don't
  patch config to hide missing dependencies or version mismatches.

## Workflow

### 1. Understand what you're working with

```bash
# What stack is this?
ls -1                                # root layout
cat README.md                        # setup instructions
cat CONTRIBUTING.md 2>/dev/null      # dev-specific steps
ls docs/ 2>/dev/null                 # any docs/ setup guide
```

Look for:
- Runtime version pins: `.nvmrc`, `.python-version`, `.ruby-version`, `.tool-versions`,
  `Volta` key in `package.json`, `requires-python` in `pyproject.toml`
- Package manager lock files: `package-lock.json`, `yarn.lock`, `pnpm-lock.yaml`,
  `poetry.lock`, `uv.lock`, `Gemfile.lock`, `Cargo.lock`
- Environment variable template: `.env.example`, `.env.sample`, `.env.template`
- Docker / devcontainer: `docker-compose.yml`, `.devcontainer/`
- CI config for reference: `.github/workflows/`, `.circleci/`, `Makefile`

Build a mental map before running anything.

### 2. Install and activate the right runtime

**Node.js:**
```bash
cat .nvmrc                           # or package.json > volta.node
nvm install                          # reads .nvmrc automatically
nvm use
node --version                       # confirm
```

**Python:**
```bash
cat .python-version                  # or pyproject.toml requires-python
# pyenv
pyenv install <version>
pyenv local <version>
python --version

# or uv (reads .python-version automatically)
uv python install
```

**Ruby:**
```bash
cat .ruby-version
rbenv install <version>
rbenv local <version>
ruby --version
```

**Rust:**
```bash
cat rust-toolchain.toml              # or rust-toolchain
rustup override set <channel>
rustc --version
```

If no version file exists, note the absence to the user and proceed with the system runtime,
stating which version is in use.

### 3. Install dependencies

Use the lock file that exists — never switch package managers or regenerate lock files:

```bash
# Node
npm ci                               # if package-lock.json
yarn install --frozen-lockfile       # if yarn.lock
pnpm install --frozen-lockfile       # if pnpm-lock.yaml

# Python / uv (preferred)
uv sync                              # reads pyproject.toml + uv.lock

# Python / pip + requirements file
python -m venv .venv
source .venv/bin/activate            # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
pip install -r requirements-dev.txt 2>/dev/null

# Python / poetry
poetry install

# Rust
cargo build                          # also fetches deps

# Ruby
bundle install
```

If the install fails, read the error before retrying. Common fixes:
- Missing system library → note the `apt`/`brew` package needed, tell the user
- Wrong Node/Python version → go back to step 2
- Registry auth error → ask the user for credentials, don't embed them

### 4. Set up environment variables

```bash
ls -1a | grep -E '\.env'            # find any .env templates
cat .env.example                    # read what's needed
```

Copy the template:
```bash
cp .env.example .env
```

For each variable in the template:
- **Clearly optional / has default** → leave as-is, note it
- **Needs a real value to run locally** → tell the user what it is and ask them to fill it in
- **Secret (API key, DB password)** → never fill in a placeholder value; ask the user

If there's no `.env.example` but the code clearly reads env vars (grep for `process.env`,
`os.environ`, `ENV[`), list what you found and ask the user.

### 5. Run any project-specific setup steps

Check for common one-time setup commands:

```bash
# Database migrations
npm run migrate 2>/dev/null
python manage.py migrate 2>/dev/null
bundle exec rails db:setup 2>/dev/null

# Code generation
npm run generate 2>/dev/null
npx prisma generate 2>/dev/null

# Build step required before tests
npm run build 2>/dev/null
cargo build 2>/dev/null
```

Check the `Makefile` or README for a `setup`, `bootstrap`, or `init` target:
```bash
cat Makefile 2>/dev/null | grep -E '^(setup|bootstrap|init|install):'
make setup 2>/dev/null
```

### 6. Verify the baseline

Confirm the environment is working end-to-end:

```bash
# Type-check / compile
npm run build        # Node
tsc --noEmit         # TypeScript
python -m py_compile src/**/*.py   # Python syntax check
cargo check          # Rust

# Tests
npm test             # Node
python -m pytest     # Python
cargo test           # Rust
bundle exec rspec    # Ruby

# Linter (confirms tooling is wired up)
npm run lint 2>/dev/null
ruff check . 2>/dev/null
```

You're done when at least one of: build, type-check, or test suite passes cleanly. If the
test suite has pre-existing failures, note them explicitly — don't hide them.

### 7. Report back

Tell the user:

- Runtime version installed and active
- Package manager and total packages installed
- Which env vars are filled in vs still need values
- Build/test result (pass, fail with details, or skipped because not applicable)
- Any manual steps remaining (service to start, secret to fill in, system dep to install)

Keep it short. A bullet list is enough.

## Common blockers and how to handle them

| Symptom | Likely cause | What to do |
| --- | --- | --- |
| `ENOENT: node_modules` after `npm ci` | `package-lock.json` out of sync | Run `npm install` once, then tell the user to commit the lockfile |
| Python `ModuleNotFoundError` after install | Wrong venv active, or `pip install` hit the system Python | Confirm `which python` points into `.venv`; reactivate and retry |
| `Missing secret key` / `DATABASE_URL not set` | Required env var absent | Ask the user for the value; don't proceed without it |
| Compilation fails on a system library | Native dependency missing | Identify the library, show the `brew`/`apt` install command, ask user to run it |
| Tests pass but linter fails | Dev tool not installed | Run the linter install step from the README; if absent, skip and note it |

## Examples

| Weak | Strong |
| --- | --- |
| Run `npm install` on a repo without checking the lock file or Node version | Read `.nvmrc` first, `nvm use`, then `npm ci` |
| Fill `.env` with placeholder values and call it done | List which vars need real values, ask the user for secrets |
| Report "setup complete" after `npm install` exits 0 | Run `npm run build` and `npm test`; report which passed |
| Silently use Python 3.12 when the project pins 3.10 | Install 3.10 via pyenv/uv, activate it, confirm with `python --version` |
