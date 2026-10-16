---
name: graceful-shutdown
description: Implementing graceful shutdown so a service drains cleanly on SIGTERM: stops accepting new requests, waits for in-flight requests to complete, closes database and cache connections in the correct order, configures Kubernetes terminationGracePeriodSeconds correctly, and returns 503 from the health check immediately so the load balancer stops routing before the drain starts. Use when you want to add graceful shutdown, handle SIGTERM, stop dropping requests on deploy, drain in-flight requests, close database connections cleanly, handle Kubernetes pod termination, or implement a shutdown hook.
---

## graceful-shutdown

Wire shutdown correctly — stop taking work, finish what is in flight, then close resources
in reverse-dependency order.

### 1. The shutdown sequence — order matters

```
1. Receive SIGTERM
2. Stop accepting new requests (close the HTTP listener)
3. Wait for in-flight requests to finish (drain)
4. Stop background workers / job queue consumers
5. Flush telemetry (traces, metrics, logs)
6. Close database connection pools
7. Close cache / message broker connections
8. Exit 0
```

**Closing in the wrong order is the most common mistake.** If you close the database pool
before in-flight requests finish, those requests will throw connection errors in their final
milliseconds. Always close dependencies after the work that uses them is done.

---

### 2. Node.js — HTTP server + database

```ts
// lib/shutdown.ts
/**
 * lib/shutdown.ts
 * ---------------
 * Registers SIGTERM / SIGINT handlers and orchestrates graceful shutdown.
 * Call registerShutdownHandlers() once at startup, after all resources are initialised.
 *
 * Depends on: lib/logger.ts, lib/db.ts
 * Used by:    main.ts
 */

import { Server } from 'http';
import { logger } from './logger';

type Closer = () => Promise<void>;

const closers: Closer[] = [];

/** Register a resource to be closed during shutdown (in LIFO order). */
export function onShutdown(fn: Closer): void {
  closers.unshift(fn);   // unshift = LIFO — last registered, first closed
}

async function shutdown(signal: string): Promise<void> {
  logger.info('Shutdown signal received. signal=%s', signal);

  for (const close of closers) {
    try {
      await close();
    } catch (err) {
      logger.error('Error during shutdown closer. error=%s', err);
      // Continue — attempt every closer even if one fails
    }
  }

  logger.info('Shutdown complete. exiting.');
  process.exit(0);
}

export function registerShutdownHandlers(): void {
  process.once('SIGTERM', () => shutdown('SIGTERM'));
  process.once('SIGINT',  () => shutdown('SIGINT'));
}
```

```ts
// main.ts
import { createServer } from 'http';
import { app } from './app';
import { pool } from './lib/db';
import { redisClient } from './lib/redis';
import { sdk as otelSdk } from './tracing';
import { onShutdown, registerShutdownHandlers } from './lib/shutdown';
import { logger } from './lib/logger';

const server = createServer(app);
const DRAIN_TIMEOUT_MS = 30_000;   // must be < Kubernetes terminationGracePeriodSeconds

// Register closers in dependency order (LIFO unshift means first registered = last closed)
// Close order: HTTP → workers → telemetry → DB → cache

onShutdown(async () => {
  logger.info('Closing HTTP server — stopping new connections.');
  await new Promise<void>((resolve, reject) => {
    server.close((err) => (err ? reject(err) : resolve()));

    // Force-close after drain timeout so shutdown never hangs indefinitely
    setTimeout(() => {
      logger.warning('HTTP drain timeout reached. forcing close. timeout_ms=%d', DRAIN_TIMEOUT_MS);
      resolve();
    }, DRAIN_TIMEOUT_MS);
  });
});

onShutdown(async () => {
  logger.info('Flushing OpenTelemetry SDK.');
  await otelSdk.shutdown();
});

onShutdown(async () => {
  logger.info('Closing database pool.');
  await pool.end();
});

onShutdown(async () => {
  logger.info('Closing Redis client.');
  await redisClient.quit();
});

registerShutdownHandlers();
server.listen(3000, () => logger.info('Server listening. port=3000'));
```

---

### 3. Python — FastAPI / uvicorn

```python
# lib/shutdown.py
"""
lib/shutdown.py
---------------
Lifespan context manager for FastAPI — handles startup and graceful shutdown.
Resources opened in startup are closed in reverse order in shutdown.

Depends on: lib/logger.py, lib/db.py, lib/cache.py
Used by:    main.py
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from lib.logger import get_logger
from lib.db import database
from lib.cache import redis_client

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ───────────────────────────────────────────────────────────
    logger.info("Starting up — connecting to database and cache.")
    await database.connect()
    await redis_client.initialize()
    logger.info("Startup complete.")

    yield   # application runs here

    # ── Shutdown (runs after SIGTERM, after in-flight requests drain) ─────
    logger.info("Shutdown signal received — beginning teardown.")

    logger.info("Closing Redis client.")
    await redis_client.close()

    logger.info("Closing database pool.")
    await database.disconnect()

    logger.info("Shutdown complete.")


def create_app() -> FastAPI:
    return FastAPI(lifespan=lifespan)
```

