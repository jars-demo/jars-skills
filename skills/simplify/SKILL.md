---
name: simplify
description: Reducing code to its simplest correct form without changing behaviour: replaces verbose imperative loops with built-in expressions, collapses redundant conditionals, eliminates unnecessary abstraction layers, removes over-engineered patterns, applies early returns to flatten nesting, and spots where a standard library function already does what 40 lines of custom code is doing. Use when you want to simplify code, reduce lines of code, make this shorter, remove over-engineering, flatten nested ifs, replace a loop with a built-in, remove unnecessary abstraction, or make this more readable.
---

## simplify

Find the simplest correct expression of what the code already does. No behaviour changes.

### 1. The rule before touching anything

Simplification must produce identical behaviour. Run the tests before and after every change.
If there are no tests, write a characterisation test first — call the function with real inputs,
record the output, pin it. Then simplify.

Never simplify and fix a bug in the same change. If you find a bug, note it separately.

---

### 2. Replace imperative loops with built-ins

The most common source of unnecessary lines. Built-in functions are faster to read, less
likely to have off-by-one errors, and optimised by the runtime.

```python
# ❌ 6 lines to filter a list
result = []
for user in users:
    if user.is_active:
        result.append(user)

# ✅ 1 line
result = [u for u in users if u.is_active]

# ❌ 7 lines to build a lookup map
mapping = {}
for item in items:
    mapping[item.id] = item

# ✅ 1 line
mapping = {item.id: item for item in items}

# ❌ 8 lines to sum a field
total = 0
for order in orders:
    total += order.amount

# ✅ 1 line
total = sum(order.amount for order in orders)

# ❌ Manual any() check
found = False
for record in records:
    if record.status == "failed":
        found = True
        break

# ✅
found = any(r.status == "failed" for r in records)
```

```ts
// ❌ Imperative filter + map in 7 lines
const result = [];
for (const user of users) {
  if (user.isActive) {
    result.push(user.email);
  }
}

// ✅ 1 line
const result = users.filter(u => u.isActive).map(u => u.email);

// ❌ Manual object build
const lookup: Record<string, Item> = {};
for (const item of items) {
  lookup[item.id] = item;
}

// ✅
const lookup = Object.fromEntries(items.map(i => [i.id, i]));
```

---

### 3. Early returns — flatten nesting, not logic

Deep nesting is the enemy of readability. Guard clauses at the top of a function eliminate
the rightward drift that makes code hard to follow.

```python
# ❌ Nested pyramid — 4 levels deep
def process_order(order):
    if order:
        if order.is_valid():
            if order.user:
                if order.user.is_active:
                    return charge(order)

# ✅ Flat — each guard exits immediately, happy path is obvious
def process_order(order):
    if not order:
        return None
    if not order.is_valid():
        return None
    if not order.user:
        return None
    if not order.user.is_active:
        return None
    return charge(order)
```

```ts
// ❌ 5-level nesting
function processOrder(order: Order | null) {
  if (order) {
    if (order.isValid()) {
      if (order.user) {
        return charge(order);
      }
    }
  }
}

// ✅ Guard clauses
function processOrder(order: Order | null) {
  if (!order) return null;
  if (!order.isValid()) return null;
  if (!order.user) return null;
  return charge(order);
}
```

---

### 4. Collapse redundant conditionals

```python
# ❌ Returns True/False explicitly from a boolean expression
def is_eligible(user):
    if user.age >= 18 and user.is_verified:
        return True
    else:
        return False

# ✅
def is_eligible(user):
    return user.age >= 18 and user.is_verified

# ❌ Assigns variable only to return it
def get_label(status):
    if status == "active":
        label = "Active"
    elif status == "inactive":
        label = "Inactive"
    else:
        label = "Unknown"
    return label

# ✅ Return directly
def get_label(status):
    if status == "active":   return "Active"
    if status == "inactive": return "Inactive"
    return "Unknown"

# ❌ Ternary written as if/else block
if condition:
    value = a
else:
    value = b

# ✅
value = a if condition else b   # Python
value = condition ? a : b;      # JS/TS
```

---

### 5. Use standard library — don't rewrite what already exists

Before writing any utility function, check the standard library and the project's existing
dependencies. Rewriting something that already exists creates two things to maintain.

