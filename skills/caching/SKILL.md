---
name: caching
description: Add caching to reduce latency and database load. Use when the user asks to add a cache, speed up repeated queries, set up Redis, implement cache invalidation, add HTTP caching headers, use a CDN, fix stale cache bugs, or decide what to cache. Never caches blindly — measures first and picks the right strategy for the data.
---

# Caching

Cache the right things, invalidate correctly, and avoid serving stale data. A wrong cache
is worse than no cache — it serves incorrect results silently.

## Ground rules

- **Measure before caching.** Confirm the operation is actually slow or expensive. Don't
  cache speculatively.
- **Understand the data before choosing a TTL.** How often does it change? How bad is it
  if a user sees stale data for 30 seconds? 5 minutes? 1 hour?
- **Cache at the highest safe layer.** HTTP caching > CDN > application cache > database
  query cache. Higher layers serve more requests for less cost.
- **Every cache needs an invalidation plan.** A TTL is a fallback, not a strategy. Know
  exactly when the cached value is wrong and evict it then.
- **Never cache secrets, tokens, or per-user sensitive data in a shared cache** without
  scoping the key to the user.

---

## Step 0: Check what's already there

```bash
# Existing cache clients
grep -r "redis\|ioredis\|memcached\|lru-cache\|node-cache\|cachetools\|go-redis" \
  --include="*.ts" --include="*.js" --include="*.py" --include="*.go" -l | head -10

# Existing cache usage patterns
grep -rn "\.get\|\.set\|\.del\|cache\." --include="*.ts" --include="*.py" | head -20

# Docker / infra: is Redis already running?
cat docker-compose.yml | grep -A5 redis
cat .env | grep REDIS
```

---

## Choosing a caching strategy

| Strategy | How it works | Use when |
| --- | --- | --- |
| **Cache-aside** | App checks cache first; on miss, loads from DB and writes to cache | Most common. Read-heavy data that changes occasionally. |
| **Write-through** | App writes to cache and DB together on every write | Data that must be in cache immediately after write. |
| **Write-behind** | App writes to cache; cache asynchronously persists to DB | High write throughput where slight data loss on crash is acceptable. Rare. |
| **Read-through** | Cache fetches from DB on miss automatically | ORM-level caches; less common in application code. |
| **Refresh-ahead** | Cache proactively refreshes before TTL expires | Predictable access patterns; avoids latency spikes on expiry. |

For most web apps: **cache-aside** with explicit invalidation on mutation.

---

## Cache-aside pattern

```ts
// TypeScript — Redis with ioredis
import Redis from "ioredis";
const redis = new Redis(process.env.REDIS_URL!);

async function getProduct(id: string) {
  const key = `product:${id}`;

  // 1. Check cache
  const cached = await redis.get(key);
  if (cached) return JSON.parse(cached);

  // 2. Miss — load from DB
  const product = await db.product.findUnique({ where: { id } });
  if (!product) return null;

  // 3. Populate cache with TTL
  await redis.set(key, JSON.stringify(product), "EX", 300);  // 5 minutes

  return product;
}

// Invalidate on mutation
async function updateProduct(id: string, data: Partial<Product>) {
  const updated = await db.product.update({ where: { id }, data });
  await redis.del(`product:${id}`);  // evict immediately
  return updated;
}
```

```python
# Python — Redis with redis-py
import redis, json
from functools import wraps

r = redis.from_url(os.environ["REDIS_URL"], decode_responses=True)

def get_product(product_id: str):
    key = f"product:{product_id}"

    cached = r.get(key)
    if cached:
        return json.loads(cached)

    product = db.query(Product).filter_by(id=product_id).first()
    if not product:
        return None

    r.setex(key, 300, json.dumps(product.to_dict()))
    return product

def update_product(product_id: str, data: dict):
    product = db.query(Product).filter_by(id=product_id).first()
    for k, v in data.items():
        setattr(product, k, v)
    db.commit()
    r.delete(f"product:{product_id}")
    return product
```

---

## Cache key design

Keys must be deterministic, unique, and scoped correctly.

```
# Pattern: <namespace>:<identifier>[:<variant>]
product:abc123
user:42:profile
search:q=shoes&page=2&sort=price
rate_limit:user:42:/api/checkout
```

Rules:
- Include all inputs that affect the output in the key. If the result differs by locale,
  include locale: `product:abc123:en`.
- Never share a key between different data shapes. Changing the serialization format will
  serve corrupt data to cache hits until TTL expires.
- For per-user data in a shared Redis instance, always scope to user ID:
  `dashboard:user:42` not `dashboard`.

---

## TTL selection

| Data type | Suggested TTL |
| --- | --- |
| Static content (images, fonts) | 1 year (versioned URL) |
| Product catalogue, blog posts | 5–15 minutes |
| User profile, settings | 1–5 minutes |
| Session data | Duration of session |
| Rate limit counters | Window size (e.g. 60 seconds) |
| Realtime data (stock price, inventory) | 5–30 seconds, or event-driven invalidation |
| Auth tokens | Token expiry minus a small buffer |

When in doubt, start with a shorter TTL. A cache miss costs a DB query; stale data costs
user trust.

---

## Cache invalidation patterns

### Key-based eviction (simplest)

Delete the exact key when the data changes. Works when the cached item maps 1:1 to a DB row.

```ts
await redis.del(`product:${id}`);
```

### Tag-based invalidation

Group related keys under a tag so you can evict them all at once. Useful when one DB
record affects many cached views.

