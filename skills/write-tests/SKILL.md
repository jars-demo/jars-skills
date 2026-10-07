---
name: write-tests
description: Write meaningful tests for existing or new code. Use when the user asks to add tests, increase coverage, write unit or integration tests, test an edge case, or set up a test suite. Focuses on tests that catch real bugs, not tests that inflate a coverage number.
---

# Write tests

Write tests that find real bugs, document behaviour, and give you confidence to change
code. Not tests that exist only to hit a coverage number.

## Ground rules

- **Read the code before writing a test.** Understand what the function does, what it
  depends on, and what can go wrong. A test written without reading the code tests your
  assumptions, not the actual behaviour.
- **Test behaviour, not implementation.** Tests should survive a refactor. If a test breaks
  when you rename a private variable, it is testing the wrong thing.
- **One assertion per logical scenario.** A test that asserts ten unrelated things tells
  you something broke but not what.
- **Use the project's existing test framework.** Match the style, helpers, fixtures, and
  file layout already in use. Do not introduce a new library without a reason.
- **Tests must be deterministic.** A test that passes sometimes and fails sometimes is
  worse than no test — it trains people to ignore failures.
- **No logic in tests.** No loops, no conditionals, no computed expected values. If the
  test logic is wrong, the test lies.

---

## Step 0: Understand the landscape

```bash
# Find the test framework and runner
cat package.json | grep -E "jest|vitest|mocha|jasmine"   # JS/TS
cat pyproject.toml | grep -E "pytest|unittest"            # Python
cat Cargo.toml | grep -E "\[dev-dependencies\]" -A 5      # Rust

# Find existing tests to match the style
ls tests/ test/ src/**/*.test.* spec/

# Run the suite to establish a baseline
pytest                    # Python
npm test -- --run         # JS/TS (single run)
cargo test                # Rust
go test ./...             # Go
```

Read two or three existing tests before writing your first one. Match their structure,
naming, fixture style, and assertion library exactly.

---

## What to test

### The happy path — but only once

One test that confirms the function works correctly with valid, typical input. This is the
minimum. Do not write five variations of "it works".

### Edge cases — this is where the value is

| Category | Examples |
| --- | --- |
| **Empty / zero** | Empty string, empty array, `0`, `0.0` |
| **Null / undefined / None** | Missing optional fields, unset config, no results from a query |
| **Boundaries** | The exact limit, one below, one above (off-by-one bugs live here) |
| **Type coercion** | `"1"` vs `1`, `true` vs `"true"`, `null` vs `undefined` |
| **Large input** | A list with 10 000 items, a string with 1 MB of text |
| **Special characters** | Unicode, newlines, quotes, SQL metacharacters, HTML tags |
| **Concurrent access** | Two writes at the same time (if the code handles concurrency) |

### Error paths

- What happens when a required argument is missing?
- What happens when an external dependency (database, API) fails?
- What does the function return / raise / reject on invalid input?

### Regression cases

Every bug that was fixed should have a test. Name it after the bug:
`test_discount_never_goes_negative` not `test_bug_fix_123`.

---

## Test naming

The name is the first thing you read when a test fails. Make it a sentence:

```
<unit under test> <condition> <expected outcome>
```

| Bad | Good |
| --- | --- |
| `test_discount` | `test_calculate_discount_returns_zero_when_coupon_exceeds_price` |
| `test_error` | `test_get_user_raises_not_found_when_id_does_not_exist` |
| `test_1` | `test_export_handles_empty_dataset_without_crashing` |
| `should work` | `login_returns_token_when_credentials_are_valid` |

In Jest / Vitest, use `describe` + `it` to form a readable sentence:

```ts
describe("calculateDiscount", () => {
  it("returns zero when the coupon value exceeds the price", () => { ... })
  it("throws InvalidCouponError when the coupon is expired", () => { ... })
})
```

In pytest, use the full name in the function:

```python
def test_calculate_discount_returns_zero_when_coupon_exceeds_price(): ...
def test_calculate_discount_raises_when_coupon_is_expired(): ...
```

---

## Test structure: Arrange → Act → Assert

Every test follows three steps, with a blank line between each:

```python
def test_calculate_discount_applies_percentage_correctly():
    # Arrange
    price = 100.0
    coupon = Coupon(type="percentage", value=20)

    # Act
    result = calculate_discount(price, coupon)

    # Assert
    assert result == 80.0
```

```ts
it("applies a percentage coupon correctly", () => {
  // Arrange
  const price = 100;
  const coupon = { type: "percentage", value: 20 };

  // Act
  const result = calculateDiscount(price, coupon);

  // Assert
  expect(result).toBe(80);
});
```

Keep Arrange short. If setup takes more than ten lines, extract a factory function or
fixture. A bloated Arrange section is a sign the function under test has too many
dependencies.

---

## Mocking and dependencies

Mock external dependencies (databases, HTTP clients, file systems, clocks) — not your own
business logic.

