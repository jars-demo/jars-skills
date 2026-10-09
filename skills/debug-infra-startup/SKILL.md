---
name: debug-infra-startup
description: Diagnose and fix service startup race conditions in containerized environments. Use when a CI job fails with a service that reports healthy but behaves broken, a container passes its healthcheck but rejects writes or connections, a dependent service says "ready" but the dependent component crashes, or a distroless image silently breaks a healthcheck command.
---

# Debug infra startup

A service can be in three different states that are easy to confuse:

1. **Process started** — the container is running, the PID exists
2. **HTTP server up** — the health or ready endpoint returns 200
3. **Actually accepting traffic** — the write path, the ring, the index, the queue is open

Most startup bugs live in the gap between 2 and 3. The readiness signal lies, or the probe checks the wrong thing, and the dependent service crashes into what looks like a mystery.

## Ground rules

- **Never trust a readiness signal until you have probed the actual work path.** A `/ready` 200 proves the HTTP server is up. It does not prove the service can handle your request.
- **Reproduce the probe the way the failing component uses the service.** If the failing component writes, your probe must write. If it queries, your probe must query.
- **Check the image before writing a healthcheck.** Distroless and minimal images have no shell, no `wget`, no `curl`. A `CMD-SHELL` healthcheck silently fails or is never executed.
- **Fix the probe before fixing the timeout.** Increasing `--interval` or `--retries` on a broken probe only delays the same failure.
- **One race, one fix.** Do not add sleeps everywhere. Find the specific gap and close it with a real probe.

## The three readiness levels

| Level | What it means | How to check |
| --- | --- | --- |
| Process started | Container is running | `docker ps`, `docker inspect --format '{{.State.Status}}'` |
| HTTP server up | Health endpoint responds | `curl -sf http://host:port/-/ready` |
| Work path open | Service can do its actual job | Write a test record, run a query, check internal state endpoint |

Always establish which level you are actually at before debugging further.

## Workflow

### 1. Establish what the readiness signal actually checks

Read the service documentation or source for what the health and ready endpoints verify:

```bash
# What does the ready endpoint actually gate on?
curl -sf http://localhost:3100/-/ready
# "ready" != "ring joined" != "ingester accepting writes"

# For services that expose internal state, check it directly
curl -s http://localhost:3100/ring | jq '.ingesters[] | {addr, state}'
curl -s http://localhost:9090/-/status
```

If the ready endpoint only checks that the HTTP server started, it is not a readiness signal for the work path. Treat it as a liveness signal only.

### 2. Probe the actual work path

Construct the simplest possible request that exercises the real path:

```bash
# Loki: probe the push path, not just /ready
curl -sf -X POST http://localhost:3100/loki/api/v1/push \
  -H 'Content-Type: application/json' \
  -d '{"streams":[{"stream":{"probe":"1"},"values":[["'"$(date +%s%N)"'","probe"]]}]}'

# Postgres: probe a write, not just a connection
psql "$DATABASE_URL" -c "INSERT INTO _healthcheck (ts) VALUES (now()) ON CONFLICT DO NOTHING"

# Redis: probe a write
redis-cli SET _healthcheck 1 EX 5

# Elasticsearch: probe index availability
curl -sf "http://localhost:9200/_cluster/health?wait_for_status=yellow&timeout=10s"
```

If the work-path probe fails while `/ready` returns 200, the readiness signal is insufficient. You have found your bug.

### 3. Check the image for shell availability

Before writing any healthcheck, confirm what the image actually contains:

```bash
# Does it have a shell?
docker run --rm --entrypoint sh <image> -c "echo ok" 2>&1

# Does it have wget?
docker run --rm --entrypoint wget <image> --version 2>&1

# Does it have curl?
docker run --rm --entrypoint curl <image> --version 2>&1
```

**If the image is distroless or scratch-based, none of these work.** Use the exec form instead:

