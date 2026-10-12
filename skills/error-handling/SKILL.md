---
name: error-handling
description: Add and improve error handling in web applications and APIs. Use when the user asks to improve error handling, add a global error handler, create custom error classes, fix unhandled promise rejections, return consistent error responses, stop leaking stack traces to clients, handle async errors, or make errors easier to debug in production.
---

# Error handling

Handle errors at the right layer, expose the right amount of detail to the client, and
always give operators enough context to diagnose what went wrong. Never swallow errors
silently and never leak internal details to users.

## Ground rules

- **Read the existing error handling before adding to it.** Check for a global handler,
  custom error classes, and existing response shapes. Don't introduce a second pattern.
- **Never swallow errors silently.** A bare `catch {}` or `except: pass` that does nothing
  is always wrong. At minimum, log and re-throw.
- **Never send stack traces or internal error messages to the client.** Log them
  server-side; return a safe, generic message to the caller.
- **Distinguish operational errors from programmer errors.** Operational errors (invalid
  input, not found, auth failure) are expected and handled gracefully. Programmer errors
  (null dereference, assertion failure) should crash the process or alert — not be silently
  caught.
- **Fail loudly in development, gracefully in production.**

---

## Step 0: Read the existing setup

```bash
# Find existing error classes or handlers
grep -r "class.*Error\|ErrorHandler\|error.*middleware\|app\.use.*err\|exception_handler\|HTTPException" \
  --include="*.ts" --include="*.js" --include="*.py" --include="*.go" -l | head -10

# Find swallowed errors
grep -rn "catch\s*{}\|catch.*{\s*}\|except:\s*pass\|except Exception:\s*$" \
  --include="*.ts" --include="*.js" --include="*.py" | head -20
```

---

## Custom error classes

Define a hierarchy once. Every thrown error should be an instance of a known class so
handlers can make decisions without parsing message strings.

### Node.js / TypeScript

```ts
// Base class — all app errors extend this
export class AppError extends Error {
  constructor(
    public readonly message: string,
    public readonly statusCode: number,
    public readonly code: string,       // machine-readable, e.g. "USER_NOT_FOUND"
    public readonly isOperational = true // false = programmer error → crash
  ) {
    super(message);
    this.name = this.constructor.name;
    Error.captureStackTrace(this, this.constructor);
  }
}

// Specific error types
export class NotFoundError extends AppError {
  constructor(resource: string, id?: string) {
    super(
      id ? `${resource} '${id}' not found` : `${resource} not found`,
      404,
      "NOT_FOUND"
    );
  }
}

export class ValidationError extends AppError {
  constructor(
    message: string,
    public readonly fields?: Record<string, string>
  ) {
    super(message, 400, "VALIDATION_ERROR");
  }
}

export class UnauthorizedError extends AppError {
  constructor(message = "Authentication required") {
    super(message, 401, "UNAUTHORIZED");
  }
}

export class ForbiddenError extends AppError {
  constructor(message = "Access denied") {
    super(message, 403, "FORBIDDEN");
  }
}

export class ConflictError extends AppError {
  constructor(message: string) {
    super(message, 409, "CONFLICT");
  }
}
```

### Python

```python
class AppError(Exception):
    def __init__(self, message: str, status_code: int, code: str):
        super().__init__(message)
        self.status_code = status_code
        self.code = code

class NotFoundError(AppError):
    def __init__(self, resource: str, id: str | None = None):
        msg = f"{resource} '{id}' not found" if id else f"{resource} not found"
        super().__init__(msg, 404, "NOT_FOUND")

class ValidationError(AppError):
    def __init__(self, message: str, fields: dict | None = None):
        super().__init__(message, 400, "VALIDATION_ERROR")
        self.fields = fields or {}

class UnauthorizedError(AppError):
    def __init__(self, message: str = "Authentication required"):
        super().__init__(message, 401, "UNAUTHORIZED")

class ForbiddenError(AppError):
    def __init__(self, message: str = "Access denied"):
        super().__init__(message, 403, "FORBIDDEN")
```

---

## Consistent error response shape

Every error response from the API must have the same shape so clients can handle errors
generically:

```json
{
  "error": {
    "code": "USER_NOT_FOUND",
    "message": "User '42' not found",
    "fields": { "email": "Email already in use" }
  }
}
```

- `code` — machine-readable, stable across releases. Clients switch on this.
- `message` — human-readable, safe to display. No stack traces, no SQL, no file paths.
- `fields` — optional, for validation errors that map to specific inputs.

Never return `500 Internal Server Error` with the actual exception message.

---

## Global error handler

### Express (TypeScript)

