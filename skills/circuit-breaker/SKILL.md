---
name: circuit-breaker
description: Implementing the circuit breaker pattern to stop cascading failures: builds the three-state machine (closed, open, half-open), wires it around outbound HTTP calls and database queries, tunes failure thresholds and recovery timeouts, exposes state as a metric, and integrates with existing retry and timeout logic. Use when you want to add a circuit breaker, prevent cascading failures, fail fast when a dependency is down, implement the circuit breaker pattern, stop hammering a failing service, add resilience to outbound calls, or use a library like opossum or resilience4j.
---

## circuit-breaker

Wrap every outbound call that can fail. Fail fast when a dependency is struggling —
never let one slow dependency drain your entire thread pool.

### 1. The three-state machine

```
          failure threshold reached
CLOSED ──────────────────────────────► OPEN
  ▲                                      │
  │   success                            │ reset timeout expires
  │                                      ▼
  └──────────────────────────────── HALF-OPEN
         probe succeeds                  │
                                         │ probe fails
                                         ▼
                                        OPEN (reset timeout restarts)
```

- **CLOSED** — normal operation; requests pass through; failures counted
- **OPEN** — dependency is unhealthy; requests fail immediately without trying; no load on the dependency
- **HALF-OPEN** — recovery probe; one request allowed through; if it succeeds → CLOSED, if it fails → OPEN again

---

### 2. Node.js — opossum (battle-tested library)

```ts
// lib/circuitBreakers.ts
/**
 * lib/circuitBreakers.ts
 * ----------------------
 * Circuit breaker instances for each outbound dependency.
 * One breaker per logical dependency — not per endpoint.
 *
 * Depends on: opossum, lib/logger.ts, lib/metrics.ts
 * Used by:    services that make outbound calls
 */

import CircuitBreaker from 'opossum';
import { logger } from './logger';

export interface BreakerOptions {
  timeout?: number;          // ms before a single call is considered failed (default 3000)
  errorThresholdPct?: number; // % failures to trip open (default 50)
  resetTimeout?: number;      // ms to wait before probing in half-open (default 30000)
  volumeThreshold?: number;   // min calls before threshold applies (default 5)
}

export function createBreaker<T extends unknown[], R>(
  name: string,
  fn: (...args: T) => Promise<R>,
  opts: BreakerOptions = {},
): CircuitBreaker<T, R> {
  const breaker = new CircuitBreaker(fn, {
    name,
    timeout:            opts.timeout            ?? 3_000,
    errorThresholdPercentage: opts.errorThresholdPct ?? 50,
    resetTimeout:       opts.resetTimeout       ?? 30_000,
    volumeThreshold:    opts.volumeThreshold    ?? 5,
  });

  // Log every state transition — critical for incident debugging
  breaker.on('open',     () => logger.error(`Circuit breaker OPEN. name=${name} action=failing_fast`));
  breaker.on('halfOpen', () => logger.warning(`Circuit breaker HALF-OPEN. name=${name} action=probing`));
  breaker.on('close',    () => logger.info(`Circuit breaker CLOSED. name=${name} action=recovered`));
  breaker.on('fallback', (result) => logger.warning(`Circuit breaker fallback used. name=${name}`));
  breaker.on('timeout',  () => logger.warning(`Circuit breaker timeout. name=${name}`));

  return breaker;
}
```

