---
name: notifications
description: Designing and implementing a multi-channel notification system: routes notifications through email, push, SMS, and in-app channels based on user preferences, renders templates with user data, tracks delivery status, deduplicates within time windows to prevent spam, respects opt-outs, and sends through the background job queue so the request path is never blocked. Use when you want to send notifications, implement email notifications, add push notifications, build an in-app notification system, manage notification preferences, track delivery status, prevent notification spam, or route alerts through multiple channels.
---

## notifications

Decouple notification delivery from business logic. Business logic fires an event —
the notification system decides channel, template, and timing.

### 1. The architecture

```
Business logic
    │ fires NotificationRequest
    ▼
NotificationService      ← checks preferences, deduplicates, rate-limits
    │
    ├── EmailChannel     ← renders template, sends via provider
    ├── PushChannel      ← sends to FCM / APNs
    ├── SMSChannel       ← sends via Twilio / SNS
    └── InAppChannel     ← writes to notifications table
```

Business logic never calls a channel directly. It calls `NotificationService.send()`.

---

### 2. Notification request — typed, not stringly typed

```python
# lib/notifications.py
"""
lib/notifications.py
---------------------
Notification request types and the central dispatch service.

Depends on: services/channels/, repositories/notification_repository.py
Used by:    services/* (fire and forget via background queue)
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any


class Channel(str, Enum):
    EMAIL  = "email"
    PUSH   = "push"
    SMS    = "sms"
    IN_APP = "in_app"


class NotificationType(str, Enum):
    ORDER_CONFIRMED       = "order.confirmed"
    PAYMENT_FAILED        = "payment.failed"
    PASSWORD_RESET        = "password.reset"
    WEEKLY_DIGEST         = "weekly.digest"
    SECURITY_ALERT        = "security.alert"


@dataclass(frozen=True)
class NotificationRequest:
    notification_type: NotificationType
    user_id:           int
    tenant_id:         str
    data:              dict[str, Any]        # template variables
    channels:          list[Channel]         # preferred channels — service may override
    idempotency_key:   str                   # prevents duplicates on retry
```

---

### 3. Notification service — preferences, dedup, dispatch

```python
# services/notification_service.py
"""
services/notification_service.py
----------------------------------
Orchestrates notification delivery: checks user preferences, deduplicates
within a time window, and dispatches to the right channels.

Depends on:
  - repositories/notification_repository.py
  - services/channels/email_channel.py
  - services/channels/push_channel.py
  - services/channels/in_app_channel.py
  - lib/notifications.py

Used by: workers/notification_worker.py
"""

from lib.notifications import Channel, NotificationRequest, NotificationType
from repositories.notification_repository import NotificationRepository
from services.channels.email_channel import EmailChannel
from services.channels.push_channel import PushChannel
from services.channels.in_app_channel import InAppChannel
from lib.logger import get_logger

logger = get_logger(__name__)

# Dedup window per notification type — prevents spam on retries
DEDUP_WINDOW_SECONDS: dict[NotificationType, int] = {
    NotificationType.ORDER_CONFIRMED: 300,    # 5 min — safe to re-send after
    NotificationType.PAYMENT_FAILED:  3600,   # 1 hour
    NotificationType.WEEKLY_DIGEST:   86400,  # 1 day
    NotificationType.SECURITY_ALERT:  60,     # 1 min — urgent, allow frequent
    NotificationType.PASSWORD_RESET:  300,
}


class NotificationService:
    def __init__(self) -> None:
        self._repo        = NotificationRepository()
        self._channels    = {
            Channel.EMAIL:  EmailChannel(),
            Channel.PUSH:   PushChannel(),
            Channel.IN_APP: InAppChannel(),
        }

    async def send(self, req: NotificationRequest) -> None:
        # 1. Idempotency — already sent?
        if await self._repo.is_duplicate(req.idempotency_key):
            logger.info(
                "Duplicate notification skipped. key=%s type=%s user_id=%s",
                req.idempotency_key, req.notification_type, req.user_id,
            )
            return

        # 2. Deduplication within time window
        dedup_window = DEDUP_WINDOW_SECONDS.get(req.notification_type, 300)
        if await self._repo.sent_recently(req.user_id, req.notification_type, dedup_window):
            logger.info(
                "Notification suppressed — sent recently. type=%s user_id=%s window_s=%d",
                req.notification_type, req.user_id, dedup_window,
            )
            return

        # 3. Load user preferences and opt-outs
        prefs = await self._repo.get_preferences(req.user_id)
        active_channels = [
            ch for ch in req.channels
            if prefs.is_enabled(req.notification_type, ch)
        ]

        if not active_channels:
            logger.info(
                "No active channels for notification. type=%s user_id=%s",
                req.notification_type, req.user_id,
            )
            return

        # 4. Dispatch to each active channel
        for channel in active_channels:
            handler = self._channels.get(channel)
            if not handler:
                logger.warning("Unknown channel, skipping. channel=%s", channel)
                continue
            try:
                await handler.send(req)
                await self._repo.record_sent(req.idempotency_key, req.user_id,
                                              req.notification_type, channel)
                logger.info(
                    "Notification sent. type=%s user_id=%s channel=%s",
                    req.notification_type, req.user_id, channel,
                )
            except Exception as exc:
                logger.error(
                    "Notification delivery failed. type=%s user_id=%s channel=%s error=%s",
                    req.notification_type, req.user_id, channel, exc,
                )
                # Continue — try remaining channels even if one fails
```

---

### 4. Email channel — template rendering

