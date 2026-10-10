---
name: docker
description: Write, review, and fix Dockerfiles, Compose files, and container build configurations. Use when the user asks to write a Dockerfile, containerize an app, fix a slow build, reduce image size, write a docker-compose.yml, set up a multi-service stack, add a healthcheck, fix a build error, or debug a container that won't start.
---

# Docker

Write Dockerfiles and Compose files that build correctly, stay small, use layer caching
well, and don't leak secrets or run as root.

## Ground rules

- **Read the project first.** Check the runtime, package manager, build tool, and port
  before writing a single line. A Node.js app and a Python app need different base images,
  install steps, and signal handling.
- **Never copy secrets into the image.** No `.env` files, no API keys, no credentials in
  `COPY`, `ENV`, or `ARG` that end up in the final layer. Use runtime environment variables
  or secrets mounts.
- **Never run as root in production images.** Create a non-root user and switch to it
  before the final `CMD`.
- **Respect the repo's existing Docker setup.** If a `Dockerfile` already exists, read it
  before replacing it.
- **Never push, publish, or deploy** unless the user explicitly asks for that action.

---

## Step 0: Read the project

Before writing anything:

```bash
# What runtime and version does the project need?
cat .nvmrc || cat .node-version || cat .python-version || cat .tool-versions

# What does the build/start look like?
cat package.json | grep -E '"scripts"' -A 10   # Node
cat pyproject.toml | grep -E 'build|start'      # Python
cat Makefile | head -30

# Does a Dockerfile already exist?
ls -la Dockerfile* docker-compose* .dockerignore
```

Note: the runtime version, the build command, the start command, the port the app listens
on, and whether there are any native dependencies that need system packages.

---

## Writing a Dockerfile

### Use the right base image

| Stack | Development | Production |
| --- | --- | --- |
| Node.js | `node:<version>-bookworm` | `node:<version>-bookworm-slim` |
| Python | `python:<version>-bookworm` | `python:<version>-slim-bookworm` |
| Go | `golang:<version>-bookworm` | `gcr.io/distroless/static-debian12` |
| Java | `eclipse-temurin:<version>-jdk` | `eclipse-temurin:<version>-jre-jammy` |
| Static binary | — | `scratch` or `gcr.io/distroless/static` |

- Pin the version tag. Never use `latest` — it breaks reproducible builds.
- Prefer `slim` / `distroless` for production. They have fewer CVEs and smaller attack
  surface.
- Check the project's required version exactly: `node:22-bookworm-slim` not `node:slim`.

### Multi-stage builds

Always use multi-stage for compiled languages and for Node/Python apps where dev
dependencies must not ship to production.

```dockerfile
# ── Stage 1: build ──────────────────────────────────────────────
FROM node:22-bookworm-slim AS builder

WORKDIR /app

# Copy manifests first — cached as long as deps don't change
COPY package.json package-lock.json ./
RUN npm ci --ignore-scripts

COPY . .
RUN npm run build

# ── Stage 2: production ─────────────────────────────────────────
FROM node:22-bookworm-slim AS production

WORKDIR /app

# Install only production deps in the final stage
COPY package.json package-lock.json ./
RUN npm ci --omit=dev --ignore-scripts

# Copy the built output from the builder stage
COPY --from=builder /app/dist ./dist

# Non-root user
RUN addgroup --system --gid 1001 appgroup && \
    adduser --system --uid 1001 --ingroup appgroup appuser
USER appuser

EXPOSE 3000
CMD ["node", "dist/server.js"]
```

### Layer caching: the most important optimisation

Docker rebuilds every layer after the first changed layer. Dependency installs are slow —
put them before `COPY . .`:

```dockerfile
# WRONG: invalidates the npm install on every code change
COPY . .
RUN npm ci

# CORRECT: npm install is cached until package.json changes
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
```

The pattern: **copy manifests → install → copy source → build**.

### .dockerignore

Always create or update `.dockerignore` to exclude:

```
.git
.env
.env.*
node_modules
__pycache__
*.pyc
dist
build
.pytest_cache
.coverage
*.log
README.md
```

Without `.dockerignore`, `COPY . .` sends `node_modules` (potentially hundreds of MB)
and `.env` (secrets) into the build context.

### Non-root user

```dockerfile
# Debian/Ubuntu-based images
RUN addgroup --system --gid 1001 appgroup && \
    adduser --system --uid 1001 --ingroup appgroup appuser
USER appuser

# Alpine-based images
RUN addgroup -S appgroup && adduser -S appuser -G appgroup
USER appuser
```

If the app writes files (uploads, logs, SQLite), ensure the target directory is owned by
the app user before switching:

```dockerfile
RUN mkdir -p /app/data && chown appuser:appgroup /app/data
USER appuser
```

### Signal handling and PID 1

Node and Python do not handle `SIGTERM` correctly as PID 1. Use `tini` or the exec form
of CMD to ensure clean shutdown:

```dockerfile
# Option A: tini (explicit, works everywhere)
RUN apt-get install -y --no-install-recommends tini
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["node", "dist/server.js"]

# Option B: exec form directly (works when the process handles signals itself)
CMD ["node", "dist/server.js"]   # exec form — NOT ["sh", "-c", "node dist/server.js"]
```

Never use `CMD node dist/server.js` (shell form) — the shell becomes PID 1 and swallows
signals.