```ts
// lib/stripeClient.ts
/**
 * lib/stripeClient.ts
 * -------------------
 * Stripe API calls wrapped in a circuit breaker.
 * Falls back to a queued-retry on open circuit.
 *
 * Depends on: lib/circuitBreakers.ts, lib/queue.ts
 * Used by:    services/paymentService.ts
 */

import Stripe from 'stripe';
import { createBreaker } from './circuitBreakers';
import { enqueueRetry } from './queue';

const stripe = new Stripe(process.env.STRIPE_SECRET_KEY!);

// Wrap the outbound call — not the service method
async function _chargeCard(amount: number, currency: string, paymentMethodId: string) {
  return stripe.paymentIntents.create({ amount, currency, payment_method: paymentMethodId });
}

export const stripeBreaker = createBreaker('stripe', _chargeCard, {
  timeout:           5_000,   // Stripe p99 is ~2 s — 5 s gives headroom
  errorThresholdPct: 30,      // trip after 30 % failures (payment is critical — trip early)
  resetTimeout:      60_000,  // wait 60 s before probing
  volumeThreshold:   3,       // trip after just 3 calls (low traffic service)
});

// Fallback — enqueue for retry rather than returning an error to the user
stripeBreaker.fallback(async (amount, currency, paymentMethodId) => {
  await enqueueRetry('stripe-charge', { amount, currency, paymentMethodId });
  throw new Error('Payment service temporarily unavailable — request queued for retry');
});

export async function chargeCard(
  amount: number,
  currency: string,
  paymentMethodId: string,
) {
  return stripeBreaker.fire(amount, currency, paymentMethodId);
}
```

---

### 3. Python — manual implementation (no heavyweight framework needed)

```python
# lib/circuit_breaker.py
"""
lib/circuit_breaker.py
----------------------
Minimal, production-ready circuit breaker implementation.
Thread-safe using asyncio.Lock for async code.

Depends on: lib/logger.py
Used by:    any service making outbound HTTP or DB calls
"""

import asyncio
import time
from enum import Enum
from lib.logger import get_logger

logger = get_logger(__name__)


class State(Enum):
    CLOSED    = "closed"
    OPEN      = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,      # failures before opening
        success_threshold: int = 2,       # successes in half-open before closing
        reset_timeout_s:   float = 30.0,  # seconds before probing
        call_timeout_s:    float = 3.0,   # per-call timeout
    ) -> None:
        self.name              = name
        self.failure_threshold = failure_threshold
        self.success_threshold = success_threshold
        self.reset_timeout_s   = reset_timeout_s
        self.call_timeout_s    = call_timeout_s

        self._state            = State.CLOSED
        self._failure_count    = 0
        self._success_count    = 0
        self._opened_at: float = 0.0
        self._lock             = asyncio.Lock()

    @property
    def state(self) -> State:
        return self._state

    async def call(self, fn, *args, **kwargs):
        """Execute fn through the circuit breaker."""
        async with self._lock:
            if self._state == State.OPEN:
                if time.monotonic() - self._opened_at >= self.reset_timeout_s:
                    self._transition(State.HALF_OPEN)
                else:
                    raise CircuitOpenError(f"Circuit breaker OPEN: {self.name}")

        try:
            result = await asyncio.wait_for(fn(*args, **kwargs), timeout=self.call_timeout_s)
            await self._on_success()
            return result

        except CircuitOpenError:
            raise

        except Exception as exc:
            await self._on_failure(exc)
            raise

    async def _on_success(self) -> None:
        async with self._lock:
            if self._state == State.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.success_threshold:
                    self._transition(State.CLOSED)
            elif self._state == State.CLOSED:
                self._failure_count = 0   # reset on success

    async def _on_failure(self, exc: Exception) -> None:
        async with self._lock:
            self._failure_count += 1
            logger.warning(
                "Circuit breaker recorded failure. name=%s failures=%d error=%s",
                self.name, self._failure_count, exc,
            )
            if self._state in (State.CLOSED, State.HALF_OPEN):
                if self._failure_count >= self.failure_threshold:
                    self._transition(State.OPEN)

    def _transition(self, new_state: State) -> None:
        old = self._state
        self._state = new_state

        if new_state == State.OPEN:
            self._opened_at     = time.monotonic()
            self._failure_count = 0
            self._success_count = 0
            logger.error("Circuit breaker OPEN. name=%s action=failing_fast", self.name)

        elif new_state == State.HALF_OPEN:
            self._failure_count = 0
            self._success_count = 0
            logger.warning("Circuit breaker HALF-OPEN. name=%s action=probing", self.name)

        elif new_state == State.CLOSED:
            self._failure_count = 0
            self._success_count = 0
            logger.info("Circuit breaker CLOSED. name=%s action=recovered", self.name)


class CircuitOpenError(Exception):
    """Raised when a call is rejected because the circuit is open."""
```