```python
# services/channels/email_channel.py
"""
services/channels/email_channel.py
------------------------------------
Renders email templates and sends via the configured provider.

Depends on: lib/email_provider.py, templates/email/
Used by:    services/notification_service.py
"""

from jinja2 import Environment, FileSystemLoader
from lib.email_provider import email_provider
from lib.logger import get_logger
from lib.notifications import NotificationRequest, NotificationType

logger = get_logger(__name__)

_jinja = Environment(
    loader=FileSystemLoader("templates/email"),
    autoescape=True,   # always escape — prevents XSS in email HTML
)

TEMPLATES: dict[NotificationType, tuple[str, str]] = {
    NotificationType.ORDER_CONFIRMED: ("order_confirmed.html", "Your order is confirmed"),
    NotificationType.PAYMENT_FAILED:  ("payment_failed.html",  "Action required: payment failed"),
    NotificationType.WEEKLY_DIGEST:   ("weekly_digest.html",   "Your weekly summary"),
    NotificationType.SECURITY_ALERT:  ("security_alert.html",  "Security alert on your account"),
    NotificationType.PASSWORD_RESET:  ("password_reset.html",  "Reset your password"),
}


class EmailChannel:
    async def send(self, req: NotificationRequest) -> None:
        template_file, default_subject = TEMPLATES.get(
            req.notification_type, (None, None)
        )
        if not template_file:
            raise ValueError(f"No email template for {req.notification_type}")

        html_body = _jinja.get_template(template_file).render(**req.data)
        subject   = req.data.get("subject", default_subject)
        to_email  = req.data["user_email"]

        await email_provider.send(
            to=to_email,
            subject=subject,
            html=html_body,
        )
        logger.info(
            "Email sent. type=%s to=%s subject=%s",
            req.notification_type, to_email, subject,
        )
```

---

### 5. In-app notifications — database table

```sql
-- migration: in-app notifications
CREATE TABLE notifications (
    id               BIGSERIAL    PRIMARY KEY,
    user_id          INTEGER      NOT NULL REFERENCES users(id),
    tenant_id        TEXT         NOT NULL,
    notification_type TEXT        NOT NULL,
    title            TEXT         NOT NULL,
    body             TEXT         NOT NULL,
    data             JSONB,
    read_at          TIMESTAMPTZ,
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX idx_notifications_user_unread
  ON notifications (user_id, created_at DESC)
  WHERE read_at IS NULL;
```

```python
# services/channels/in_app_channel.py
from lib.notifications import NotificationRequest

IN_APP_TEMPLATES: dict = {
    "order.confirmed": {"title": "Order confirmed",   "body": "Your order #{order_id} is confirmed."},
    "payment.failed":  {"title": "Payment failed",    "body": "Your payment for order #{order_id} failed."},
    "security.alert":  {"title": "Security alert",    "body": "A new login was detected from {location}."},
}


class InAppChannel:
    async def send(self, req: NotificationRequest) -> None:
        tmpl  = IN_APP_TEMPLATES.get(req.notification_type)
        if not tmpl:
            return
        title = tmpl["title"]
        body  = tmpl["body"].format(**req.data)
        await db.execute(
            """
            INSERT INTO notifications (user_id, tenant_id, notification_type, title, body, data)
            VALUES (:user_id, :tenant_id, :type, :title, :body, :data)
            """,
            {"user_id": req.user_id, "tenant_id": req.tenant_id,
             "type": req.notification_type, "title": title,
             "body": body, "data": req.data},
        )
```

---

### 6. User preferences schema

```sql
CREATE TABLE notification_preferences (
    user_id           INTEGER  NOT NULL REFERENCES users(id),
    notification_type TEXT     NOT NULL,
    channel           TEXT     NOT NULL,
    enabled           BOOLEAN  NOT NULL DEFAULT TRUE,
    PRIMARY KEY (user_id, notification_type, channel)
);
```

```python
@dataclass
class UserPreferences:
    settings: dict   # {(notification_type, channel): bool}

    def is_enabled(self, notification_type, channel) -> bool:
        # Default: enabled unless explicitly opted out
        return self.settings.get((notification_type, channel), True)
```

---

### 7. Fire from business logic — always via queue

```python
# In any service — fire and forget via the background queue
from lib.notifications import NotificationRequest, NotificationType, Channel
from lib.queue import enqueue

async def place_order(user_id: int, order_id: int) -> Order:
    order = await order_repo.create(user_id, order_id)

    # Enqueue notification — never await directly in business logic
    await enqueue("notification", NotificationRequest(
        notification_type = NotificationType.ORDER_CONFIRMED,
        user_id           = user_id,
        tenant_id         = get_tenant(),
        data              = {
            "order_id":   order.id,
            "total":      order.total_formatted,
            "user_email": order.user_email,
            "user_name":  order.user_name,
        },
        channels          = [Channel.EMAIL, Channel.IN_APP],
        idempotency_key   = f"order.confirmed:{order.id}",
    ))
    return order
```

### Rules

- Never call a notification channel directly from business logic — always via the service.
- Always send notifications via the background queue — never block the request path.
- Deduplicate within a time window per notification type — what that window is depends on urgency.
- Respect opt-outs before sending — check preferences before dispatching to any channel.
- Template rendering must use autoescape — email HTML with unescaped user data is an XSS vector.
- Derive the idempotency key from the business event, not a random UUID — so retries produce the same notification, not a duplicate.
- Log every send with type, user_id, and channel — notifications are the one thing users will complain about when they go missing or arrive twice.
