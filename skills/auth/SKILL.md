---
name: auth
description: Implement and review authentication and authorization in web applications. Use when the user asks to add login, implement JWT, set up sessions, add OAuth, protect a route, implement role-based access control (RBAC), fix an auth bug, or review auth code for security issues. Never cuts corners on security — always reads the existing auth setup before adding to it.
---

# Auth

Implement authentication (who are you?) and authorization (what are you allowed to do?)
correctly and completely. Auth bugs are security incidents. Read before writing.

## Ground rules

- **Read the existing auth setup first.** Never add a second auth system alongside one
  that already exists.
- **Never roll your own crypto.** Use battle-tested libraries: `bcrypt`/`argon2` for
  passwords, established JWT libraries for tokens, the platform's OAuth library for SSO.
- **Authorization checks belong in the backend.** Never trust the client to enforce what
  a user can access. Always verify on the server.
- **Fail closed.** When in doubt (missing token, ambiguous role, unexpected state), deny
  access. Never default to "allow".
- **Never log tokens, passwords, or credentials** — even in debug statements.
- **If you find a real auth vulnerability, stop and flag it clearly** before doing anything
  else.

---

## Step 0: Read the existing auth

```bash
# Find the auth layer
grep -r "passport\|jsonwebtoken\|jwt\|bcrypt\|argon2\|session\|cookie\|oauth\|middleware.*auth\|auth.*middleware" \
  --include="*.ts" --include="*.js" --include="*.py" --include="*.go" -l | head -10

# Find route protection patterns
grep -rn "requireAuth\|isAuthenticated\|authMiddleware\|Authorize\|@login_required\|@require_auth" \
  --include="*.ts" --include="*.js" --include="*.py" --include="*.go" | head -20

# Check the user model / schema
cat prisma/schema.prisma
cat app/models/user.py
cat src/entities/User.ts
```

Understand: how tokens or sessions are issued, where they're validated, and how routes
are protected before adding anything.

---

## Passwords

### Hashing

Always hash with bcrypt or argon2. Never SHA-256, MD5, or plain storage.

```ts
// Node.js — bcrypt
import bcrypt from "bcrypt";

const SALT_ROUNDS = 12;  // minimum 10; 12 is a good default

async function hashPassword(plain: string): Promise<string> {
  return bcrypt.hash(plain, SALT_ROUNDS);
}

async function verifyPassword(plain: string, hash: string): Promise<boolean> {
  return bcrypt.compare(plain, hash);
}
```

```python
# Python — bcrypt
import bcrypt

def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt(rounds=12)).decode()

def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())
```

Argon2 is preferred for new projects (winner of the Password Hashing Competition):

```ts
import argon2 from "argon2";
const hash = await argon2.hash(plain);
const valid = await argon2.verify(hash, plain);
```

### Validation before hashing

Before hashing, enforce a minimum length (8+ characters). Do not enforce arbitrary
complexity rules (mandatory symbols, max length < 64) — they reduce entropy. Do check
against a breached-password list for high-value apps.

---

## JWT (stateless tokens)

### Issuing

```ts
import jwt from "jsonwebtoken";

const ACCESS_TOKEN_EXPIRY = "15m";   // short-lived
const REFRESH_TOKEN_EXPIRY = "7d";   // longer-lived, stored securely

function issueAccessToken(userId: string, role: string): string {
  return jwt.sign(
    { sub: userId, role },            // minimal claims — no PII in the payload
    process.env.JWT_SECRET!,
    { expiresIn: ACCESS_TOKEN_EXPIRY, algorithm: "HS256" }
  );
}
```

- Keep the payload minimal: `sub` (subject = user ID), `role`, `exp`. No email, no name,
  no permissions lists — those belong in the database.
- Use a strong secret (32+ random bytes). Load from environment, never hardcode.
- For multi-service systems, prefer RS256 (asymmetric) so services can verify without
  sharing the signing secret.