```python
# main.py
"""
main.py
-------
Entrypoint — creates the app and starts uvicorn.
No business logic here.

Depends on: lib/shutdown.py, routes/
Used by:    deployment / uvicorn
"""

import uvicorn
from lib.shutdown import create_app
from routes.user_routes import router as user_router
from routes.order_routes import router as order_router

app = create_app()
app.include_router(user_router, prefix="/users")
app.include_router(order_router, prefix="/orders")

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        timeout_graceful_shutdown=30,   # uvicorn drains requests for up to 30 s
    )
```

---

### 4. Go — net/http server

```go
// internal/server/shutdown.go
package server

import (
    "context"
    "net/http"
    "os"
    "os/signal"
    "syscall"
    "time"

    "go.uber.org/zap"
)

const drainTimeout = 30 * time.Second

// Run starts the HTTP server and blocks until SIGTERM or SIGINT,
// then shuts down gracefully.
func Run(srv *http.Server, log *zap.Logger, closers ...func(ctx context.Context) error) error {
    // Start server in background
    errCh := make(chan error, 1)
    go func() {
        log.Info("Server listening", zap.String("addr", srv.Addr))
        if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
            errCh <- err
        }
    }()

    // Wait for signal
    quit := make(chan os.Signal, 1)
    signal.Notify(quit, syscall.SIGTERM, syscall.SIGINT)

    select {
    case sig := <-quit:
        log.Info("Shutdown signal received", zap.String("signal", sig.String()))
    case err := <-errCh:
        return err
    }

    ctx, cancel := context.WithTimeout(context.Background(), drainTimeout)
    defer cancel()

    // 1. Stop accepting new requests, drain in-flight
    log.Info("Draining HTTP server")
    if err := srv.Shutdown(ctx); err != nil {
        log.Error("HTTP shutdown error", zap.Error(err))
    }

    // 2. Close additional resources in order provided (DB, cache, etc.)
    for _, close := range closers {
        if err := close(ctx); err != nil {
            log.Error("Closer error during shutdown", zap.Error(err))
        }
    }

    log.Info("Shutdown complete")
    return nil
}
```

```go
// main.go
func main() {
    log, _ := zap.NewProduction()
    defer log.Sync()

    db  := mustConnectDB()
    rdb := mustConnectRedis()

    srv := &http.Server{Addr: ":8080", Handler: buildRouter(db, rdb)}

    if err := server.Run(srv, log,
        func(ctx context.Context) error {
            log.Info("Closing database pool")
            return db.Close()
        },
        func(ctx context.Context) error {
            log.Info("Closing Redis client")
            return rdb.Close()
        },
    ); err != nil {
        log.Fatal("Server error", zap.Error(err))
    }
}
```

---

### 5. Kubernetes — configure terminationGracePeriodSeconds

Kubernetes sends SIGTERM then waits `terminationGracePeriodSeconds` before SIGKILL.
Your drain timeout must be less than this value — otherwise the pod is killed mid-drain.

```yaml
# deployment.yaml
spec:
  terminationGracePeriodSeconds: 60   # K8s waits this long before SIGKILL

  containers:
    - name: api
      lifecycle:
        preStop:
          exec:
            # Give the load balancer time to stop routing traffic to this pod
            # before the app starts draining. Without this, new requests
            # arrive during the ~2 s it takes kube-proxy to update endpoints.
            command: ["/bin/sleep", "5"]
```

**The timing relationship:**
```
SIGTERM received
  ├── preStop hook runs (sleep 5 s — load balancer catches up)
  ├── App stops accepting new connections
  ├── App drains in-flight requests (max 30 s)
  └── App exits 0
                          ← terminationGracePeriodSeconds = 60 s
                             SIGKILL fires here if still running
```

Set `drainTimeout` in your app to `terminationGracePeriodSeconds − preStop − 5s buffer`.

---

### 6. Health check — report not-ready immediately on shutdown

Tell the load balancer to stop sending traffic as soon as shutdown starts.

```ts
// Node.js — flip a flag the health check reads
let isShuttingDown = false;

onShutdown(async () => { isShuttingDown = true; });

app.get('/health', (req, res) => {
  if (isShuttingDown) {
    return res.status(503).json({ status: 'shutting_down' });
  }
  res.json({ status: 'ok' });
});
```

```python
# FastAPI — same pattern
_shutting_down = False

@app.get("/health")
async def health():
    if _shutting_down:
        return JSONResponse({"status": "shutting_down"}, status_code=503)
    return {"status": "ok"}
```

### Rules

- Always set a drain timeout. Shutdown must never hang indefinitely — a stuck request
  should not block the entire deploy pipeline.
- Close resources in reverse-dependency order: HTTP first, then workers, then telemetry,
  then database, then cache. Never the other way.
- Log every step of shutdown with the logger — not print. Shutdown logs are often the only
  evidence of what happened during a bad deploy.
- The drain timeout in the app must be shorter than `terminationGracePeriodSeconds` in
  Kubernetes. If they are equal or reversed, pods get SIGKILLed mid-drain.
- Return `503` from `/health` the moment shutdown begins. The load balancer needs this
  signal to stop routing new traffic before the drain starts.
- Never call `process.exit()` inside a request handler. Only the shutdown sequence exits.
