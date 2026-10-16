---
name: env-config
description: Designing a typed, validated configuration system: centralises all env var reads into one config module, validates and fails fast at startup with a clear error, distinguishes secrets from plain config, maintains a .env.example with every key documented, and prevents os.environ / process.env scattered across the codebase. Use when you want to set up config properly, validate environment variables at startup, add a config module, manage secrets vs config, structure .env files, fail fast on missing config, or stop using os.environ everywhere.
---

## env-config

Design the config system once, in one place. Every other module reads from it — never from
the environment directly.

### 1. The core rule

```
os.environ  /  process.env  /  ENV[]
    ↓ read exactly once
config/settings.py  (or config.ts / config.go)
    ↓ imported by
everything else
```

If any module outside `config/` calls `os.environ.get`, `process.env.X`, or `os.getenv`
directly — move it into the config module. One place to look, one place to fix.

---

### 2. Distinguish secrets from plain config

| Type | Examples | Where it lives |
|------|----------|----------------|
| **Secret** | DB password, API keys, JWT secret | Secrets manager (AWS SSM, Vault, Doppler) or `.env` — never committed |
| **Plain config** | Port, log level, feature flags, timeout values | `.env` or environment — safe to commit as defaults in `.env.example` |
| **Build-time constant** | App name, version | Hardcoded or read from `package.json` / `pyproject.toml` |

Never put a secret in a config file that is committed. Never put plain config in a secrets
manager — it creates operational overhead for no security gain.

---

### 3. Python — typed config with Pydantic Settings

```python
# config/settings.py
"""
config/settings.py
------------------
Single source of truth for all application configuration.
Reads from environment variables (and .env file in development).
Fails fast at import time if any required variable is missing or invalid.

Depends on: pydantic-settings
Used by:    every module that needs config — import settings, never os.environ
"""

from pydantic import AnyHttpUrl, Field, PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ── Server ────────────────────────────────────────────────────────────
    app_env: str = Field("development", pattern="^(development|staging|production)$")
    port: int = Field(8000, ge=1, le=65535)
    log_level: str = Field("INFO", pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$")

    # ── Database ──────────────────────────────────────────────────────────
    database_url: PostgresDsn  # required — no default, startup fails if missing

    # ── Auth ──────────────────────────────────────────────────────────────
    jwt_secret: str = Field(min_length=32)   # required, enforced minimum length
    jwt_expiry_seconds: int = Field(3600, ge=60)

    # ── External services ─────────────────────────────────────────────────
    email_provider_api_key: str              # required
    email_from_address: str

    # ── Optional / feature flags ──────────────────────────────────────────
    rate_limit_enabled: bool = True
    max_requests_per_minute: int = Field(60, ge=1)


# Module-level singleton — validated once at startup, shared everywhere.
# If any required field is missing or invalid, this raises immediately with
# a clear error message naming the exact variable that failed.
settings = Settings()
```

```python
# Usage anywhere in the app — never os.environ
from config.settings import settings

def connect_database():
    return create_engine(str(settings.database_url))

def build_jwt(user_id: int) -> str:
    return jwt.encode({"sub": user_id}, settings.jwt_secret, algorithm="HS256")
```

**Install:**
```bash
uv add pydantic-settings   # or: pip install pydantic-settings
```

---

### 4. Node.js / TypeScript — typed config with zod

```ts
// config/settings.ts
/**
 * config/settings.ts
 * ------------------
 * Single source of truth for all application configuration.
 * Parses and validates process.env at startup — throws on first missing or
 * invalid variable so the app never starts with bad config.
 *
 * Depends on: zod, dotenv
 * Used by:    every module that needs config — import { settings }, never process.env
 */

import { z } from 'zod';
import 'dotenv/config';   // loads .env into process.env before validation

const schema = z.object({
  // Server
  NODE_ENV: z.enum(['development', 'staging', 'production']).default('development'),
  PORT:     z.coerce.number().int().min(1).max(65535).default(3000),
  LOG_LEVEL: z.enum(['debug', 'info', 'warn', 'error']).default('info'),

  // Database
  DATABASE_URL: z.string().url(),   // required — no default

  // Auth
  JWT_SECRET:         z.string().min(32),
  JWT_EXPIRY_SECONDS: z.coerce.number().int().min(60).default(3600),

  // External services
  EMAIL_API_KEY:      z.string().min(1),
  EMAIL_FROM_ADDRESS: z.string().email(),

  // Feature flags
  RATE_LIMIT_ENABLED:      z.coerce.boolean().default(true),
  MAX_REQUESTS_PER_MINUTE: z.coerce.number().int().min(1).default(60),
});

const parsed = schema.safeParse(process.env);

if (!parsed.success) {
  console.error('❌  Invalid configuration — fix these before starting:\n');
  parsed.error.issues.forEach((issue) => {
    console.error(`  ${issue.path.join('.')}: ${issue.message}`);
  });
  process.exit(1);   // fail fast — never start with bad config
}

export const settings = parsed.data;
```

