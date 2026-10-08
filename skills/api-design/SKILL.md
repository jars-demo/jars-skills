---
name: api-design
description: Design clean, consistent HTTP APIs. Use when the user asks to design an endpoint, review an API contract, add a new route, define request/response shapes, write an OpenAPI spec, or decide on REST vs GraphQL vs RPC for a feature.
---

# API design

Design APIs that are easy to consume, hard to misuse, and consistent enough that a new
developer can guess the next endpoint before reading the docs.

## Ground rules

- **Read what already exists.** Grep for existing routes, OpenAPI/Swagger files, GraphQL schemas,
  or REST conventions before proposing anything new. New endpoints must fit the existing style.
- **One resource, one URL.** Each endpoint does one thing. An endpoint that "creates and also
  sends an email and optionally deletes the old one" is three jobs — split it.
- **Be boring.** Use the HTTP method and status code the spec actually defines. Do not invent
  new conventions when standard ones exist.
- **Design the contract before writing the handler.** Agree on the URL, method, request shape,
  and response shape first. The implementation follows the contract, not the other way around.
- **Never break a published contract** without versioning. Additive changes (new optional fields)
  are usually fine; removing or renaming fields is a breaking change.

## Workflow

### 1. Understand the context

```bash
# Find existing routes
grep -rn "router\.\|app\.\|@app\.\|Route\|path=" src/ --include="*.py" --include="*.ts" --include="*.js"

# Find the OpenAPI or API description file
find . -name "openapi*.yaml" -o -name "openapi*.json" -o -name "swagger*.yaml" | head -5
```

Ask (or find in context):

- What resource does this endpoint act on?
- Who calls it — a browser, a mobile client, another service?
- What authentication scheme is already in use?
- Does the project use REST, GraphQL, tRPC, gRPC, or something else?

### 2. Pick the right method and URL

For REST follow these conventions without deviation:

| Action | Method | URL |
| --- | --- | --- |
| List a collection | `GET` | `/resources` |
| Get one item | `GET` | `/resources/{id}` |
| Create | `POST` | `/resources` |
| Full replace | `PUT` | `/resources/{id}` |
| Partial update | `PATCH` | `/resources/{id}` |
| Delete | `DELETE` | `/resources/{id}` |
| Sub-resource | `GET/POST` | `/resources/{id}/sub` |
| Non-CRUD action | `POST` | `/resources/{id}/action-name` |

URL rules:
- Lowercase, hyphen-separated words: `/payment-methods`, not `/paymentMethods`.
- Plural nouns for collections: `/orders`, not `/order`.
- No verbs in the URL (except action sub-routes): `/users/{id}/activate`, not `/activateUser`.
- No trailing slashes unless the existing API uses them.
- Resource nesting only one level deep: `/orders/{id}/items` yes; `/orders/{id}/items/{iid}/tags` — flatten it.

### 3. Define the request shape

For every non-GET endpoint, define:

```yaml
# Example in OpenAPI 3 style
requestBody:
  required: true
  content:
    application/json:
      schema:
        type: object
        required: [name, email]
        properties:
          name:
            type: string
            minLength: 1
            maxLength: 255
          email:
            type: string
            format: email
        additionalProperties: false
```

Rules:
- Mark every field `required` or optional explicitly. Implicit optionality hides bugs.
- Add `minLength`, `maxLength`, `minimum`, `maximum`, `pattern`, `enum` for every field
  that has a natural constraint.
- `additionalProperties: false` prevents clients from sending junk that gets silently ignored.
- Never accept raw HTML, SQL, or executable content unless the endpoint exists specifically
  to process it, and even then sanitise it.

### 4. Define the response shape

Pick the right status code:

| Situation | Code |
| --- | --- |
| Successful GET, PATCH, PUT | `200 OK` |
| Created resource | `201 Created` + `Location: /resources/{id}` header |
| Accepted for async processing | `202 Accepted` |
| Successful DELETE with no body | `204 No Content` |
| Bad input (client error) | `400 Bad Request` + error body |
| Missing or invalid credentials | `401 Unauthorized` |
| Valid credentials, wrong permissions | `403 Forbidden` |
| Resource not found | `404 Not Found` |
| Method not allowed | `405 Method Not Allowed` |
| Conflict (duplicate, state mismatch) | `409 Conflict` |
| Validation failed | `422 Unprocessable Entity` |
| Server error | `500 Internal Server Error` |

Return consistent error bodies:

```json
{
  "error": {
    "code": "VALIDATION_FAILED",
    "message": "name is required",
    "fields": { "name": "required" }
  }
}
```

Return consistent success bodies. For collections, include pagination metadata:

```json
{
  "data": [...],
  "meta": { "total": 84, "page": 2, "pageSize": 20 }
}
```

Never return a `200` with `{ "success": false }`. Use the status code.

### 5. Handle auth and permissions

- Check whether the existing service uses API keys, JWT, OAuth 2, session cookies, or mTLS.
  Match it — do not introduce a second auth scheme.
- Authorisation belongs in the handler or a middleware, never in the URL
  (`/admin/users` is a smell — use middleware to check roles).
- Return `401` when identity is missing or invalid, `403` when the identity is known but
  not allowed. Never swap them.

### 6. Design for change

Before finalising:

- Could a field name be mistaken for another? Rename it.
- Could a required field become optional later without a breaking change? Make it optional now.
- Is the response returning more data than the caller needs? Consider a `fields` query param
  or a dedicated summary shape.
- Does the endpoint need to be called in a loop? Consider a batch variant.
- Will the resource list grow unbounded? Add cursor- or offset-based pagination from day one.

### 7. Document it

Update the OpenAPI/Swagger file, or create one if none exists:

```bash
# Validate an OpenAPI file
npx @redocly/cli lint openapi.yaml
```

At minimum, each endpoint needs:
- A `summary` (one sentence)
- A `description` for any non-obvious behaviour
- All parameters with types and descriptions
- All possible response codes with example bodies

### 8. Review the contract

Before implementation, share the spec with whoever will consume the API (or re-read it as
if you are the caller):

- Can you build a client from this spec alone, without reading the implementation?
- Are the error codes specific enough to act on?
- Would a new developer guess the next endpoint correctly?

If the answer to any is "no", revise the spec.

## Common mistakes to avoid

| Mistake | Correct approach |
| --- | --- |
| Tunnelling everything through POST `/api/do` | Use resource URLs and the right method |
| Returning `500` for validation errors | Return `400` or `422` with field details |
| Swallowing auth errors as `404` to "hide" resources | Return `403`; hiding is security theatre |
| Nesting resources three levels deep | Flatten: expose the leaf resource directly |
| Mutable resource IDs | IDs are permanent; if a slug changes, keep an alias |
| Skipping pagination on list endpoints | Every collection endpoint needs pagination |
| Returning the whole record after every mutation | Return the updated record or `204`; let the client decide if it needs to re-fetch |
