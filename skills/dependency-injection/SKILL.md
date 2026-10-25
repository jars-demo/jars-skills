---
name: dependency-injection
description: Designing and wiring dependencies through constructor injection so classes are testable, loosely coupled, and easy to swap: defines interfaces/protocols before implementations, injects all dependencies at construction time, wires the object graph at the composition root, avoids service locators and hidden globals, and uses a DI container only when the graph is genuinely large. Use when you want to add dependency injection, make a class testable, inject a database or service dependency, avoid tight coupling, use a DI container, refactor away from global state, wire a FastAPI or Express app with proper DI, or swap an implementation without changing business logic.
---

## dependency-injection

Pass dependencies in — never reach out and grab them. A class that constructs its own
dependencies is a class you cannot test or swap without changing its source code.

### 1. The core principle

```python
# ❌ Tight coupling — class grabs its own dependencies
class OrderService:
    def __init__(self):
        self.repo  = OrderRepository()     # hardwired to one implementation
        self.email = SmtpEmailProvider()   # hardwired to SMTP
        self.db    = get_db_connection()   # hidden global

# ✅ Constructor injection — dependencies passed in, class owns nothing it didn't ask for
class OrderService:
    def __init__(
        self,
        order_repo:    OrderRepositoryProtocol,
        email_service: EmailServiceProtocol,
    ) -> None:
        self._order_repo    = order_repo
        self._email_service = email_service
```

The difference: with injection, tests pass a fake. Without it, tests run against real SMTP.

---

### 2. Define interfaces/protocols before implementations

Write the contract first. The class that uses a dependency should depend on the interface,
not on the concrete class.

```python
# lib/protocols.py
"""
lib/protocols.py
----------------
Protocol definitions for all injectable dependencies.
Business logic imports from here — never from concrete implementations.

Depends on: nothing (stdlib only)
Used by:    services/*, tests/*
"""

from typing import Protocol, runtime_checkable


@runtime_checkable
class OrderRepositoryProtocol(Protocol):
    async def find_by_id(self, order_id: int) -> dict | None: ...
    async def create(self, user_id: int, total_cents: int) -> dict: ...
    async def update_status(self, order_id: int, status: str) -> None: ...


@runtime_checkable
class EmailServiceProtocol(Protocol):
    async def send(self, to: str, subject: str, body: str) -> None: ...


@runtime_checkable
class CacheProtocol(Protocol):
    async def get(self, key: str) -> str | None: ...
    async def set(self, key: str, value: str, ttl: int) -> None: ...
    async def delete(self, key: str) -> None: ...
```

```ts
// lib/protocols.ts
/**
 * lib/protocols.ts
 * ----------------
 * Interfaces for all injectable dependencies.
 * Services depend on these — never on concrete classes.
 *
 * Depends on: nothing
 * Used by:    services/*, tests/*
 */

export interface OrderRepository {
  findById(orderId: number): Promise<Order | null>;
  create(userId: number, totalCents: number): Promise<Order>;
  updateStatus(orderId: number, status: string): Promise<void>;
}

export interface EmailService {
  send(to: string, subject: string, body: string): Promise<void>;
}

export interface Cache {
  get(key: string): Promise<string | null>;
  set(key: string, value: string, ttl: number): Promise<void>;
  delete(key: string): Promise<void>;
}
```

---

### 3. Constructor injection — the right default

```python
# services/order_service.py
"""
services/order_service.py
--------------------------
Business logic for order management.
All dependencies injected — no globals, no hardwired implementations.

Depends on: lib/protocols.py
Used by:    routes/order_routes.py, tests/
"""

from lib.protocols import OrderRepositoryProtocol, EmailServiceProtocol
from lib.logger import get_logger

logger = get_logger(__name__)


class OrderService:
    def __init__(
        self,
        order_repo:    OrderRepositoryProtocol,
        email_service: EmailServiceProtocol,
    ) -> None:
        self._order_repo    = order_repo
        self._email_service = email_service

    async def place_order(self, user_id: int, total_cents: int, email: str) -> dict:
        order = await self._order_repo.create(user_id=user_id, total_cents=total_cents)
        await self._email_service.send(
            to=email,
            subject="Order confirmed",
            body=f"Your order #{order['id']} has been placed.",
        )
        logger.info("Order placed. order_id=%s user_id=%s", order["id"], user_id)
        return order
```

```ts
// services/orderService.ts
import type { OrderRepository, EmailService } from '../lib/protocols';
import { logger } from '../lib/logger';

export class OrderService {
  constructor(
    private readonly orderRepo:    OrderRepository,
    private readonly emailService: EmailService,
  ) {}

  async placeOrder(userId: number, totalCents: number, email: string) {
    const order = await this.orderRepo.create(userId, totalCents);
    await this.emailService.send(email, 'Order confirmed', `Order #${order.id} placed.`);
    logger.info('Order placed', { orderId: order.id, userId });
    return order;
  }
}
```

---

### 4. The composition root — wire everything in one place

The composition root is the single place where concrete implementations are chosen and
the object graph is assembled. It is the only place that imports concrete classes.
Everything else imports protocols/interfaces only.

```python
# lib/container.py
"""
lib/container.py
-----------------
Composition root — wires the full object graph.
This is the ONLY file that imports concrete implementations.
Routes and services import interfaces (protocols.py) only.

Depends on: all concrete implementations
Used by:    main.py
"""