```python
# ❌ Custom flatten
def flatten(nested):
    result = []
    for sublist in nested:
        for item in sublist:
            result.append(item)
    return result

# ✅ Already exists
from itertools import chain
flat = list(chain.from_iterable(nested))

# ❌ Custom grouping — 10 lines
groups = {}
for item in items:
    key = item.category
    if key not in groups:
        groups[key] = []
    groups[key].append(item)

# ✅
from collections import defaultdict
groups = defaultdict(list)
for item in items:
    groups[item.category].append(item)

# ❌ Custom chunk function
def chunks(lst, n):
    result = []
    for i in range(0, len(lst), n):
        result.append(lst[i:i+n])
    return result

# ✅ Already a one-liner
chunks = [lst[i:i+n] for i in range(0, len(lst), n)]
```

```ts
// ❌ Custom deep clone — 15 lines of recursive copying
// ✅ Already exists (for JSON-serialisable data)
const clone = structuredClone(obj);

// ❌ Custom unique filter
const unique = [];
for (const item of items) {
  if (!unique.includes(item)) unique.push(item);
}
// ✅
const unique = [...new Set(items)];

// ❌ Custom last-element getter
function last(arr) { return arr[arr.length - 1]; }
// ✅
const last = arr.at(-1);
```

---

### 6. Remove unnecessary abstraction

Abstraction that adds indirection without adding clarity is overhead, not design.

```python
# ❌ A function that wraps a single expression with no added logic
def get_user_email(user):
    return user.email

# called as:
email = get_user_email(user)

# ✅ Just use the attribute
email = user.email

# ❌ A class with one method that could be a function
class EmailSender:
    def send(self, to: str, body: str):
        smtp.send(to, body)

sender = EmailSender()
sender.send(to, body)

# ✅ If there is genuinely no state, use a function
def send_email(to: str, body: str):
    smtp.send(to, body)
```

**When abstraction IS justified:**
- The function encapsulates a decision that could change (e.g. which SMTP provider)
- The wrapper adds error handling, logging, or retry logic
- The class manages state across calls
- The abstraction makes tests significantly easier to write

If none of these apply, remove the layer.

---

### 7. Simplify boolean and None checks

```python
# ❌ Verbose None / empty checks
if len(items) > 0:   ...
if items != []:      ...
if items is not None and len(items) > 0: ...

# ✅
if items: ...

# ❌ Double negative
if not user is None: ...

# ✅
if user is not None: ...

# ❌ Explicit comparison to True/False
if is_valid == True:  ...
if is_valid == False: ...

# ✅
if is_valid:  ...
if not is_valid: ...
```

```ts
// ❌
if (items.length > 0) { ... }
if (value !== null && value !== undefined) { ... }

// ✅
if (items.length) { ... }
if (value != null) { ... }   // != null catches both null and undefined
```

---

### 8. Spot over-engineered patterns

These patterns appear most often in AI-generated or over-abstracted code. When you see them,
ask: does this complexity earn its keep?

| Pattern | Signal it's over-engineered | Simpler form |
|---------|---------------------------|-------------|
| Factory that creates one type | No polymorphism needed | Direct instantiation |
| Strategy pattern for one algorithm | No swappability needed | Inline the logic |
| Event bus for in-process calls | No decoupling benefit | Direct function call |
| DTO that mirrors the model exactly | No transformation happening | Use the model directly |
| Config object passed to every function | Only 1–2 fields actually used | Pass the fields directly |
| Custom error class with no extra fields | Adds nothing over the base | Use base exception |
| Wrapper class around a single dict | Dict is already fine | Use the dict |

Apply the test: **if you removed this layer, would anything break or become harder to test?**
If the answer is no, remove it.

---

### 9. Simplification checklist

Before marking a simplification done:

- [ ] Tests pass (run the suite, not just syntax check)
- [ ] Line count is actually lower — count before and after
- [ ] No behaviour was changed (same inputs → same outputs)
- [ ] No new dependencies introduced just to simplify
- [ ] The simplified version is genuinely easier to read, not just shorter
- [ ] Commit is isolated — only simplification, no feature changes

### Rules

- Shorter is not always simpler. A one-liner that needs a comment to explain it is not
  simpler than three readable lines. Optimise for clarity, not character count.
- Never simplify code you do not understand. Read it, trace it, test it first.
- Standard library over custom code — always check before writing a utility function.
- Remove abstraction layers that add indirection without adding value.
- One simplification concern per commit — loops, then conditionals, then abstractions.
  Mixing them makes the diff unreadable.