```python
# Good — mock the external call, test your logic
def test_send_invoice_email_logs_error_on_smtp_failure(mocker):
    mocker.patch("app.email.smtp_client.send", side_effect=SMTPError("timeout"))
    with pytest.raises(EmailDeliveryError):
        send_invoice_email(invoice_id=42)

# Bad — mocking your own function to test another function
def test_process_order(mocker):
    mocker.patch("app.orders.calculate_discount", return_value=10)  # don't do this
```

Rules for mocks:
- Mock at the boundary (the HTTP call, the DB query, the file read) — not deep inside
  your own code.
- Verify that the mock was called with the right arguments when the call itself is the
  behaviour being tested.
- Do not mock just to make a test easier to write. If setup is painful, the code is too
  coupled — that is a refactor signal.

---

## Test file layout

Mirror the source tree. Tests live next to the code or in a parallel `tests/` directory:

```
# Option A — co-located (common in JS/TS)
src/
  billing/
    discount.ts
    discount.test.ts

# Option B — parallel tree (common in Python)
src/
  billing/
    discount.py
tests/
  billing/
    test_discount.py
```

One test file per source file. A test file that tests three unrelated modules is hard to
navigate.

---

## Coverage — what it means and what it does not

Coverage tells you which lines were executed, not whether the behaviour is correct. A test
that calls every line but asserts nothing gives 100 % coverage and zero confidence.

**Meaningful coverage targets:**

| Layer | Target |
| --- | --- |
| Pure functions (no I/O) | 90 %+ line coverage, all branches |
| Service / business logic | 80 %+ with edge cases |
| Controllers / handlers | Happy path + common error paths |
| Integration tests | Critical user flows end-to-end |

**How to use coverage well:**

```bash
pytest --cov=src --cov-report=term-missing   # Python
npx vitest run --coverage                    # Vitest
npx jest --coverage                          # Jest
```

Look at the **missing lines**, not the percentage. A line missed in error handling is more
dangerous than a line missed in a comment block. Prioritise uncovered branches in:
- Error handling paths
- Security checks
- Financial calculations
- Data validation

---

## Integration and end-to-end tests

Unit tests cover logic in isolation. Integration tests cover how components work together.

Write an integration test when:
- A feature touches multiple layers (API → service → database)
- A bug was caused by two correct units interacting incorrectly
- You need confidence that the system works as a whole before a release

Keep integration tests few and focused. They are slower and harder to maintain than unit
tests. Do not replace unit tests with integration tests — use both.

---

## What makes a bad test

| Anti-pattern | Why it is harmful |
| --- | --- |
| Testing private methods directly | Breaks on any refactor; test via the public API instead |
| `assert True` or empty test body | Gives false confidence; counts as passing |
| Testing a mock instead of real code | `expect(mock).toBeCalled()` without asserting the outcome |
| Interdependent tests (order matters) | One failure cascades; each test must be independent |
| Hardcoded timestamps and IDs | Fails in a different timezone or after a DB reset |
| `sleep()` / `time.sleep()` in tests | Flaky and slow; mock the clock instead |
| One test that asserts 20 things | When it fails, you do not know which thing broke |

---

## Checklist before submitting tests

- [ ] Tests run and pass with `pytest` / `npm test -- --run` / equivalent
- [ ] Each test name reads as a sentence describing the scenario
- [ ] Arrange → Act → Assert structure, blank lines between sections
- [ ] No logic (loops, conditionals) inside test bodies
- [ ] External dependencies are mocked; own business logic is not
- [ ] Edge cases covered: empty, null, boundary, error path
- [ ] No hardcoded timestamps, sequential IDs, or environment-specific paths
- [ ] Test file mirrors the source file location and name
- [ ] No commented-out tests left behind

---

## Examples

```python
# Pure function — full edge case coverage
def test_calculate_discount_returns_zero_when_coupon_exceeds_price():
    assert calculate_discount(price=10.0, coupon=Coupon(value=50)) == 0.0

def test_calculate_discount_raises_expired_coupon_error():
    expired = Coupon(value=10, expires_at=datetime(2020, 1, 1))
    with pytest.raises(ExpiredCouponError):
        calculate_discount(price=100.0, coupon=expired)

def test_calculate_discount_raises_value_error_on_negative_price():
    with pytest.raises(ValueError, match="price must be >= 0"):
        calculate_discount(price=-1.0, coupon=Coupon(value=10))
```

```ts
// Async function with a dependency
describe("fetchUserProfile", () => {
  it("returns the profile when the user exists", async () => {
    // Arrange
    const mockRepo = { findById: jest.fn().mockResolvedValue({ id: 1, name: "Alice" }) };

    // Act
    const profile = await fetchUserProfile(1, mockRepo);

    // Assert
    expect(profile).toEqual({ id: 1, name: "Alice" });
  });

  it("throws NotFoundError when the user does not exist", async () => {
    // Arrange
    const mockRepo = { findById: jest.fn().mockResolvedValue(null) };

    // Act & Assert
    await expect(fetchUserProfile(99, mockRepo)).rejects.toThrow(NotFoundError);
  });
});
```
