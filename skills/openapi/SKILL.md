---
name: openapi
description: Generate, validate, and maintain OpenAPI specs for HTTP APIs. Use when the user asks to write an OpenAPI spec, generate a swagger file, document an API, add request/response schemas, validate an existing spec, keep the spec in sync with code, add examples to an OpenAPI file, or fix OpenAPI validation errors.
---

# OpenAPI

Write and maintain OpenAPI 3.1 specs that are valid, complete, and actually match what the
server returns. Read the code before writing the spec — never document what you assume the
API does.

## Ground rules

- **Read the route handlers before writing schemas.** The spec documents what the code does,
  not what you think it should do.
- **Validate the spec after every change.** An invalid spec is worse than no spec — it breaks
  codegen and misleads consumers.
- **One source of truth.** Either the spec drives the code (spec-first) or the code drives
  the spec (code-first). Pick one and state it. Never let them silently diverge.
- **Never add endpoints or fields to the spec that don't exist in the code.** Flag the gap
  and let the user decide whether to add the code or remove the spec entry.

---

## Step 0: Understand the existing setup

```bash
# Does a spec already exist?
ls openapi.yaml openapi.json docs/openapi* api/openapi* swagger.yaml

# What framework is in use?
cat package.json | grep -E "express|fastify|hono|nestjs|koa"
cat pyproject.toml | grep -E "fastapi|flask|django|litestar"
cat go.mod | grep -E "gin|echo|chi|fiber"

# Is there an existing codegen or validation step?
cat package.json | grep -E "openapi|swagger|redoc|spectral"
```

If a spec already exists, read it fully before touching it.

---

## Spec structure

Use OpenAPI 3.1. The minimal valid structure:

```yaml
openapi: "3.1.0"

info:
  title: My API
  version: "1.0.0"
  description: One sentence about what this API does.

servers:
  - url: https://api.example.com/v1
    description: Production
  - url: http://localhost:3000/v1
    description: Local development

paths:
  /users/{id}:
    get:
      operationId: getUser
      summary: Get a user by ID
      tags: [Users]
      parameters:
        - name: id
          in: path
          required: true
          schema:
            type: string
            format: uuid
      responses:
        "200":
          description: User found
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/User"
              example:
                id: "550e8400-e29b-41d4-a716-446655440000"
                email: "alice@example.com"
                createdAt: "2024-01-15T10:30:00Z"
        "404":
          $ref: "#/components/responses/NotFound"
        "401":
          $ref: "#/components/responses/Unauthorized"

components:
  schemas:
    User:
      type: object
      required: [id, email, createdAt]
      properties:
        id:
          type: string
          format: uuid
        email:
          type: string
          format: email
        createdAt:
          type: string
          format: date-time

  responses:
    NotFound:
      description: Resource not found
      content:
        application/json:
          schema:
            $ref: "#/components/schemas/Error"
    Unauthorized:
      description: Missing or invalid authentication
      content:
        application/json:
          schema:
            $ref: "#/components/schemas/Error"

    Error:
      type: object
      required: [code, message]
      properties:
        code:
          type: string
        message:
          type: string

  securitySchemes:
    bearerAuth:
      type: http
      scheme: bearer
      bearerFormat: JWT

security:
  - bearerAuth: []
```

---

## Writing schemas

### Required vs optional

Every field must be either in `required` or explicitly optional. A field listed in
`properties` but not in `required` is optional (nullable by default in OpenAPI 3.1 only if
`nullable: true` or the type includes `null`).

```yaml
# 3.1 — use type arrays for nullable
type: [string, "null"]

# 3.0 (legacy) — use nullable
type: string
nullable: true
```

### Reuse with $ref

Put every schema used more than once in `components/schemas`. Inline schemas that appear
once are fine; copy-pasted inline schemas are not.

```yaml
# Good — reused via $ref
schema:
  $ref: "#/components/schemas/User"

# Bad — same shape pasted in three places
schema:
  type: object
  properties:
    id:
      type: string
```

### Arrays

```yaml
type: array
items:
  $ref: "#/components/schemas/User"
minItems: 0
```

### Enums

```yaml
status:
  type: string
  enum: [active, suspended, deleted]
```

### Discriminated unions (3.1)

```yaml
schema:
  oneOf:
    - $ref: "#/components/schemas/CreditCardPayment"
    - $ref: "#/components/schemas/BankTransferPayment"
  discriminator:
    propertyName: method
    mapping:
      card: "#/components/schemas/CreditCardPayment"
      bank: "#/components/schemas/BankTransferPayment"
```

---

## Parameters

```yaml
parameters:
  # Path param — always required: true
  - name: userId
    in: path
    required: true
    schema:
      type: string
      format: uuid

  # Query param with default
  - name: page
    in: query
    schema:
      type: integer
      minimum: 1
      default: 1

  # Header
  - name: X-Request-ID
    in: header
    schema:
      type: string
      format: uuid
```

