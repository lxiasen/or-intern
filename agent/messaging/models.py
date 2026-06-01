"""Runtime data models for the messaging subsystem.

Configuration types (MessagingConfig, DestinationConfig, etc.) are
defined in ``agent.config`` and re-exported here for convenience.
"""

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from agent.config import (
    SUPPORTED_AUTO_EVENT_TYPES,
    DestinationConfig,
    MessagingConfig,
    SlackDestinationConfig,
)


class NotificationRequest(BaseModel):
    destination: str
    title: str | None = None
    message: str
    severity: Literal["info", "success", "warning", "error"] = "info"
    metadata: dict[str, str] = Field(default_factory=dict)
    event_type: str | None = None

    @field_validator("destination", "message")
    @classmethod
    def _require_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be empty")
        return value

    @field_validator("title")
    @classmethod
    def _normalize_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class NotificationResult(BaseModel):
    destination: str
    ok: bool
    provider: str
    error: str | None = None
    external_id: str | None = None


__all__ = [
    "SUPPORTED_AUTO_EVENT_TYPES",
    "DestinationConfig",
    "MessagingConfig",
    "NotificationRequest",
    "NotificationResult",
    "SlackDestinationConfig",
]