```ts
// Usage anywhere in the app
import { settings } from '../config/settings';

const db = new Pool({ connectionString: settings.DATABASE_URL });
```

**Install:**
```bash
npm install zod dotenv
```

---

### 5. .env files — one template, never committed secrets

```bash
# .env.example  ← committed to git, no real values
# Copy to .env and fill in the required values before running locally.

# ── Server ────────────────────────────────
APP_ENV=development
PORT=8000
LOG_LEVEL=INFO

# ── Database (required) ───────────────────
# Format: postgresql://user:password@host:5432/dbname
DATABASE_URL=

# ── Auth (required) ───────────────────────
# Must be at least 32 characters. Generate with: openssl rand -hex 32
JWT_SECRET=
JWT_EXPIRY_SECONDS=3600

# ── Email provider (required) ─────────────
# Get from: https://app.youremailprovider.com/api-keys
EMAIL_PROVIDER_API_KEY=
EMAIL_FROM_ADDRESS=noreply@example.com

# ── Feature flags ─────────────────────────
RATE_LIMIT_ENABLED=true
MAX_REQUESTS_PER_MINUTE=60
```

**Rules for `.env.example`:**
- Every key the app reads must appear here — no undocumented env vars.
- Required keys have an empty value and a comment explaining where to get it.
- Optional keys have their default value filled in.
- Include a generation command for secrets (`openssl rand -hex 32`).
- Commit `.env.example`. Never commit `.env`.

**`.gitignore`:**
```
.env
.env.local
.env.staging
.env.production
```

---

### 6. Multi-environment strategy

```
.env.example        ← committed template (no values)
.env                ← local dev (gitignored, filled in by developer)
.env.test           ← test overrides (can be committed if no secrets)
```

For staging and production — **do not use `.env` files on servers.** Inject variables
directly through the deployment platform:

| Platform | How to inject |
|----------|--------------|
| Docker / Compose | `environment:` block or `--env-file` flag |
| Kubernetes | `ConfigMap` (plain) + `Secret` (sensitive) → `envFrom` |
| AWS ECS | Task definition environment / SSM parameter store |
| Heroku / Render / Railway | Dashboard config vars |
| GitHub Actions | Repository secrets → `env:` in workflow |

Never write a `.env.production` file. If it exists, it will eventually be committed.

---

### 7. Fail fast — what good startup output looks like

```
# ✅ Good — missing config caught immediately, clear message
$ python main.py
ValidationError: 1 validation error for Settings
database_url
  Field required [type=missing, input_value={'APP_ENV': 'development'...}]
  Hint: set DATABASE_URL in your .env file
  Format: postgresql://user:password@host:5432/dbname

# ❌ Bad — missing config causes a cryptic crash deep in the app
$ python main.py
Traceback (most recent call last):
  File "repositories/user_repository.py", line 47, in connect
    engine = create_engine(os.environ["DATABASE_URL"])
KeyError: 'DATABASE_URL'
```

The difference: config validated at the module boundary catches the problem at startup.
`os.environ` scattered through the code crashes wherever it's first called.

---

### Rules

- Read env vars in exactly one file. Grep for `os.environ`, `process.env`, `ENV[` — any
  hit outside the config module is a bug to fix.
- Validate type and constraints at startup — port is an integer in range, URL is a valid URL,
  secret meets minimum length. A bad value caught at startup is better than a crash at 2am.
- Document every key in `.env.example`. If a key is missing from the template, the next
  developer will spend an hour finding it.
- Never log the config object at startup — it contains secrets. Log only non-sensitive fields
  (`app_env`, `port`, `log_level`) to confirm the app started with the right profile.
- Never use `os.environ.get("KEY", "")` as a fallback for a required value. An empty string
  is not the same as "not set" — it will pass validation silently and fail mysteriously later.