```python
# Usage in a service
from lib.circuit_breaker import CircuitBreaker, CircuitOpenError

_stripe_breaker = CircuitBreaker(
    name="stripe",
    failure_threshold=5,
    reset_timeout_s=60.0,
    call_timeout_s=5.0,
)

async def charge_card(amount: int, payment_method_id: str):
    try:
        return await _stripe_breaker.call(
            stripe_client.charge,
            amount=amount,
            payment_method_id=payment_method_id,
        )
    except CircuitOpenError:
        logger.warning(
            "Stripe circuit open — queuing charge for retry. "
            "amount=%d payment_method_id=%s",
            amount, payment_method_id,
        )
        await enqueue_retry("stripe-charge", {"amount": amount, "pmid": payment_method_id})
        raise PaymentUnavailableError("Payment temporarily unavailable")
```

---

### 4. Tune the thresholds — defaults are not production values

| Parameter | Too low | Too high | Starting point |
|-----------|---------|----------|---------------|
| `failure_threshold` | Trips on normal transient errors | Allows long degradation before tripping | 5 failures |
| `error_threshold_pct` | Trips during traffic spikes with 1–2 failures | Allows high failure rates | 50 % |
| `reset_timeout` | Re-opens immediately, thrashes | Long outage window for callers | 30–60 s |
| `call_timeout` | Times out healthy slow calls | Hangs thread pool | p99 latency × 2 |
| `volume_threshold` | Ignores initial failures | Takes too long to trip | 5–10 calls |

**Set `call_timeout` from real p99 latency data, not guesses.** Check your monitoring
dashboard for the dependency's p99 over the last 30 days. Multiply by 2. That is your
starting timeout.

---

### 5. Expose circuit state as a metric

The circuit breaker state must be observable. When it opens in production, the on-call
engineer needs to know immediately.

```ts
// Add to your Prometheus metrics
import { Gauge } from 'prom-client';

const breakerState = new Gauge({
  name: 'circuit_breaker_state',
  help: 'Circuit breaker state: 0=closed, 1=half_open, 2=open',
  labelNames: ['name'],
});

// opossum exposes stats — sync to gauge every 10 s
setInterval(() => {
  const state = stripeBreaker.opened ? 2 : stripeBreaker.halfOpen ? 1 : 0;
  breakerState.set({ name: 'stripe' }, state);
}, 10_000);
```

**Alert when `circuit_breaker_state{name="stripe"} == 2` for more than 60 s.**
A breaker that stays open for more than one reset cycle needs human attention.

---

### 6. What NOT to wrap in a circuit breaker

| Do wrap | Do not wrap |
|---------|------------|
| Outbound HTTP to third-party APIs | In-memory function calls |
| Database queries on a separate host | Redis reads on localhost |
| gRPC calls to other services | Idempotent cache reads |
| External email / SMS providers | Synchronous CPU-bound work |

Circuit breakers add latency overhead on every call. Use them at service boundaries
where failure is external and observable, not inside a single process.

### Rules

- One circuit breaker per logical dependency, not per endpoint. All Stripe calls share
  one breaker — if Stripe is down, all Stripe calls should fail fast together.
- Always log state transitions at the right level: OPEN = error, HALF-OPEN = warning,
  CLOSED = info.
- Set a fallback before the breaker opens in production. An open breaker with no
  fallback returns a raw error to the user — a fallback returns a graceful degradation.
- Never catch `CircuitOpenError` inside the same layer that makes the call. Let it
  propagate to the service boundary so the caller can decide the fallback.
- Test the open state explicitly — most teams only test the happy path.