```ts
import { Request, Response, NextFunction } from "express";
import { AppError } from "./errors";

// Must have 4 parameters — Express identifies error handlers by arity
export function globalErrorHandler(
  err: Error,
  req: Request,
  res: Response,
  _next: NextFunction
) {
  // Log everything server-side
  req.log?.error({ err }, "Request failed") ?? console.error(err);

  if (err instanceof AppError && err.isOperational) {
    return res.status(err.statusCode).json({
      error: {
        code: err.code,
        message: err.message,
        ...(err instanceof ValidationError && { fields: err.fields }),
      },
    });
  }

  // Programmer error or unknown — hide internals from client
  return res.status(500).json({
    error: {
      code: "INTERNAL_ERROR",
      message: "An unexpected error occurred.",
    },
  });
}

// Register last, after all routes
app.use(globalErrorHandler);
```

### FastAPI (Python)

```python
from fastapi import Request
from fastapi.responses import JSONResponse

@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    log.error("request.failed", path=request.url.path, error=str(exc), exc_info=True)
    body = {"error": {"code": exc.code, "message": str(exc)}}
    if isinstance(exc, ValidationError) and exc.fields:
        body["error"]["fields"] = exc.fields
    return JSONResponse(status_code=exc.status_code, content=body)

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    log.error("request.unhandled_error", path=request.url.path, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": {"code": "INTERNAL_ERROR", "message": "An unexpected error occurred."}},
    )
```

---

## Async error handling

In Node.js, unhandled promise rejections crash the process (Node 15+) or produce silent
failures (older). Wrap async route handlers:

```ts
// Utility: wraps an async handler so Express catches rejections
export const asyncHandler =
  (fn: (req: Request, res: Response, next: NextFunction) => Promise<void>) =>
  (req: Request, res: Response, next: NextFunction) =>
    fn(req, res, next).catch(next);  // forwards to the global error handler

// Usage
router.get("/users/:id", asyncHandler(async (req, res) => {
  const user = await userService.findById(req.params.id);
  if (!user) throw new NotFoundError("User", req.params.id);
  res.json(user);
}));
```

### Unhandled rejection safety net

```ts
// In your process entrypoint — catches anything that slips through
process.on("unhandledRejection", (reason) => {
  console.error("Unhandled rejection:", reason);
  // For programmer errors, crash and let the process manager restart
  process.exit(1);
});

process.on("uncaughtException", (err) => {
  console.error("Uncaught exception:", err);
  process.exit(1);
});
```

---

## Where to throw vs where to catch

| Layer | Throw | Catch |
| --- | --- | --- |
| **Route handler** | `NotFoundError`, `ValidationError` | Nothing — let the global handler catch |
| **Service layer** | `ConflictError`, `ForbiddenError` | External service errors (wrap and re-throw) |
| **Repository / DB layer** | Wrap DB errors into `AppError` subclasses | Raw DB driver errors |
| **Global handler** | — | Everything |

Catch at a layer only if you can add context or recover. Otherwise re-throw.

```ts
// Repository — translate DB errors into app errors
async function createUser(data: CreateUserInput) {
  try {
    return await db.user.create({ data });
  } catch (err: any) {
    if (err.code === "P2002") {  // Prisma unique constraint violation
      throw new ConflictError("A user with this email already exists");
    }
    throw err;  // unknown error — let it bubble
  }
}
```

---

## What not to do

```ts
// ❌ Swallowing — the error disappears silently
try {
  await sendEmail(user.email);
} catch {}

// ❌ Logging without re-throwing — the request succeeds when it shouldn't
try {
  await chargeCard(amount);
} catch (err) {
  console.error(err);
  // execution continues — order marked as paid when charge failed
}

// ❌ Returning the raw error message to the client
res.status(500).json({ error: err.message });  // may expose SQL, file paths, internals

// ❌ Using a generic Error when a specific class exists
throw new Error("not found");  // handler can't distinguish from a programmer error

// ✅ Correct: throw specific, catch at the boundary, log server-side, return safe shape
throw new NotFoundError("User", userId);
```

---

## Checklist

- [ ] Custom error class hierarchy defined (`AppError` base + specific subclasses)
- [ ] Global error handler registered as the last middleware / exception handler
- [ ] All error responses use a consistent JSON shape (`code`, `message`, `fields`)
- [ ] Stack traces and internal messages never sent to the client
- [ ] Async route handlers wrapped or using framework-native async support
- [ ] `unhandledRejection` and `uncaughtException` handlers in the process entrypoint
- [ ] DB / external service errors caught at the repository layer and wrapped into `AppError`
- [ ] No bare `catch {}` or `except: pass` blocks — every catch logs or re-throws
- [ ] Operational errors (4xx) logged at WARN; programmer errors (5xx) logged at ERROR
- [ ] Error response for 500 returns `"An unexpected error occurred."`, not the real message
