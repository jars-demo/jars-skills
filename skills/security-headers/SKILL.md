---
name: security-headers
description: Hardening HTTP responses with the right security headers. Audits the current headers first, adds Strict-Transport-Security, X-Content-Type-Options, Referrer-Policy, Permissions-Policy, and frame-ancestors, rolls out a nonce-based Content-Security-Policy in Report-Only mode before enforcing it, configures CORS with an explicit origin allow-list, sets Cross-Origin-Opener-Policy, removes headers that leak server versions, and verifies with curl. Use when you want to add security headers, set up a Content Security Policy, fix CSP violations, configure CORS, fix a CORS error, enable HSTS, prevent clickjacking, stop MIME sniffing, pass a security scan or pentest finding about missing headers, use helmet, or harden nginx response headers.
---

## security-headers

Every HTTP response is a chance to tell the browser what it must refuse. Set the headers
once, centrally, and verify them against the live response, not the config file.

### Ground rules

- Follow the project's own conventions first: `CONTRIBUTING.md`, `CLAUDE.md`, `AGENTS.md`,
  existing middleware, and where headers are already set (app, reverse proxy, or CDN).
- Set each header in **one** layer. The same header from both nginx and the app produces
  duplicates, and browsers combine duplicate CSP headers into the strictest intersection.
- Never enforce a new CSP without a Report-Only period first. A wrong policy breaks the site.
- Never enable HSTS `preload` or submit a domain to the preload list unless the user asks
  for that exact action. It is hard to undo and affects every subdomain.
- Do not deploy, push, or change CDN or load balancer settings unless the user asks.
- Report what you verified with real output. If you could not hit a running server, say so.

---

### 1. Audit what is sent today

Check a real response before changing anything. Test an HTML page, an API route, and a
static asset; they are often served by different layers.

```bash
curl -sS -D - -o /dev/null https://localhost:3000/          | sort
curl -sS -D - -o /dev/null https://localhost:3000/api/health | sort
curl -sS -D - -o /dev/null https://localhost:3000/static/app.js | sort
```

Then find where headers are set in the code:

```bash
grep -rnE "helmet|Content-Security-Policy|add_header|Strict-Transport|Access-Control-Allow" \
  --include=*.{js,ts,py,go,conf,yaml,yml,toml} . | grep -v node_modules
```

Write down, per header: present or missing, current value, and which layer sets it.

---

### 2. The baseline set

| Header | Value | Prevents |
| --- | --- | --- |
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains` | Protocol downgrade, cookie theft over HTTP |
| `X-Content-Type-Options` | `nosniff` | MIME sniffing a text upload into script |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | Leaking full URLs (tokens, IDs) to other sites |
| `Permissions-Policy` | `camera=(), microphone=(), geolocation=()` | Third-party scripts using device APIs |
| `Content-Security-Policy` | see step 3, includes `frame-ancestors 'self'` | XSS, clickjacking, data exfiltration |
| `Cross-Origin-Opener-Policy` | `same-origin` | Cross-window attacks (`window.opener`) |
| `X-Frame-Options` | `DENY` or `SAMEORIGIN` | Clickjacking in old browsers (CSP `frame-ancestors` supersedes it) |

Remove or blank these, they only help attackers fingerprint the stack:

- `X-Powered-By` (Express, PHP)
- `Server` version string (`server_tokens off;` in nginx)

Do **not** add `X-XSS-Protection: 1`. The XSS auditor it controls is removed from modern
browsers and the header caused vulnerabilities in old ones. Omit it or send `0`.

HSTS rules:

- Only send it over HTTPS. Browsers ignore it on HTTP, and sending it from a dev server on
  `localhost` can pin HTTPS for that host in your browser.
- Start with `max-age=300` on a new domain, confirm every subdomain serves HTTPS, then raise
  to one year.
- `includeSubDomains` breaks any subdomain still on plain HTTP. Check before adding it.

---

### 3. Content-Security-Policy, nonce-based

A strict CSP with per-response nonces blocks injected scripts without maintaining a list of
allowed domains.

```
Content-Security-Policy:
  default-src 'self';
  script-src 'nonce-{RANDOM}' 'strict-dynamic';
  style-src 'self' 'nonce-{RANDOM}';
  img-src 'self' data:;
  connect-src 'self';
  object-src 'none';
  base-uri 'none';
  frame-ancestors 'self';
  form-action 'self';
  report-to csp-endpoint
