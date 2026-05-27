"""OR-Intern Slack integration stub.

Simplified from ML-Intern — provides a no-op Slack provider for Phase 0.
"""

import logging
from .base import NotificationProvider, NotificationRequest, NotificationResult

logger = logging.getLogger(__name__)


class SlackProvider(NotificationProvider):
    """No-op Slack provider for OR-Intern Phase 0."""

    def __init__(self, bot_token: str = "", channel_id: str = ""):
        self.bot_token = bot_token
        self.channel_id = channel_id

    async def send(self, request: NotificationRequest) -> NotificationResult:
        logger.debug("Slack notification suppressed (no-op stub)")
        return NotificationResult(success=True)
