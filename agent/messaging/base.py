"""Base messaging types for OR-Intern.

Defines the provider protocol and error hierarchy.
Concrete data models (NotificationRequest, NotificationResult) live in
``agent.messaging.models`` to avoid duplication.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    import httpx
    from agent.config import DestinationConfig
    from agent.messaging.models import (
        NotificationRequest,
        NotificationResult,
    )


class NotificationError(Exception):
    """Base notification error — non-retryable."""


class RetryableNotificationError(NotificationError):
    """Notification error that can be retried (transient failure)."""


class NotificationProvider(Protocol):
    """Protocol that all notification providers must implement.

    ``send`` is called by ``NotificationGateway._send_with_retries`` with
    four positional arguments beyond ``self``:

    * ``client`` — a shared ``httpx.AsyncClient`` for making HTTP requests
    * ``destination_name`` — the logical name of the destination (e.g. "slack.ops")
    * ``destination`` — the typed destination config (e.g. ``SlackDestinationConfig``)
    * ``request`` — the ``NotificationRequest`` to deliver

    Providers should raise ``RetryableNotificationError`` for transient
    failures and ``NotificationError`` for permanent ones.
    """

    provider_name: str

    async def send(
        self,
        client: httpx.AsyncClient,
        destination_name: str,
        destination: DestinationConfig,
        request: NotificationRequest,
    ) -> NotificationResult: ...