### Verifying

```ts
function verifyAccessToken(token: string): { sub: string; role: string } {
  // jwt.verify throws if the token is expired, tampered, or uses the wrong algorithm
  const payload = jwt.verify(token, process.env.JWT_SECRET!, {
    algorithms: ["HS256"],   // pin the algorithm — prevents "none" algorithm attacks
  });
  return payload as { sub: string; role: string };
}
```

### Refresh token rotation

Access tokens are short-lived. Refresh tokens let users stay logged in without
re-entering credentials.

```ts
// On login: issue both tokens, persist the refresh token
async function login(userId: string, role: string) {
  const accessToken = issueAccessToken(userId, role);
  const refreshToken = crypto.randomBytes(64).toString("hex");  // opaque, not JWT

  // Store hashed refresh token in DB with expiry
  await db.refreshToken.create({
    data: {
      userId,
      tokenHash: await bcrypt.hash(refreshToken, 10),
      expiresAt: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000),
    },
  });

  return { accessToken, refreshToken };
}

// On refresh: validate, rotate (delete old, issue new)
async function refreshAccessToken(refreshToken: string) {
  const stored = await db.refreshToken.findMany({ where: { expiresAt: { gt: new Date() } } });
  const match = await Promise.any(
    stored.map(async (r) => {
      if (await bcrypt.compare(refreshToken, r.tokenHash)) return r;
      throw new Error("no match");
    })
  ).catch(() => null);

  if (!match) throw new UnauthorizedError("Invalid or expired refresh token");

  // Rotate: delete the used token, issue a new one
  await db.refreshToken.delete({ where: { id: match.id } });
  return login(match.userId, match.role);
}
```

Store refresh tokens in an `httpOnly`, `Secure`, `SameSite=Strict` cookie — not in
`localStorage`.

---

## Sessions (server-side)

Use sessions when you need instant revocation (e.g., force logout on password change).

```ts
// Express + express-session
import session from "express-session";
import connectPgSimple from "connect-pg-simple";

const PgSession = connectPgSimple(session);

app.use(session({
  store: new PgSession({ pool }),         // persist in DB, not memory
  secret: process.env.SESSION_SECRET!,
  resave: false,
  saveUninitialized: false,
  cookie: {
    httpOnly: true,    // not accessible from JS
    secure: process.env.NODE_ENV === "production",   // HTTPS only in prod
    sameSite: "strict",
    maxAge: 7 * 24 * 60 * 60 * 1000,   // 7 days
  },
}));
```

On login: `req.session.userId = user.id`
On logout: `req.session.destroy()`
On password change or suspicious activity: delete all sessions for the user.

---

## Route protection middleware

### Express (TypeScript)

```ts
import { Request, Response, NextFunction } from "express";

export function requireAuth(req: Request, res: Response, next: NextFunction) {
  const token = req.cookies.accessToken ?? req.headers.authorization?.split(" ")[1];
  if (!token) return res.status(401).json({ error: "Authentication required" });

  try {
    req.user = verifyAccessToken(token);
    next();
  } catch {
    return res.status(401).json({ error: "Invalid or expired token" });
  }
}

export function requireRole(...roles: string[]) {
  return (req: Request, res: Response, next: NextFunction) => {
    if (!req.user) return res.status(401).json({ error: "Authentication required" });
    if (!roles.includes(req.user.role)) return res.status(403).json({ error: "Forbidden" });
    next();
  };
}

// Usage
router.get("/admin/users", requireAuth, requireRole("admin"), listUsers);
router.delete("/posts/:id", requireAuth, deletePost);
```

### FastAPI (Python)

```python
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer()

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = verify_access_token(credentials.credentials)
        user = await db.get_user(payload["sub"])
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
        return user
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

def require_role(*roles: str):
    async def check(current_user=Depends(get_current_user)):
        if current_user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
        return current_user
    return check

# Usage
@app.get("/admin/users", dependencies=[Depends(require_role("admin"))])
async def list_users(): ...
```