---

## Request bodies

```yaml
requestBody:
  required: true
  content:
    application/json:
      schema:
        $ref: "#/components/schemas/CreateUserRequest"
      example:
        email: "alice@example.com"
        name: "Alice"
```

---

## Response coverage

Every endpoint must have:
- The success response (`200`, `201`, `204`)
- `400` for invalid input (if the endpoint validates anything)
- `401` if authentication is required
- `403` if authorization can fail separately from auth
- `404` for resource lookups by ID
- `422` for validation errors (if you use it separately from `400`)
- `500` is optional — include it if your error format is documented

Don't list every possible HTTP status code. Document the ones the client needs to handle.

---

## Validation

Always validate the spec before committing:

```bash
# Spectral — the standard linter (catches style + correctness issues)
npx @stoplight/spectral-cli lint openapi.yaml

# swagger-cli — validates spec structure
npx swagger-cli validate openapi.yaml

# redocly — validates and previews
npx @redocly/cli lint openapi.yaml
npx @redocly/cli preview-docs openapi.yaml   # opens a browser preview
```

Fix every error. Warnings are worth reading — most are real issues.

Common validation errors and fixes:

| Error | Fix |
| --- | --- |
| `Property 'required' must be an array` | Move `required: true` into the `parameters` block, not inside `schema` for path/query params |
| `$ref target not found` | Check the path in `$ref` — it's case-sensitive |
| `Duplicate operationId` | Every operation must have a unique `operationId` |
| `Missing required field: responses` | Every `path + method` must have at least one response |
| `Schema has no properties` | Add `properties`, or use `type: object` with `additionalProperties` |
| `oneOf/anyOf contains only one schema` | Use a direct `$ref` instead |

---

## Keeping the spec in sync with code

### Code-first workflow (generate from code)

Many frameworks can generate an OpenAPI spec automatically. Prefer this over maintaining a
hand-written spec for large APIs.

```bash
# FastAPI — auto-generates at runtime
# GET /openapi.json  (built-in)
curl http://localhost:8000/openapi.json | python -m json.tool > openapi.json

# NestJS with @nestjs/swagger
# Spec is built in main.ts via SwaggerModule.createDocument()

# Express with tsoa
npx tsoa spec          # generates openapi.json from decorators and JSDoc
npx tsoa routes        # generates the route wiring

# Hono with zod-openapi
# Spec is built in-process via app.getOpenAPIDocument()
```

After generating: validate with Spectral, commit the output file, add generation to CI.

### Spec-first workflow (generate code from spec)

```bash
# Generate a server stub or client from the spec
npx @openapitools/openapi-generator-cli generate \
  -i openapi.yaml \
  -g typescript-fetch \
  -o src/generated/api-client

# Or with orval (TypeScript + React Query / SWR)
npx orval --config orval.config.ts
```

The generated code should never be hand-edited. Regenerate it whenever the spec changes.
Add the generation command to CI so drift is caught immediately.

### Drift detection in CI

Add a step that regenerates and fails if the output differs:

```yaml
# GitHub Actions
- name: Check spec is up to date
  run: |
    npx tsoa spec
    git diff --exit-code openapi.json || (echo "openapi.json is out of date. Run 'npx tsoa spec' and commit." && exit 1)
```

---

## Adding examples

Good examples make a spec usable. Add them at the schema level for reuse, and at the
operation level for context:

```yaml
components:
  schemas:
    User:
      type: object
      required: [id, email]
      properties:
        id:
          type: string
          format: uuid
          example: "550e8400-e29b-41d4-a716-446655440000"
        email:
          type: string
          format: email
          example: "alice@example.com"

paths:
  /users:
    post:
      requestBody:
        content:
          application/json:
            schema:
              $ref: "#/components/schemas/CreateUserRequest"
            examples:
              typical:
                summary: Standard user creation
                value:
                  email: "alice@example.com"
                  name: "Alice"
              minimal:
                summary: Only required fields
                value:
                  email: "bob@example.com"
```

Use real-looking values (UUID format for IDs, ISO 8601 for dates, valid emails). Avoid
`foo`, `string`, `1234`.

---

## Checklist

- [ ] Spec opens with `openapi: "3.1.0"` and a valid `info` block
- [ ] Every path has at least the success response documented
- [ ] Auth-required endpoints have `401` (and `403` if needed)
- [ ] All `$ref` targets exist in `components`
- [ ] Required fields listed in `required` arrays, not just in property descriptions
- [ ] Every operation has a unique `operationId`
- [ ] Schemas used more than once are in `components/schemas`, not inlined
- [ ] At least one example per request body and success response
- [ ] `npx @stoplight/spectral-cli lint openapi.yaml` passes with no errors
- [ ] Spec matches what the code actually returns (verified by reading route handlers)