```ts
// On write: store which keys belong to a tag
await redis.sadd(`tag:product:${id}`, `product:${id}`, `homepage:featured`);

// On mutation: evict all tagged keys
async function invalidateByTag(tag: string) {
  const keys = await redis.smembers(`tag:${tag}`);
  if (keys.length) await redis.del(...keys, `tag:${tag}`);
}
await invalidateByTag(`product:${id}`);
```

### Versioned keys (cache-busting)

Increment a version counter instead of deleting keys. Old keys expire naturally via TTL.

```ts
// Bump version on mutation
await redis.incr(`product:${id}:version`);

// Read: include version in the key
const version = await redis.get(`product:${id}:version`) ?? "1";
const key = `product:${id}:v${version}`;
```

---

## HTTP caching headers

Set headers so browsers and CDNs cache responses — free performance with no Redis needed.

```ts
// Express — static public content (versioned assets)
res.set("Cache-Control", "public, max-age=31536000, immutable");

// Frequently changing public content
res.set("Cache-Control", "public, max-age=300, stale-while-revalidate=60");

// Authenticated or user-specific — never cache in shared cache
res.set("Cache-Control", "private, no-store");

// ETag-based conditional caching
import crypto from "crypto";
const etag = crypto.createHash("md5").update(JSON.stringify(data)).digest("hex");
res.set("ETag", `"${etag}"`);
if (req.headers["if-none-match"] === `"${etag}"`) {
  return res.status(304).send();
}
res.json(data);
```

```
Cache-Control directive cheat sheet:
  public              — CDNs and browsers may cache
  private             — browser only, no CDN
  no-store            — never cache (sensitive data)
  max-age=N           — cache for N seconds
  s-maxage=N          — CDN TTL (overrides max-age for CDNs)
  stale-while-revalidate=N  — serve stale while fetching fresh in background
  immutable           — content will never change (use with versioned URLs only)
```

---

## Memoization (in-process cache)

For expensive pure computations within a single request or process lifetime:

```ts
// Simple LRU cache (no Redis needed)
import { LRUCache } from "lru-cache";

const cache = new LRUCache<string, unknown>({ max: 500, ttl: 1000 * 60 * 5 });

function memoize<T>(key: string, fn: () => Promise<T>, ttlMs?: number): Promise<T> {
  if (cache.has(key)) return Promise.resolve(cache.get(key) as T);
  return fn().then((result) => {
    cache.set(key, result);
    return result;
  });
}
```

```python
# Python — functools.lru_cache for sync functions
from functools import lru_cache

@lru_cache(maxsize=256)
def get_exchange_rate(currency: str) -> float:
    return fetch_from_api(currency)

# For async functions — cachetools
from cachetools import TTLCache
_cache: TTLCache = TTLCache(maxsize=256, ttl=300)

async def get_exchange_rate(currency: str) -> float:
    if currency in _cache:
        return _cache[currency]
    rate = await fetch_from_api(currency)
    _cache[currency] = rate
    return rate
```

In-process caches don't survive restarts and aren't shared across instances. Use Redis
for anything that must be consistent across multiple app servers.

---

## Avoiding common cache bugs

| Bug | Cause | Fix |
| --- | --- | --- |
| **Cache stampede** | Many requests miss at the same time and hammer the DB | Use a lock or probabilistic early expiry |
| **Stale data after write** | Write path doesn't invalidate the cache key | Evict or update the key on every mutation |
| **Caching null results** | A missing record is fetched from DB on every request | Cache a sentinel value (`"__NULL__"`) with a short TTL |
| **Key collision** | Two features share a key prefix accidentally | Use namespaced keys (`<service>:<type>:<id>`) |
| **PII in shared cache** | User A sees User B's data | Include user ID in every user-scoped key |
| **Unbounded in-process cache** | Memory grows indefinitely | Always set `maxSize` on LRU caches |
| **Serialization mismatch** | Cached JSON doesn't deserialize to the expected type | Validate or version the cached shape |

### Cache stampede prevention

```ts
// Use a short-lived lock so only one request fetches from DB on a cold miss
async function getWithLock<T>(key: string, fetch: () => Promise<T>, ttl: number): Promise<T> {
  const cached = await redis.get(key);
  if (cached) return JSON.parse(cached);

  const lockKey = `lock:${key}`;
  const locked = await redis.set(lockKey, "1", "NX", "EX", 5);  // 5s lock

  if (!locked) {
    // Another request is fetching — wait briefly and retry
    await new Promise((r) => setTimeout(r, 50));
    return getWithLock(key, fetch, ttl);
  }

  try {
    const result = await fetch();
    await redis.set(key, JSON.stringify(result), "EX", ttl);
    return result;
  } finally {
    await redis.del(lockKey);
  }
}
```

---

## Checklist

- [ ] Confirmed the target operation is actually slow before adding cache
- [ ] Cache key includes all inputs that affect the output
- [ ] Per-user data keys are scoped with the user ID
- [ ] TTL chosen based on how stale the data can safely be
- [ ] Every write path that mutates cached data also invalidates the key
- [ ] Null/missing results are handled (cached sentinel or not cached)
- [ ] In-process caches have a bounded `maxSize`
- [ ] Shared Redis instance is not storing plaintext secrets or tokens
- [ ] HTTP responses that vary by user have `Cache-Control: private` or `no-store`
- [ ] Static assets with versioned URLs have `Cache-Control: immutable`
