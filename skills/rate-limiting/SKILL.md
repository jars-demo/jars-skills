---
name: rate-limiting
description: Add rate limiting to protect APIs and services from abuse, brute-force attacks, and traffic spikes. Use when the user asks to add rate limiting, prevent brute-force login attempts, throttle an API endpoint, implement a token bucket or sliding window, add per-user or per-IP limits, or fix a service that is getting hammered by excessive requests.
---

# Rate limiting

Protect endpoints from abuse and overload by enforcing request limits. Rate limiting is
both a security control (brute-force, credential stuffing) and a reliability control
(runaway clients, traffic spikes). Pick the right algorithm and scope for the threat.

## Ground rules

- **Read the existing setup first.** Check for an existing middleware, reverse proxy config
  (nginx, Caddy), or API gateway rule before adding application-level limiting.
- **Scope limits to the right key.** IP-based limits are easy to bypass with proxies.
  Prefer user ID for authenticated endpoints and IP + endpoint for unauthenticated ones.
- **Return `429 Too Many Requests` with a `Retry-After` header.** Never return `200` or
  `403` for rate limit violations — `429` is the standard and clients know how to handle it.
- **Store counters outside the app process.** In-memory counters reset on restart and don't
  work across multiple instances. Use Redis.
- **Never rate-limit health check or readiness endpoints.** Load balancers depend on them.

---

## Algorithms

| Algorithm | How it works | Best for |
| --- | --- | --- |
| **Fixed window** | Count requests in a fixed time bucket (e.g. 100 req/min). Resets at the boundary. | Simple cases; beware burst at window edge. |
| **Sliding window** | Count requests in a rolling window ending now. Smoother than fixed. | General API limiting. |
| **Token bucket** | Tokens refill at a steady rate; each request consumes one. Allows short bursts up to bucket size. | APIs that should allow occasional bursts. |
| **Leaky bucket** | Requests queue and are processed at a fixed rate. Excess are dropped. | Smoothing output rate; less common in web APIs. |

Sliding window or token bucket covers most use cases. Use fixed window only when simplicity
matters more than edge-case burst behaviour.

---

## Node.js / Express

### Using `express-rate-limit` + `rate-limit-redis`

```ts
import rateLimit from "express-rate-limit";
import RedisStore from "rate-limit-redis";
import { createClient } from "redis";

const redis = createClient({ url: process.env.REDIS_URL });
await redis.connect();

// General API limit — applied globally
export const apiLimiter = rateLimit({
  windowMs: 60 * 1000,       // 1 minute
  max: 100,                  // 100 requests per window per key
  standardHeaders: "draft-7", // sends RateLimit-* headers (RFC 6585 draft)
  legacyHeaders: false,
  store: new RedisStore({
    sendCommand: (...args: string[]) => redis.sendCommand(args),
  }),
  keyGenerator: (req) => {
    // Authenticated: scope to user; unauthenticated: fall back to IP
    return (req.user?.id ?? req.ip) as string;
  },
  handler: (req, res) => {
    res.status(429).json({
      error: { code: "RATE_LIMITED", message: "Too many requests. Please try again later." },
    });
  },
});

// Strict limit for auth endpoints — brute-force protection
export const authLimiter = rateLimit({
  windowMs: 15 * 60 * 1000,  // 15 minutes
  max: 10,                   // 10 attempts per 15 min per IP
  standardHeaders: "draft-7",
  legacyHeaders: false,
  store: new RedisStore({
    sendCommand: (...args: string[]) => redis.sendCommand(args),
  }),
  keyGenerator: (req) => req.ip as string,
  skipSuccessfulRequests: true,  // only count failures toward the limit
  handler: (req, res) => {
    res.status(429)
      .set("Retry-After", "900")
      .json({
        error: { code: "TOO_MANY_ATTEMPTS", message: "Too many attempts. Try again in 15 minutes." },
      });
  },
});

// Apply
app.use("/api/", apiLimiter);
app.post("/auth/login", authLimiter, loginHandler);
app.post("/auth/forgot-password", authLimiter, forgotPasswordHandler);
```

---

## Python / FastAPI

