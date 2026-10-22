---
name: testing-strategy
description: Designing a test suite that catches real bugs without becoming a maintenance burden: applies the test pyramid (unit, integration, contract, E2E), decides what to test at each layer, writes tests that test behaviour not implementation, avoids over-mocking, uses real databases in integration tests, and keeps the suite fast enough to run on every commit. Use when you want to design a testing strategy, decide what to unit test vs integration test, set up integration tests with a real database, write contract tests, avoid over-mocking, make tests faster, reduce brittle tests, or plan a test suite for a new service.
---

## testing-strategy

Test behaviour, not implementation. The test suite should catch bugs that matter —
not just verify that functions call each other in a specific order.

### 1. The test pyramid — what goes at each layer

```
         ┌─────────┐
         │   E2E   │  ← few, slow, catch integration bugs across the whole stack
         ├─────────┤
         │Contract │  ← verify producer/consumer agreements without full E2E
         ├─────────┤
         │Integrat.│  ← real DB, real cache, test the full slice
         ├─────────┤
         │  Unit   │  ← many, fast, pure business logic only
         └─────────┘
```

| Layer | What to test | Mocks | Speed |
|-------|-------------|-------|-------|
| **Unit** | Pure functions, domain logic, validation rules, algorithms | External I/O only | < 10 ms |
| **Integration** | Repository + real DB, service + real cache, HTTP handler → DB | None or minimal | < 500 ms |
| **Contract** | Producer schema matches consumer expectations | None | < 100 ms |
| **E2E** | Critical user journeys through the live system | None | Seconds |

---

### 2. Unit tests — test behaviour, not implementation

```python
# ❌ Tests implementation — breaks when you rename internal variables
def test_calculate_tax_calls_rate_lookup():
    with patch("services.tax._get_rate") as mock:
        mock.return_value = 0.1
        calculate_tax(100)
    mock.assert_called_once_with("US")   # implementation detail

# ✅ Tests behaviour — survives any internal refactor
def test_calculate_tax_applies_correct_rate():
    assert calculate_tax(amount=100, country="US") == 10
    assert calculate_tax(amount=200, country="UK") == 40
    assert calculate_tax(amount=100, country="XX") == 0   # unknown country = no tax
```

**What belongs in unit tests:**
- Pure functions: tax calculations, validation logic, formatters, algorithms
- Domain model invariants: `Order.can_be_cancelled()`, `User.is_eligible()`
- Edge cases: empty input, boundary values, error conditions
- Business rules that are likely to change

**What does NOT belong in unit tests:**
- Code that is just glue (calls function A then B then C with no logic)
- Database queries — test those in integration tests with a real DB
- HTTP handlers — test those with a real server and real routes

---

### 3. Integration tests — real dependencies, no mocks

The most valuable tests in most codebases. Test a full slice: HTTP request → handler →
service → repository → real database → response.

```python
# tests/integration/test_order_api.py
"""
Integration tests for the order API.
Uses a real PostgreSQL database (test schema, rolled back after each test).
No mocks — if this passes, the feature works end-to-end within the service.
"""

import pytest
from httpx import AsyncClient
from main import app
from tests.fixtures import create_test_user, create_test_tenant


@pytest.fixture(autouse=True)
async def rollback_db(db):
    """Roll back all DB changes after each test — tests are isolated."""
    async with db.transaction():
        yield
        raise Exception("rollback")   # force rollback


@pytest.mark.asyncio
async def test_place_order_returns_201(client: AsyncClient, auth_headers):
    response = await client.post(
        "/v1/orders",
        json={"product_id": 1, "quantity": 2},
        headers=auth_headers,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "pending"
    assert body["total_cents"] > 0
    assert "id" in body


@pytest.mark.asyncio
async def test_place_order_with_unknown_product_returns_404(client: AsyncClient, auth_headers):
    response = await client.post(
        "/v1/orders",
        json={"product_id": 99999, "quantity": 1},
        headers=auth_headers,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_place_order_enforces_quantity_limit(client: AsyncClient, auth_headers):
    response = await client.post(
        "/v1/orders",
        json={"product_id": 1, "quantity": 101},   # over limit
        headers=auth_headers,
    )
    assert response.status_code == 422
    assert "quantity" in response.json()["details"]
```

**Integration test setup — real PostgreSQL with pytest:**