```yaml
# WRONG on distroless: CMD-SHELL is never available
healthcheck:
  test: ["CMD-SHELL", "wget -qO- http://localhost:3100/-/ready || exit 1"]

# Correct: exec form, binary must exist in the image
healthcheck:
  test: ["CMD", "/usr/bin/wget", "-qO-", "http://localhost:3100/-/ready"]

# If no HTTP client exists, use a native TCP check via Docker's built-in
healthcheck:
  test: ["CMD", "/bin/grpc_health_probe", "-addr=:50051"]
```

For images with no probe binary at all, add a sidecar or use a purpose-built probe image:

```yaml
# docker-compose: separate probe container that waits before declaring healthy
depends_on:
  loki:
    condition: service_healthy
```

### 4. Find where the wait logic belongs

Pick the right place based on what tools are available:

| Context | Correct approach |
| --- | --- |
| Docker Compose | `healthcheck` on the service + `depends_on: condition: service_healthy` on the dependent |
| CI pipeline (GitHub Actions) | A `wait-for` step before the step that needs the service |
| Kubernetes | `readinessProbe` on the pod, `initContainers` for dependency ordering |
| Shell script | A retry loop with a real work-path probe |

Do not add `sleep N` as the wait mechanism. A sleep either waits too long on a fast machine or not long enough under load. Use a probe loop:

```bash
# Portable retry loop: probe the real work path
wait_for_loki() {
  local retries=30
  until curl -sf -X POST http://localhost:3100/loki/api/v1/push \
    -H 'Content-Type: application/json' \
    -d '{"streams":[{"stream":{"probe":"1"},"values":[["'"$(date +%s%N)"'","probe"]]}]}' \
    > /dev/null 2>&1
  do
    retries=$((retries - 1))
    [ "$retries" -le 0 ] && echo "Loki never became ready" >&2 && return 1
    sleep 1
  done
}
```

### 5. Check config path assumptions

Startup failures that look like race conditions are sometimes config path mismatches — the process starts, but it is reading the wrong directory or file:

```bash
# Is the config being picked up from where the process expects it?
docker inspect <container> | jq '.[0].HostConfig.Binds'
docker exec <container> cat /etc/loki/config.yaml

# Is the working directory what the tool assumes?
# e.g. a build tool that expects to be run from the repo root
# but the CI job is already inside a subdirectory
pwd
ls -la
```

If a tool says a file or directory does not exist, confirm what the working directory actually is before assuming the config is wrong.

### 6. Read the startup logs in full

Do not skim. The real error is almost never on the last line:

```bash
docker logs <container> 2>&1 | head -80
docker logs <container> 2>&1 | grep -i "error\|warn\|fail\|ring\|leaving\|joining"

# For a service that crashed immediately
docker logs <container> --tail 50

# Follow until a pattern appears
docker logs -f <container> 2>&1 | grep -m 1 "started\|ready\|error"
```

Ring state messages, joining/leaving log lines, and "waiting for" messages appear early in the log. A service that looks ready from the outside may have logged its actual state several lines up.

### 7. Verify the fix end-to-end

After fixing the probe or the wait logic:

1. Tear down and restart from clean state: `docker compose down -v && docker compose up -d`
2. Wait for the probe to pass naturally — do not skip or bypass it
3. Confirm the work-path probe succeeds after the service is declared healthy
4. Run the dependent component and confirm it no longer fails at startup

## Common patterns and their fixes

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| `/ready` returns 200, writes return 503 | Ready probe only checks HTTP server, not write path | Replace probe with a write-path request |
| Healthcheck defined but never seems to run | Image has no shell, `CMD-SHELL` silently does nothing | Switch to exec form `["CMD", "/path/to/binary", ...]` |
| Service healthy, dependent crashes immediately | `depends_on` without `condition: service_healthy` | Add `condition: service_healthy` to `depends_on` |
| Ingester in "leaving" or "joining" state | Ring not yet stabilised after restart | Probe ring state endpoint, not just `/ready` |
| "directory does not exist" in CI | Tool assumes wrong working directory | Check `pwd`, confirm bind mounts and config paths |
| Works locally, fails in CI | Different startup timing under resource constraints | Replace `sleep` with a real probe retry loop |
| Probe works in shell, fails in healthcheck | Shell not available in image | Use exec form, verify binary path inside container |