from repositories.order_repository import OrderRepository
from services.email_service import SmtpEmailService
from services.order_service import OrderService
from lib.db import db_pool
from lib.redis import redis_client
from config.settings import settings


def build_order_service() -> OrderService:
    """Build a fully wired OrderService with production dependencies."""
    return OrderService(
        order_repo    = OrderRepository(db_pool),
        email_service = SmtpEmailService(
            host=settings.smtp_host,
            api_key=settings.smtp_api_key,
        ),
    )
```

```python
# main.py / routes/order_routes.py — use the container
from fastapi import APIRouter, Depends
from lib.container import build_order_service
from services.order_service import OrderService

router = APIRouter(prefix="/orders")


def get_order_service() -> OrderService:
    return build_order_service()


@router.post("/", status_code=201)
async def place_order(
    body: PlaceOrderRequest,
    service: OrderService = Depends(get_order_service),
):
    return await service.place_order(
        user_id=body.user_id,
        total_cents=body.total_cents,
        email=body.email,
    )
```

---

### 5. Testing — the payoff of injection

With constructor injection, tests swap real dependencies for fakes without patching,
monkeypatching, or mocking framework magic.

```python
# tests/unit/test_order_service.py
import pytest
from services.order_service import OrderService


# Fake implementations — no mocking framework needed
class FakeOrderRepository:
    def __init__(self):
        self.orders: list[dict] = []

    async def create(self, user_id: int, total_cents: int) -> dict:
        order = {"id": len(self.orders) + 1, "user_id": user_id, "total_cents": total_cents}
        self.orders.append(order)
        return order

    async def find_by_id(self, order_id: int) -> dict | None:
        return next((o for o in self.orders if o["id"] == order_id), None)

    async def update_status(self, order_id: int, status: str) -> None:
        for o in self.orders:
            if o["id"] == order_id:
                o["status"] = status


class FakeEmailService:
    def __init__(self):
        self.sent: list[dict] = []

    async def send(self, to: str, subject: str, body: str) -> None:
        self.sent.append({"to": to, "subject": subject, "body": body})


@pytest.mark.asyncio
async def test_place_order_creates_order_and_sends_email():
    repo    = FakeOrderRepository()
    email   = FakeEmailService()
    service = OrderService(order_repo=repo, email_service=email)

    order = await service.place_order(user_id=1, total_cents=1999, email="user@example.com")

    assert order["id"] == 1
    assert order["total_cents"] == 1999
    assert len(repo.orders) == 1
    assert len(email.sent) == 1
    assert email.sent[0]["to"] == "user@example.com"
```

---

### 6. DI container — only when the graph is genuinely large

A DI container auto-wires the object graph based on type annotations. Use one when
manually wiring > 10–15 dependencies becomes tedious. For smaller apps, manual wiring
in `container.py` is simpler and more explicit.

```python
# Python — dependency-injector library
from dependency_injector import containers, providers
from repositories.order_repository import OrderRepository
from services.email_service import SmtpEmailService
from services.order_service import OrderService


class Container(containers.DeclarativeContainer):
    config = providers.Configuration()

    db_pool = providers.Singleton(
        create_db_pool,
        dsn=config.database_url,
    )

    order_repo = providers.Factory(
        OrderRepository,
        pool=db_pool,
    )

    email_service = providers.Factory(
        SmtpEmailService,
        host=config.smtp_host,
        api_key=config.smtp_api_key,
    )

    order_service = providers.Factory(
        OrderService,
        order_repo=order_repo,
        email_service=email_service,
    )
```

```ts
// TypeScript — tsyringe (lightweight DI container)
import 'reflect-metadata';
import { container, injectable, inject } from 'tsyringe';
import type { OrderRepository } from './lib/protocols';

@injectable()
export class OrderService {
  constructor(
    @inject('OrderRepository') private orderRepo: OrderRepository,
    @inject('EmailService')    private emailService: EmailService,
  ) {}
}

// Registration at startup
container.register('OrderRepository', { useClass: PrismaOrderRepository });
container.register('EmailService',    { useClass: SendgridEmailService });

// Resolution
const service = container.resolve(OrderService);
```

---

### 7. Service locator — the anti-pattern to avoid

```python
# ❌ Service locator — looks like DI but is not
class OrderService:
    def place_order(self, user_id: int):
        repo  = ServiceLocator.get("order_repo")   # hidden dependency
        email = ServiceLocator.get("email")         # no way to see what this needs
        ...

# ❌ Global registry
_services: dict = {}

def get_service(name: str):
    return _services[name]   # implicit dependency, impossible to test in isolation
```

Service locators make dependencies invisible. You cannot tell what a class needs just by
reading its constructor — you have to trace runtime calls. Constructor injection makes
every dependency explicit and visible at the call site.

### Rules

- Define a protocol/interface for every injectable dependency before writing the implementation.
- Every dependency must be injected via the constructor — no class constructs its own dependencies.
- The composition root is the only file that imports concrete implementations. Everything else imports interfaces.
- Write a fake implementation in tests instead of using a mocking framework. Fakes are faster, more readable, and catch interface drift.
- Use a DI container only when the object graph has more than ~15 nodes. For smaller apps, manual wiring in `container.py` is clearer.
- Never use a service locator. Hidden dependencies cannot be tested in isolation.
