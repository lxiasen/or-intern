"""Slack notification provider for OR-Intern.

Currently a no-op stub — logs the notification but does not call the
Slack API.  When Slack integration is needed, replace the body of
``send`` with an actual ``chat.postMessage`` call via ``client``.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from agent.messaging.models import NotificationResult

if TYPE_CHECKING:
    import httpx
    from agent.config import DestinationConfig
    from agent.messaging.models import NotificationRequest

logger = logging.getLogger(__name__)


class SlackProvider:
    """Slack notification provider.

    Implements the ``NotificationProvider`` protocol defined in
    ``agent.messaging.base``.
    """

    provider_name: str = "slack"

    async def send(
        self,
        client: httpx.AsyncClient,
        destination_name: str,
        destination: DestinationConfig,
        request: NotificationRequest,
    ) -> NotificationResult:
        logger.debug(
            "Slack notification suppressed (no-op): dest=%s title=%s",
            destination_name,
            request.title,
        )
        return NotificationResult(
            destination=destination_name,
            ok=True,
            provider=self.provider_name,
        )
