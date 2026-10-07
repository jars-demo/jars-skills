---
name: dependency-update
description: Audit outdated dependencies, review changelogs for breaking changes, update packages safely, and write a clean commit. Use when the user asks to update dependencies, upgrade packages, check for outdated deps, or bump a library version. Never upgrades a major version blindly — always reads the changelog first and surfaces breaking changes before touching any file.
---

# Dependency Update

Work through a dependency upgrade systematically: find what's outdated, read what changed,
update one layer at a time, verify the build still passes, and leave a clear commit. The goal
is to land updates that don't break anything and that a reviewer can audit in 30 seconds.

## Ground rules

- **Read the changelog before touching anything.** For any major or minor bump, find and read
  the migration guide or release notes. Never upgrade based on the version number alone.
- **Major versions require explicit user confirmation.** Flag the breaking changes you found,
  explain what migration work is likely needed, and wait for a go-ahead before updating.
- **One package at a time for risky upgrades.** Don't batch a major + two minors into one
  commit. Group patch updates together; keep each significant upgrade isolated.
- **Never push.** Stage, commit, and stop. The user decides when to push.
- **Never skip hooks or force-write lockfiles.** Use the package manager's standard update
  command so integrity checks and resolution logic run normally.
- **Tests must pass after every update.** If they don't, report the failure honestly — don't
  hide it, don't proceed with the next package.

## Workflow

### 1. Identify the package manager and current state

```bash
# Node / npm
cat package.json
npm outdated

# Node / yarn
yarn outdated

# Node / pnpm
pnpm outdated

# Python / pip
pip list --outdated

# Python / uv
uv pip list --outdated

# Rust
cargo outdated          # requires cargo-outdated

# Ruby
bundle outdated
```

Also check:
- `.nvmrc`, `.node-version`, `.python-version` — confirm you're on the right runtime
- `package.json` `"engines"` field or `pyproject.toml` `requires-python` — version constraints
- CI config (`.github/workflows/`, `Jenkinsfile`) — if it pins versions there too, note it

### 2. Triage the outdated list

Build a table before touching anything:

| Package | Current | Latest | Jump | Category |
| --- | --- | --- | --- | --- |
| `express` | 4.18.2 | 4.21.0 | patch/minor | safe to batch |
| `eslint` | 8.57.0 | 9.12.0 | **major** | needs changelog review |
| `axios` | 1.6.8 | 1.7.4 | minor | safe to batch |

Categories:
- **safe to batch** — patch or minor bumps with no noted breaking changes
- **needs changelog review** — any major bump, or a minor bump on a library known for sharp edges
- **skip** — packages the user hasn't asked about, or locked by a peer-dependency

### 3. Read the changelog for each significant bump

For every major version bump (and minors on critical libraries):

```bash
# Find changelog on npm
npm info <package> homepage
npm info <package> repository.url

# Or fetch directly
curl -s https://raw.githubusercontent.com/<owner>/<repo>/main/CHANGELOG.md | head -200
```

Look for:
- **Removed APIs** — will your codebase call something that no longer exists?
- **Renamed exports, config keys, or CLI flags**
- **Peer dependency changes** — does the new version require a different version of something else?
- **Node.js / Python minimum version bumps**

Report what you found before proceeding with a major bump. Wait for the user to confirm.

### 4. Apply updates

**Batch safe updates (patches and minors):**

```bash
# npm
npm update                           # patch + minor updates within semver ranges
npx npm-check-updates -u            # also update the ranges in package.json if needed
npm install

# yarn
yarn upgrade --latest --pattern "*" # or specify packages

# pnpm
pnpm update

# Python / uv
uv pip install --upgrade <package1> <package2>

# Python / pip
pip install --upgrade <package1> <package2>
pip freeze > requirements.txt       # if using a flat requirements file

# Rust
cargo update
```

**Individual major upgrade (confirmed by user):**

```bash
npm install <package>@<new-major>
# then apply any migration steps found in step 3
```

After each install, verify the lockfile changed as expected:

```bash
git diff package-lock.json   # or yarn.lock / pnpm-lock.yaml / Cargo.lock
```

### 5. Verify the build

Run the full check suite:

```bash
# Node
npm run build   # or tsc --noEmit
npm test

# Python
python -m pytest
# or
uv run pytest

# Rust
cargo build
cargo test
```

If anything fails:
1. Read the error carefully — it is usually a removed or renamed API.
2. Fix the call site, not the version pin.
3. If the fix is non-trivial, stop and report to the user before continuing.

### 6. Commit

Group related updates into logical commits:

```
chore(deps): update patch and minor dependencies

Bumped:
- axios 1.6.8 → 1.7.4
- eslint-plugin-react 7.34.3 → 7.35.1
- vitest 1.6.0 → 1.6.4
```

For a major upgrade, use a separate commit with more context:

```
chore(deps)!: upgrade eslint 8 → 9

Breaking changes from upstream:
- Flat config is now required; migrated eslint.config.js
- Removed --ext flag; now configured via ignores pattern

Ref: https://eslint.org/docs/latest/use/migrate-to-9.0.0
```

Use the repository's existing commit style if it differs from the examples above.

### 7. Report back

Tell the user:
- What was updated and to which version
- Any breaking changes found and how they were handled (or flagged for later)
- Any packages you skipped and why
- Any test failures still unresolved

## Examples

| Weak | Strong |
| --- | --- |
| Run `npm update` and commit everything | Triage first, batch safe updates, isolate majors |
| Upgrade `webpack` 4 → 5 without reading the migration guide | Read the [webpack 5 migration guide](https://webpack.js.org/migrate/5/) first, note breaking changes, confirm with user |
| `chore: bump deps` | `chore(deps): update axios 1.6.8 → 1.7.4, vitest 1.6.0 → 1.6.4` |
| Hide a failing test after the upgrade | Report the failure explicitly; fix or revert before committing |
