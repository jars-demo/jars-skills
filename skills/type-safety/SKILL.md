---
name: type-safety
description: Eliminating type errors, unsafe casts, and any-typed holes in TypeScript and Python codebases: enables strict mode, removes every any and cast, narrows types correctly with guards and discriminated unions, uses branded types for domain correctness, validates external data with Zod or Pydantic at runtime, and makes illegal states unrepresentable in the type system. Use when you want to enable TypeScript strict mode, remove any types, add type safety, fix type errors, use discriminated unions, add branded types, make invalid state unrepresentable, validate with Zod or Pydantic, or improve type coverage.
---

## type-safety

Make the type system do work. Every `any`, unsafe cast, and missing type annotation is a
bug waiting to happen that the compiler was willing to catch for free.

### 1. TypeScript — enable strict mode first

Strict mode enables the flags that catch the most real bugs. Turn it on before doing
anything else — it will surface every existing unsafe pattern immediately.

```json
// tsconfig.json
{
  "compilerOptions": {
    "strict": true,              // enables all strict flags below
    "noUncheckedIndexedAccess": true,   // arr[i] returns T | undefined, not T
    "noImplicitOverride": true,
    "exactOptionalPropertyTypes": true, // { x?: string } ≠ { x: string | undefined }
    "noPropertyAccessFromIndexSignature": true
  }
}
```

`strict: true` enables: `strictNullChecks`, `strictFunctionTypes`, `strictBindCallApply`,
`strictPropertyInitialization`, `noImplicitAny`, `noImplicitThis`, `alwaysStrict`.

**Fix `noImplicitAny` errors without suppressing them:**
```ts
// ❌ Suppresses the error — learns nothing
function process(data: any) { ... }

// ❌ Lies about the type
function process(data: unknown) {
  return (data as SomeType).field;   // cast without check = same as any
}

// ✅ Validate the shape before using it
function process(raw: unknown) {
  const data = mySchema.parse(raw);   // throws if invalid — typed after parse
  return data.field;
}
```

---

### 2. Eliminate every `any`

`any` disables the type checker for that value and everything derived from it.
Find all occurrences and fix them one by one.

```bash
# Find every any in the codebase
grep -rn ": any" src/ --include="*.ts"
grep -rn "as any" src/ --include="*.ts"
grep -rn "<any>" src/ --include="*.ts"
```

| `any` appears because... | Replace with |
|--------------------------|-------------|
| External API / JSON response | `unknown` + Zod parse |
| Function that handles multiple types | Generic `<T>` or union |
| Lazy shortcut mid-implementation | The actual type |
| `JSON.parse()` result | `unknown` + schema parse |
| Event handler payload | Specific event type |
| Third-party lib with no types | `@types/<lib>` or local `.d.ts` |

```ts
// ❌ JSON.parse returns any — propagates unsafely
const data = JSON.parse(responseText);
console.log(data.user.email);   // no type checking at all

// ✅ Parse and validate with Zod
import { z } from 'zod';

const responseSchema = z.object({
  user: z.object({ email: z.string().email() }),
});

const data = responseSchema.parse(JSON.parse(responseText));
console.log(data.user.email);   // fully typed
```

---

### 3. Narrow types correctly — no casts

A type cast (`as SomeType`) is a promise to the compiler that you cannot keep.
Use type guards and discriminated unions instead.

```ts
// ❌ Cast — silences the error but doesn't check
function getEmail(user: User | null): string {
  return (user as User).email;   // crashes if user is null at runtime
}

// ✅ Null guard
function getEmail(user: User | null): string {
  if (!user) throw new Error('user is required');
  return user.email;   // user is narrowed to User here
}

// ❌ instanceof cast without check
function handleEvent(event: MouseEvent | KeyboardEvent) {
  const key = (event as KeyboardEvent).key;   // crashes on MouseEvent
}

// ✅ Discriminated narrowing
function handleEvent(event: MouseEvent | KeyboardEvent) {
  if (event instanceof KeyboardEvent) {
    console.log(event.key);     // KeyboardEvent
  } else {
    console.log(event.clientX); // MouseEvent
  }
}
```

**Custom type guards:**
```ts
// ✅ Type predicate — narrows in the calling scope
function isUser(value: unknown): value is User {
  return (
    typeof value === 'object' &&
    value !== null &&
    'id' in value &&
    'email' in value
  );
}

if (isUser(payload)) {
  console.log(payload.email);   // User inside the if block
}
```

---

### 4. Discriminated unions — make illegal states unrepresentable

Instead of optional fields that may or may not exist together, use a union where each
variant is complete and unambiguous.