### Using `slowapi` (wraps `limits` library)

```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request
from fastapi.responses import JSONResponse

# Key function: use user ID for authenticated routes, IP for public ones
def get_limit_key(request: Request) -> str:
    user = getattr(request.state, "user", None)
    return str(user.id) if user else request.client.host

limiter = Limiter(
    key_func=get_limit_key,
    storage_uri=os.environ["REDIS_URL"],  # Redis backend
)
app.state.limiter = limiter

# Custom 429 handler — consistent error shape
@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        headers={"Retry-After": "60"},
        content={"error": {"code": "RATE_LIMITED", "message": "Too many requests. Please try again later."}},
    )

# Per-route limits
@app.get("/api/search")
@limiter.limit("30/minute")
async def search(request: Request, q: str): ...

@app.post("/auth/login")
@limiter.limit("10/15minutes")
async def login(request: Request, body: LoginRequest): ...
```

### Manual sliding window with Redis (no library)

```python
import time, redis

r = redis.from_url(os.environ["REDIS_URL"])

def check_rate_limit(key: str, limit: int, window_seconds: int) -> bool:
    """Returns True if the request is allowed, False if rate limited."""
    now = time.time()
    window_start = now - window_seconds

    pipe = r.pipeline()
    pipe.zremrangebyscore(key, 0, window_start)       # remove old entries
    pipe.zadd(key, {str(now): now})                   # add current request
    pipe.zcard(key)                                   # count in window
    pipe.expire(key, window_seconds)
    results = pipe.execute()

    count = results[2]
    return count <= limit
```

---

## Response headers

Always send rate limit headers so clients can back off gracefully:

```
RateLimit-Limit: 100          # max requests allowed in the window
RateLimit-Remaining: 43       # requests left in the current window
RateLimit-Reset: 1705329660   # unix timestamp when the window resets
Retry-After: 47               # seconds until the client may retry (on 429 only)
```

`express-rate-limit` with `standardHeaders: "draft-7"` sends these automatically.
For manual implementations, add them yourself before every response on limited routes.

---

## Nginx / reverse proxy (before the app)

If you control the reverse proxy, rate limiting there is cheaper — requests are dropped
before hitting application code:

```nginx
# nginx.conf
http {
  # Define a shared memory zone keyed on client IP
  limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
  limit_req_zone $binary_remote_addr zone=auth:10m rate=1r/s;

  server {
    location /api/ {
      limit_req zone=api burst=20 nodelay;
      limit_req_status 429;
      proxy_pass http://app;
    }

    location /auth/login {
      limit_req zone=auth burst=5;
      limit_req_status 429;
      proxy_pass http://app;
    }
  }
}
```

`burst` allows a short queue beyond the rate before returning 429. `nodelay` serves the
burst immediately rather than spacing it out.

---

## What to rate-limit and at what level

| Endpoint type | Recommended limit | Key |
| --- | --- | --- |
| Public read API | 100–300 req/min | IP |
| Authenticated API | 300–600 req/min | User ID |
| Login / token endpoint | 5–10 attempts / 15 min | IP |
| Password reset / OTP | 3–5 attempts / 15 min | IP + email |
| File upload | 10–20 req/min | User ID |
| Webhook receiver | 100–500 req/min | Sending IP |
| Health check | No limit | — |

Start conservative and loosen based on real traffic data. It's easier to raise a limit
than to explain why a brute-force attack succeeded.

---

## Checklist

- [ ] Redis (or equivalent) used as the counter store — not in-process memory
- [ ] Auth endpoints (login, password reset, OTP) have strict limits keyed on IP
- [ ] Authenticated routes use user ID as the limit key, not IP
- [ ] `429 Too Many Requests` returned on violation — not `200`, `403`, or `503`
- [ ] `Retry-After` header included in every `429` response
- [ ] `RateLimit-*` headers sent on all rate-limited routes so clients can self-throttle
- [ ] Health check and readiness endpoints are excluded from rate limiting
- [ ] Limits tested: confirm a `429` is actually returned after the threshold is hit
- [ ] Multi-instance safe: counters shared via Redis, not per-process
