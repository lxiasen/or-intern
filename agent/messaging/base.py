"""Base messaging types for OR-Intern.

Stub module — simplified from ML-Intern messaging.
"""

from typing import Protocol


class NotificationRequest:
    """Notification request data."""
    def __init__(self, title: str = "", body: str = "", **kwargs):
        self.title = title
        self.body = body
        for k, v in kwargs.items():
            setattr(self, k, v)


class NotificationResult:
    """Notification sending result."""
    def __init__(self, success: bool = True, error: str = ""):
        self.success = success
        self.error = error


class NotificationError(Exception):
    """Base notification error."""
    pass


class RetryableNotificationError(NotificationError):
    """Notification error that can be retried."""
    pass


class NotificationProvider(Protocol):
    """Protocol for notification providers."""
    async def send(self, request: NotificationRequest) -> NotificationResult:
        ...