```python
# tests/conftest.py
import pytest
import asyncpg
from httpx import AsyncClient, ASGITransport
from main import app

TEST_DB_URL = "postgresql://test_user:test@localhost:5432/test_db"


@pytest.fixture(scope="session")
async def db_pool():
    pool = await asyncpg.create_pool(TEST_DB_URL)
    yield pool
    await pool.close()


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.fixture
async def auth_headers(db_pool):
    user = await create_test_user(db_pool)
    token = create_test_jwt(user.id, tenant_id="test-tenant")
    return {"Authorization": f"Bearer {token}"}
```

---

### 4. Contract tests — verify producer/consumer agreements

Contract tests check that a producer's output matches what consumers expect —
without running both services simultaneously. Use Pact or a simple schema check.

```python
# tests/contract/test_order_event_contract.py
"""
Contract test: verifies that the OrderPlacedV1 event schema matches
what the notification service expects to receive.
"""

from lib.events import OrderPlacedV1
from pydantic import ValidationError
import pytest


# The fields the notification service depends on — documented here
REQUIRED_FIELDS_FOR_NOTIFICATION = ["order_id", "user_id", "tenant_id", "total_cents"]


def test_order_placed_v1_contains_notification_required_fields():
    """Consumer contract: notification service needs these fields."""
    event = OrderPlacedV1(
        order_id=1,
        tenant_id="tenant_abc",
        user_id=42,
        total_cents=1999,
        currency="USD",
    )
    for field in REQUIRED_FIELDS_FOR_NOTIFICATION:
        assert hasattr(event, field), f"Missing required field: {field}"
        assert getattr(event, field) is not None


def test_order_placed_v1_rejects_negative_total():
    """Consumer expects total_cents to always be positive."""
    with pytest.raises(ValidationError):
        OrderPlacedV1(order_id=1, tenant_id="t", user_id=1, total_cents=-1, currency="USD")
```

---

### 5. What to mock — and what not to

```python
# ✅ Mock external services — network calls that cost money or are unreliable
@pytest.fixture
def mock_stripe(mocker):
    return mocker.patch("lib.stripe_client.stripe.PaymentIntent.create",
                        return_value={"id": "pi_test", "status": "succeeded"})

# ✅ Mock time — makes tests deterministic
@pytest.fixture
def frozen_time(mocker):
    return mocker.patch("services.order_service.datetime",
                        return_value=datetime(2026, 1, 1, tzinfo=timezone.utc))

# ❌ Don't mock the database — use a real test DB
# Tests that mock the DB only verify that your code calls the right ORM methods,
# not that the queries actually work.

# ❌ Don't mock your own service layer in integration tests
# If you mock UserService in an order test, you're not testing the integration
```

---

### 6. Keeping the suite fast

| Technique | Impact |
|-----------|--------|
| Run tests in parallel (`pytest-xdist -n auto`) | 4–8× faster |
| Use DB transactions + rollback instead of truncate | ~10× faster per test |
| Session-scoped DB pool, function-scoped transactions | Pool creation once, isolation per test |
| Avoid `sleep()` in tests — use `wait_for` with timeout | Removes flakiness |
| Skip E2E in unit/integration CI, run separately | Keeps PR feedback < 60 s |

```bash
# Run unit + integration in parallel — should finish in < 60 s
pytest tests/unit tests/integration -n auto --timeout=30

# Run E2E separately (nightly or on merge to main)
pytest tests/e2e --timeout=120
```

---

### 7. Test naming — tests as documentation

```python
# ❌ Tells you nothing when it fails
def test_order():
    ...

def test_order_2():
    ...

# ✅ Reads as a sentence — tells you exactly what broke
def test_place_order_with_valid_product_returns_pending_status():
    ...

def test_place_order_with_out_of_stock_product_returns_409():
    ...

def test_cancel_order_after_shipping_raises_invalid_state_error():
    ...
```

Pattern: `test_<action>_<condition>_<expected_outcome>`

### Rules

- Test behaviour, not implementation. A test that breaks when you rename a private method
  is not testing anything useful.
- Use a real database in integration tests. Mocking the DB only verifies ORM call patterns.
- One assertion concept per test. Multiple unrelated assertions make failure messages useless.
- Tests must be deterministic. Flaky tests erode trust in the entire suite — fix or delete them.
- The test suite must run in CI on every commit. If it takes more than 5 minutes, it will be skipped.
- Write the test name as a sentence. It is documentation for the engineer who inherits the code.
- Delete tests that no longer reflect the current behaviour. Dead tests create false confidence.