### Healthcheck

Add a healthcheck so Docker and Compose know when the service is actually ready:

```dockerfile
HEALTHCHECK --interval=10s --timeout=5s --start-period=15s --retries=3 \
  CMD node -e "require('http').get('http://localhost:3000/health', r => process.exit(r.statusCode === 200 ? 0 : 1)).on('error', () => process.exit(1))"
```

For distroless or minimal images with no shell, use exec form:

```dockerfile
HEALTHCHECK --interval=10s --timeout=5s --start-period=15s --retries=3 \
  CMD ["/usr/bin/grpc_health_probe", "-addr=:50051"]
```

---

## Writing a docker-compose.yml

Use Compose for local development and multi-service stacks. Use explicit service names,
pinned image versions, and health-gated dependencies.

```yaml
services:
  app:
    build:
      context: .
      target: production      # target the prod stage, not the builder
    ports:
      - "3000:3000"
    environment:
      - NODE_ENV=production
      - DATABASE_URL=postgresql://postgres:postgres@db:5432/myapp
    depends_on:
      db:
        condition: service_healthy   # wait for the real healthcheck, not just "started"
    restart: unless-stopped

  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: myapp
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 5s
      retries: 10
      start_period: 10s

volumes:
  postgres_data:
```

Key rules:
- `depends_on: condition: service_healthy` — not just `depends_on: db`. Without the
  condition, Compose starts the dependent before the database is ready to accept connections.
- Never hardcode passwords in `docker-compose.yml` for anything beyond local dev. Use
  `docker-compose.override.yml` or a `.env` file that is in `.gitignore`.
- Pin image versions: `postgres:16-alpine`, not `postgres:latest`.

### Development override

Keep dev-only config out of the production Compose file:

```yaml
# docker-compose.override.yml  (loaded automatically in dev, not in CI)
services:
  app:
    build:
      target: builder          # use the dev stage with hot reload
    volumes:
      - .:/app                 # mount source for live reload
      - /app/node_modules      # anonymous volume to prevent host modules overwriting container's
    environment:
      - NODE_ENV=development
    command: npm run dev
```

---

## Reducing image size

1. **Use multi-stage builds** — build tooling stays in the builder stage.
2. **Use slim or distroless base images** — `node:22-bookworm-slim` is ~200MB vs ~1GB for `node:22`.
3. **Combine RUN commands** to avoid intermediate layers with leftover apt cache:
   ```dockerfile
   # WRONG: leaves apt cache in a layer
   RUN apt-get update
   RUN apt-get install -y curl
   
   # CORRECT: clean up in the same layer
   RUN apt-get update && \
       apt-get install -y --no-install-recommends curl && \
       rm -rf /var/lib/apt/lists/*
   ```
4. **Use `--no-install-recommends`** with apt to skip optional packages.
5. **Don't install dev tools in the production stage** — debuggers, compilers, test runners.

Check the final image size and layer breakdown:

```bash
docker build -t myapp .
docker images myapp
docker history myapp   # layer-by-layer size breakdown
```

---

## Debugging build failures

### Build fails during package install

```bash
# Run the failing RUN step interactively to see the real error
docker run --rm -it <base-image> bash
# then run the install command manually
```

### Build produces wrong output

```bash
# Inspect the builder stage specifically
docker build --target builder -t myapp-debug .
docker run --rm -it myapp-debug bash
ls dist/   # did the build output land where you expected?
```

### Container exits immediately

```bash
docker run --rm myapp           # run without -d to see output
docker logs <container-id>      # if it was already started
docker inspect <container-id>   # check exit code and OOMKilled
```

### Container starts but app misbehaves

```bash
# Check what's actually running inside
docker exec -it <container> sh   # or bash if available
env                              # are environment variables set correctly?
ps aux                           # is the process actually running?
```

---

## Common mistakes

| Mistake | Fix |
| --- | --- |
| `COPY . .` before `npm install` | Copy manifests first, install, then copy source |
| `latest` tag on base image | Pin the exact version: `node:22-bookworm-slim` |
| `.env` not in `.dockerignore` | Add `.env*` to `.dockerignore` |
| Running as root | Add a non-root user, `USER appuser` before `CMD` |
| Shell form CMD: `CMD npm start` | Exec form: `CMD ["node", "dist/server.js"]` |
| `depends_on: db` without condition | Add `condition: service_healthy` |
| apt cache left in layer | `rm -rf /var/lib/apt/lists/*` in the same `RUN` |
| Dev dependencies in production image | Use multi-stage, `npm ci --omit=dev` in final stage |
| Secrets in `ENV` or `ARG` | Use runtime env vars or `--secret` mounts |

---

## Checklist before finishing

- [ ] Base image version is pinned, not `latest`
- [ ] Multi-stage build separates build tooling from the runtime image
- [ ] `COPY` of manifests comes before dependency install
- [ ] `.dockerignore` excludes `.env`, `node_modules`, `.git`, build output
- [ ] No secrets in `ENV`, `ARG`, or `COPY`
- [ ] Non-root user created and active before `CMD`
- [ ] `CMD` uses exec form, not shell form
- [ ] Healthcheck defined with a real probe (not just `CMD true`)
- [ ] `docker build` runs without error
- [ ] `docker run` starts the container and the app responds on the expected port
- [ ] For Compose: `depends_on` uses `condition: service_healthy` where needed