```

(Shown on several lines for reading. It must be sent as one header line.)

- The nonce is fresh, random, and at least 128 bits **per response**. A fixed nonce is no
  protection.
- Every `<script>` the app renders gets `nonce="{RANDOM}"`. `'strict-dynamic'` lets those
  scripts load further scripts.
- Never add `'unsafe-inline'` or `'unsafe-eval'` to `script-src` to silence violations. Fix
  the source: move inline handlers (`onclick=`) into script files, replace `eval` and
  `new Function`.
- `object-src 'none'` and `base-uri 'none'` close two common bypasses. Always include them.
- For a JSON-only API, send the minimal policy `default-src 'none'; frame-ancestors 'none'`.

#### Roll out in two phases

1. Send `Content-Security-Policy-Report-Only` with the policy and a report endpoint. Nothing
   is blocked; violations are reported.
2. Collect reports for at least one full release cycle. Fix each real violation in code.
   Ignore noise from browser extensions (`chrome-extension://`, `moz-extension://` sources).
3. Switch the header name to `Content-Security-Policy`. Keep reporting on.

```
Reporting-Endpoints: csp-endpoint="https://example.com/csp-reports"
```

Keep `report-uri /csp-reports` alongside `report-to` until every browser you support
handles `report-to`. The report endpoint must accept `application/csp-report` and
`application/reports+json`, rate-limit by IP, and never echo the body back.

---

### 4. Node.js, Express with helmet

```ts
// middleware/securityHeaders.ts
import crypto from 'node:crypto';
import helmet from 'helmet';
import type { RequestHandler } from 'express';

export const cspNonce: RequestHandler = (_req, res, next) => {
  res.locals.cspNonce = crypto.randomBytes(16).toString('base64');
  next();
};

export const securityHeaders = helmet({
  contentSecurityPolicy: {
    useDefaults: false,
    reportOnly: process.env.CSP_ENFORCE !== 'true',
    directives: {
      defaultSrc: ["'self'"],
      scriptSrc: [(_req, res) => `'nonce-${(res as any).locals.cspNonce}'`, "'strict-dynamic'"],
      styleSrc: ["'self'", (_req, res) => `'nonce-${(res as any).locals.cspNonce}'`],
      imgSrc: ["'self'", 'data:'],
      connectSrc: ["'self'"],
      objectSrc: ["'none'"],
      baseUri: ["'none'"],
      frameAncestors: ["'self'"],
      formAction: ["'self'"],
      reportUri: ['/csp-reports'],
    },
  },
  strictTransportSecurity: { maxAge: 31_536_000, includeSubDomains: true },
  referrerPolicy: { policy: 'strict-origin-when-cross-origin' },
  crossOriginOpenerPolicy: { policy: 'same-origin' },
  xFrameOptions: { action: 'sameorigin' },
});
```

```ts
// app.ts
app.disable('x-powered-by');
app.use(cspNonce);
app.use(securityHeaders);
app.use((_req, res, next) => {
  res.setHeader('Permissions-Policy', 'camera=(), microphone=(), geolocation=()');
  next();
});
```

Pass `res.locals.cspNonce` into templates: `<script nonce="<%= cspNonce %>" src="/app.js">`.

---

### 5. Python, FastAPI / Starlette middleware

```python
# app/middleware/security_headers.py
import secrets

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

STATIC_HEADERS = {
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Cross-Origin-Opener-Policy": "same-origin",
    "X-Frame-Options": "SAMEORIGIN",
}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, enforce_csp: bool = False):
        super().__init__(app)
        self.csp_header = (
            "Content-Security-Policy" if enforce_csp
            else "Content-Security-Policy-Report-Only"
        )

    async def dispatch(self, request: Request, call_next):
        nonce = secrets.token_urlsafe(16)
        request.state.csp_nonce = nonce   # read in templates
        response = await call_next(request)
        response.headers.update(STATIC_HEADERS)
        response.headers[self.csp_header] = (
            f"default-src 'self'; script-src 'nonce-{nonce}' 'strict-dynamic'; "
            f"style-src 'self' 'nonce-{nonce}'; img-src 'self' data:; "
            "connect-src 'self'; object-src 'none'; base-uri 'none'; "
            "frame-ancestors 'self'; form-action 'self'; report-uri /csp-reports"
        )
        return response
```

The `Server: uvicorn` header is added by the server, not the app. Run uvicorn with
`--no-server-header` (or `server_header=False` in `uvicorn.run`) to drop it.

Django: use `SecurityMiddleware` settings (`SECURE_HSTS_SECONDS`,
`SECURE_CONTENT_TYPE_NOSNIFF`, `SECURE_REFERRER_POLICY`, `SECURE_CROSS_ORIGIN_OPENER_POLICY`)
and `django-csp` for the policy, rather than a hand-written middleware.

---

### 6. nginx

```nginx
server_tokens off;

# "always" adds headers to error responses (4xx, 5xx) too.
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
add_header X-Content-Type-Options    "nosniff" always;
add_header Referrer-Policy           "strict-origin-when-cross-origin" always;
add_header Permissions-Policy        "camera=(), microphone=(), geolocation=()" always;
add_header X-Frame-Options           "SAMEORIGIN" always;
```

