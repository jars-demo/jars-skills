---
name: feature-flags
description: >
  Implementing, gating, and cleaning up feature flags: picks the right flag type (boolean,
  percentage rollout, user-targeted), wires up a flag client (LaunchDarkly, Unleash, Flagsmith,
  or a homegrown config), wraps new code in flag checks without coupling business logic to the
  flag system, tracks flag age, and removes stale flags safely. Use when you want to "add a
  feature flag", "do a gradual rollout", "gate a feature for specific users", "implement a kill
  switch", "set up LaunchDarkly or Unleash", "clean up an old flag", or "roll back without
  deploying".
---

## feature-flags

Add, use, and eventually remove feature flags cleanly.

### 1. Decide the flag type before writing any code

| Type | When to use | Example |
|------|-------------|---------|
| **Boolean (on/off)** | Kill switch, staff-only preview | `new-checkout-flow` |
| **Percentage rollout** | Gradual exposure to reduce blast radius | Roll out to 5% → 25% → 100% |
| **User / segment targeting** | Beta testers, paying customers, internal team | `user.plan === 'pro'` |
| **Multivariate** | A/B testing or configuration values | `button_color = blue\|green\|red` |

Start with the simplest type that satisfies the requirement. Over-engineering flags is a common
source of long-lived flag debt.

### 2. Pick a flag backend

**Managed service (recommended for teams):**

- [LaunchDarkly](https://launchdarkly.com) — SDKs for every language, percentage rollouts,
  targeting rules, real-time streaming.
- [Unleash](https://www.getunleash.io) — open-source, self-hostable, strong gradual rollout
  support.
- [Flagsmith](https://flagsmith.com) — open-source, supports remote config values alongside
  booleans.

**Homegrown (fine for simple cases):**

Keep flags in a config file or environment variable and parse them at startup. This works for
kill switches and staff-only flags but does not support percentage rollouts or targeting without
extra code.

```json
// flags.json — simplest possible homegrown approach
{
  "new-checkout-flow": false,
  "enable-new-search":  true
}
```

### 3. Wrap the SDK in a thin abstraction

Never call the flag SDK directly in business logic. One wrapper keeps the system swappable and
makes testing trivial.

```ts
// lib/flags.ts
export interface FlagClient {
  isEnabled(flagKey: string, context?: FlagContext): boolean;
  getVariant<T>(flagKey: string, defaultValue: T, context?: FlagContext): T;
}

export interface FlagContext {
  userId?: string;
  email?: string;
  plan?: string;
  [key: string]: string | undefined;
}

// LaunchDarkly implementation
import LaunchDarkly from '@launchdarkly/node-server-sdk';

const ldClient = LaunchDarkly.init(process.env.LD_SDK_KEY!);
await ldClient.waitForInitialization();

export const flags: FlagClient = {
  isEnabled(key, ctx = {}) {
    return ldClient.variation(key, { key: ctx.userId ?? 'anonymous', ...ctx }, false);
  },
  getVariant(key, defaultValue, ctx = {}) {
    return ldClient.variation(key, { key: ctx.userId ?? 'anonymous', ...ctx }, defaultValue);
  },
};
```

```ts
// Stub for tests — no SDK needed
export const stubFlags = (overrides: Record<string, boolean> = {}): FlagClient => ({
  isEnabled: (key) => overrides[key] ?? false,
  getVariant: (key, defaultValue) => (overrides[key] as typeof defaultValue) ?? defaultValue,
});
```

### 4. Write the flag check

Gate the new code path; always provide a fallback.

```ts
// ✅ Good — flag isolated at the call site, fallback is explicit
import { flags } from '../lib/flags';

export async function handleCheckout(req: Request, res: Response) {
  const ctx = { userId: req.user.id, plan: req.user.plan };

  if (flags.isEnabled('new-checkout-flow', ctx)) {
    return newCheckoutHandler(req, res);
  }
  return legacyCheckoutHandler(req, res);
}
```

```ts
// ❌ Bad — flag check buried inside business logic, hard to find and remove later
export function calculateTotal(items: Item[], userId: string) {
  const base = items.reduce((s, i) => s + i.price, 0);
  if (ldClient.variation('discount-rounding-fix', { key: userId }, false)) {
    return Math.round(base * 100) / 100;   // hidden deep in a helper
  }
  return base;
}
```

### 5. Avoid coupling business logic to the flag system

- Pass the evaluated boolean into functions; don't call `flags.isEnabled` from inside pure
  functions or domain models.
- Keep flag checks at the controller / handler / route level where possible.
- Never make a flag check affect database schema or migrations — those changes must be
  backward-compatible on their own.

### 6. Name flags consistently

Use `kebab-case`. Include a prefix that groups related flags.

```
checkout-new-flow          ✅
enable_new_checkout_FLOW   ❌  inconsistent case
flag123                    ❌  meaningless
```

Add a comment or description in the flag dashboard explaining: what it gates, who owns it,
and the intended removal date.

### 7. Track flag age and set a removal date

Flags are temporary by design. Long-lived flags become invisible tech debt.

- When you create a flag, open a ticket for its removal (e.g., "Remove `new-checkout-flow`
  flag after 100% rollout stabilises — target: 2 weeks after full rollout").
- Enforce a maximum age with a lint rule or CI check:

```bash
# Simple shell check — fails CI if a flag string is older than 90 days in the codebase
# (adapt to your flag naming convention)
git log --all --diff-filter=A --format="%ai %H" -- "*.ts" \
  | grep "new-checkout-flow" \
  | awk '{ if (systime() - mktime(gensub(/-/, " ", "g", $1) " " gensub(/:/, " ", "g", $2) " 0") > 7776000) exit 1 }'
```

### 8. Remove a stale flag

Once a flag is at 100% and stable:

1. Search the codebase for every reference to the flag key string.
2. Replace each `if (flags.isEnabled('my-flag')) { NEW } else { OLD }` with just `NEW`.
3. Delete the `OLD` code path and any types / helpers that only existed for it.
4. Archive or delete the flag in the dashboard.
5. Remove the flag key from any test overrides.
6. Commit: `refactor: Remove my-flag feature flag (fully rolled out)`.

```bash
# Find all references before you start
grep -r "new-checkout-flow" src/
```

### 9. Test flag-gated code

Test both branches. Use the stub client, not the real SDK.

```ts
import { stubFlags } from '../lib/flags';

describe('handleCheckout', () => {
  it('uses new flow when flag is on', async () => {
    const handler = buildHandler(stubFlags({ 'new-checkout-flow': true }));
    const res = await handler(mockRequest());
    expect(res.body.flow).toBe('new');
  });

  it('falls back to legacy when flag is off', async () => {
    const handler = buildHandler(stubFlags({ 'new-checkout-flow': false }));
    const res = await handler(mockRequest());
    expect(res.body.flow).toBe('legacy');
  });
});
```

### Rules

- Always provide a safe default (usually `false` / the old behaviour). The flag should fail
  closed, not open.
- Never read flags in migrations, seed scripts, or schema definitions.
- Never hard-code a user ID as the only way to enable a flag in production — use targeting
  rules in the dashboard.
- One flag = one decision. Don't reuse a flag for a second, unrelated feature.
- If the flag SDK is unavailable at startup, default to `false` and log a warning — don't crash.
- Treat the flag key string as an API: once it's in production, don't rename it.