---

## Authorization: resource ownership

Always check that the authenticated user owns the resource they're accessing. Role checks
alone are not enough.

```ts
// Bad — any authenticated user can delete any post
router.delete("/posts/:id", requireAuth, async (req, res) => {
  await db.post.delete({ where: { id: req.params.id } });
  res.status(204).send();
});

// Good — verify ownership before acting
router.delete("/posts/:id", requireAuth, async (req, res) => {
  const post = await db.post.findUnique({ where: { id: req.params.id } });
  if (!post) return res.status(404).json({ error: "Not found" });
  if (post.authorId !== req.user.sub && req.user.role !== "admin") {
    return res.status(403).json({ error: "Forbidden" });
  }
  await db.post.delete({ where: { id: req.params.id } });
  res.status(204).send();
});
```

This pattern (Insecure Direct Object Reference — IDOR) is one of the most common auth
vulnerabilities. Check it on every endpoint that takes a resource ID.

---

## OAuth / SSO (third-party login)

Use an established library. Don't implement OAuth flows manually.

```ts
// Next.js — NextAuth.js / Auth.js
// next-auth handles token exchange, session management, and provider config

import NextAuth from "next-auth";
import GitHub from "next-auth/providers/github";

export const { handlers, signIn, signOut, auth } = NextAuth({
  providers: [
    GitHub({
      clientId: process.env.GITHUB_CLIENT_ID!,
      clientSecret: process.env.GITHUB_CLIENT_SECRET!,
    }),
  ],
  callbacks: {
    session({ session, token }) {
      session.user.id = token.sub!;
      return session;
    },
  },
});
```

```python
# FastAPI — authlib
from authlib.integrations.starlette_client import OAuth

oauth = OAuth()
oauth.register(
    name="google",
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)
```

Never store OAuth `access_token` long-term. Store only the user's profile data from the
provider after first login.

---

## Common vulnerabilities checklist

| Vulnerability | Check |
| --- | --- |
| **IDOR** | Every endpoint with a resource ID verifies ownership |
| **JWT algorithm confusion** | `algorithms` list is pinned, `none` is impossible |
| **Hardcoded secrets** | `JWT_SECRET`, `SESSION_SECRET` come from env, not code |
| **Weak password hashing** | bcrypt/argon2 with cost ≥ 10, not SHA-256 or MD5 |
| **Token in localStorage** | Tokens in `httpOnly` cookies, not `localStorage` |
| **Missing auth on new routes** | Every new route explicitly applies auth middleware |
| **Broken logout** | Logout deletes the session/refresh token server-side |
| **No rate limiting on login** | Brute-force protection on `/login` and `/token` endpoints |
| **Verbose error messages** | Auth failures return generic messages, not "user not found" vs "wrong password" |
| **Privilege escalation** | Role changes go through a separate admin action, not a user-editable field |

---

## Checklist

- [ ] Passwords hashed with bcrypt or argon2 (cost factor ≥ 10)
- [ ] JWT secret loaded from environment variable, not hardcoded
- [ ] JWT algorithm pinned (`algorithms: ["HS256"]`), `"none"` impossible
- [ ] Access tokens short-lived (≤ 15 min), refresh tokens rotated on use
- [ ] Tokens stored in `httpOnly`, `Secure`, `SameSite=Strict` cookies
- [ ] Every protected route has auth middleware applied explicitly
- [ ] Resource ownership verified on every endpoint with an ID parameter (IDOR check)
- [ ] Role-based checks use `403 Forbidden`, not `404` (don't leak resource existence to unauthorized users — unless hiding existence is a requirement)
- [ ] Login endpoint has rate limiting
- [ ] Auth errors return generic messages (no "user not found" vs "wrong password")
- [ ] Logout invalidates the token/session server-side
- [ ] No tokens, passwords, or secrets appear in logs