```ts
// ❌ Optional fields — many combinations are logically invalid
interface OrderState {
  status:       'pending' | 'paid' | 'failed';
  chargeId?:    string;   // present only when paid — but the type doesn't enforce this
  failureCode?: string;   // present only when failed
}

// ❌ This compiles but is logically wrong:
const bad: OrderState = { status: 'pending', chargeId: 'ch_123' };

// ✅ Discriminated union — each variant is self-contained and correct
type OrderState =
  | { status: 'pending' }
  | { status: 'paid';   chargeId: string }
  | { status: 'failed'; failureCode: string };

// The compiler enforces that chargeId is only accessible on 'paid':
function describeOrder(order: OrderState): string {
  switch (order.status) {
    case 'pending': return 'Awaiting payment';
    case 'paid':    return `Paid — charge ${order.chargeId}`;
    case 'failed':  return `Failed — ${order.failureCode}`;
  }
}
```

---

### 5. Branded types — domain correctness the compiler enforces

Branded types prevent passing a `UserId` where an `OrderId` is expected, even though
both are `string` under the hood.

```ts
// Without branding — both are string, compiler can't distinguish them
type UserId  = string;
type OrderId = string;

function getOrder(orderId: OrderId) { ... }
const userId: UserId = 'usr_123';
getOrder(userId);   // ❌ compiles — wrong! should be an error

// ✅ Branded types
type UserId  = string & { readonly __brand: 'UserId' };
type OrderId = string & { readonly __brand: 'OrderId' };

// Smart constructors validate and brand at the boundary
function makeUserId(raw: string): UserId {
  if (!raw.startsWith('usr_')) throw new Error(`Invalid UserId: ${raw}`);
  return raw as UserId;
}

function makeOrderId(raw: string): OrderId {
  if (!raw.startsWith('ord_')) throw new Error(`Invalid OrderId: ${raw}`);
  return raw as OrderId;
}

function getOrder(orderId: OrderId) { ... }

const userId  = makeUserId('usr_123');
const orderId = makeOrderId('ord_456');
getOrder(userId);    // ✅ compile error — UserId not assignable to OrderId
getOrder(orderId);   // ✅ correct
```

---

### 6. Python — Pydantic models and type annotations

```python
# ❌ Untyped — no editor support, no runtime validation
def create_user(data: dict):
    name  = data["name"]
    email = data["email"]
    age   = data.get("age")   # could be anything
    ...

# ✅ Typed with Pydantic — validated at the boundary, typed everywhere else
from pydantic import BaseModel, EmailStr, Field

class CreateUserRequest(BaseModel):
    name:  str = Field(min_length=1, max_length=100)
    email: EmailStr
    age:   int | None = Field(default=None, ge=0, le=150)

def create_user(data: CreateUserRequest) -> User:
    # data.email is guaranteed to be a valid email string
    # data.age is guaranteed to be int between 0 and 150, or None
    ...
```

**Strict mypy config:**
```ini
# mypy.ini
[mypy]
strict            = true
warn_return_any   = true
warn_unused_ignores = true
disallow_any_generics = true
```

```bash
# Find untyped functions
mypy src/ --strict 2>&1 | grep "error:"
```

---

### 7. Exhaustiveness checking — the compiler catches missing cases

```ts
// Compile-time guarantee that every union variant is handled
function assertNever(x: never): never {
  throw new Error(`Unhandled variant: ${JSON.stringify(x)}`);
}

type Shape = { kind: 'circle'; radius: number }
           | { kind: 'square'; side: number }
           | { kind: 'triangle'; base: number; height: number };

function area(shape: Shape): number {
  switch (shape.kind) {
    case 'circle':   return Math.PI * shape.radius ** 2;
    case 'square':   return shape.side ** 2;
    case 'triangle': return 0.5 * shape.base * shape.height;
    default:         return assertNever(shape);   // compile error if a case is missing
  }
}
// Add a new variant to Shape → compile error at assertNever until you handle it. ✅
```

### Rules

- Enable `strict: true` in tsconfig before writing new code, not after.
- Never use `as SomeType` without a preceding runtime check that proves the assertion.
- `any` is a hole in the type system — every `any` in your codebase is an implicit
  `// I have decided not to type-check this`.
- Validate external data (API responses, JSON.parse, env vars, user input) with a schema
  library at the boundary. Types alone are compile-time — they disappear at runtime.
- Use discriminated unions to make illegal state unrepresentable. If optional fields only
  make sense together, they belong in a union variant.
- Brand domain identifiers (UserId, OrderId, ProductId) when they share the same
  primitive type. Mixing them up is a bug the compiler can catch for free.

---

For the TypeScript handbook sections on narrowing, Zod docs, mypy strict flags, and the
branded types pattern, see [references/REFERENCE.md](references/REFERENCE.md).