`add_header` in a `location` block **replaces** every `add_header` inherited from `server`.
Repeat the full set in that `location`, or move them into an `include` file used in both.

Set the CSP in the app, not nginx, when it needs a per-response nonce.

---

### 7. CORS: allow-list, never reflect

CORS relaxes the same-origin policy. It is not a security feature you add; it is a hole you
open as narrowly as possible. Only add it when a browser on another origin must call the API.

```ts
// Express with the cors package
import cors from 'cors';

const ALLOWED_ORIGINS = new Set(config.corsOrigins); // e.g. ['https://app.example.com']

app.use('/api', cors({
  origin: (origin, cb) => cb(null, !origin || ALLOWED_ORIGINS.has(origin)),
  credentials: true,
  methods: ['GET', 'POST', 'PATCH', 'DELETE'],
  allowedHeaders: ['Content-Type', 'Authorization'],
  maxAge: 600,
}));
```

```python
# FastAPI
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,   # explicit list, from config
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
    max_age=600,
)
```

Rules:

- `Access-Control-Allow-Origin: *` with credentials is rejected by browsers. Never "fix" that
  by echoing the request's `Origin` back. That lets every site make authenticated calls.
- Match origins exactly from a set. No `endsWith('example.com')` or unanchored regex:
  `evil-example.com` and `example.com.evil.io` pass those.
- Never allow the `null` origin. Sandboxed iframes and local files send it.
- When the allowed origin varies per request, send `Vary: Origin` so caches do not serve one
  origin's response to another (the `cors` package and Starlette do this).
- Keep origins in config per environment. `http://localhost:5173` belongs in dev only.
- A CORS error in the browser console is often a different failure (a 500 without CORS
  headers, a redirect, a failed preflight). Check the actual response in the network tab
  before widening the policy.

---

### 8. Verify

```bash
# Every expected header present, once
curl -sS -D - -o /dev/null https://localhost:3000/ \
  | grep -iE "strict-transport|content-security|x-content-type|referrer-policy|permissions-policy|cross-origin-opener|x-frame"

# No version leaks
curl -sS -D - -o /dev/null https://localhost:3000/ | grep -iE "^(server|x-powered-by):"

# CORS: allowed origin is echoed, unknown origin is not
curl -sS -D - -o /dev/null -H "Origin: https://app.example.com" https://localhost:3000/api/me | grep -i access-control
curl -sS -D - -o /dev/null -H "Origin: https://evil.example"    https://localhost:3000/api/me | grep -i access-control

# Preflight
curl -sS -D - -o /dev/null -X OPTIONS \
  -H "Origin: https://app.example.com" \
  -H "Access-Control-Request-Method: PATCH" \
  https://localhost:3000/api/orders/1
```

Add a test so the headers cannot silently disappear:

```ts
it('sends security headers on HTML responses', async () => {
  const res = await request(app).get('/');
  expect(res.headers['x-content-type-options']).toBe('nosniff');
  expect(res.headers['content-security-policy-report-only'] ?? res.headers['content-security-policy'])
    .toMatch(/object-src 'none'/);
  expect(res.headers['x-powered-by']).toBeUndefined();
});

it('does not grant CORS to unknown origins', async () => {
  const res = await request(app).get('/api/me').set('Origin', 'https://evil.example');
  expect(res.headers['access-control-allow-origin']).toBeUndefined();
});
```

Open the main pages in a browser with devtools open and confirm the console shows no CSP
violations from the app's own code.

---

### Examples

| Weak | Strong |
| --- | --- |
| `script-src 'self' 'unsafe-inline'` | `script-src 'nonce-…' 'strict-dynamic'`, inline handlers moved to files |
| Enforce a new CSP on Friday | Report-Only for a release cycle, fix violations, then enforce |
| `res.setHeader('Access-Control-Allow-Origin', req.headers.origin)` | Exact match against a configured allow-list |
| Headers set in nginx and the app | One layer owns each header |
| `add_header` in one `location`, others silently lost | Full set repeated or included in each block |
| "Headers added" | `curl -D -` output showing each header on the live response |

### Rules

- Audit the live response first, change second, verify the live response last.
- One layer owns each header. Duplicates cause conflicts.
- CSP: nonce per response, `object-src 'none'`, `base-uri 'none'`, no `'unsafe-inline'`
  in `script-src`, Report-Only before enforce.
- HSTS only over HTTPS; never `preload` unless the user asks.
- CORS: explicit origin set, exact match, never reflect `Origin`, never allow `null`.
- Strip `X-Powered-By` and server version strings.
- Lock the headers in with a test.
