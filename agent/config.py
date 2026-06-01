"""OR-Intern configuration management.

Loads configuration from YAML file with environment variable substitution.

Config file search order:
  1. OR_INTERN_CONFIG environment variable (explicit path)
  2. ./config.yaml (current working directory)
  3. ~/.config/or-intern/config.yaml (user config directory)

Environment variables take precedence over config file values for
specific override keys (OR_INTERN_MODEL, OR_INTERN_MAX_ITERATIONS, OR_INTERN_YOLO).
"""

import os
import re
from pathlib import Path
from typing import Annotated, Any, Literal, Optional

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator


# ── Config file paths ──────────────────────────────────────────────
_USER_CONFIG_DIR = Path.home() / ".config" / "or-intern"


def _find_config_file() -> Path | None:
    """Find the config file using the search order."""
    # 1. Explicit path from environment variable
    if env_path := os.getenv("OR_INTERN_CONFIG"):
        p = Path(env_path)
        if p.exists():
            return p

    # 2. Current working directory
    cwd_config = Path.cwd() / "config.yaml"
    if cwd_config.exists():
        return cwd_config

    # 3. User config directory
    user_config = _USER_CONFIG_DIR / "config.yaml"
    if user_config.exists():
        return user_config

    return None


def _resolve_env_vars(value: str) -> str:
    """Resolve $VAR and ${VAR} patterns in a string value.

    Supports:
      - $VAR: Simple variable reference
      - ${VAR}: Braced variable reference
      - ${VAR:-default}: Variable with default value if unset/empty
    """
    def _replace(match: re.Match) -> str:
        full_match = match.group(0)

        # ${VAR:-default} pattern
        if ":-" in full_match:
            var, default = full_match[2:-1].split(":-", 1)
            return os.getenv(var.strip(), default.strip())

        # ${VAR} pattern
        if full_match.startswith("${"):
            var = full_match[2:-1]
            return os.getenv(var.strip(), "")

        # $VAR pattern
        var = full_match[1:]
        return os.getenv(var, "")

    pattern = r'(?<!\$)(\$(?:[A-Za-z_][A-Za-z0-9_]*|\{[A-Za-z_][A-Za-z0-9_]*(?::-[^}]*)?\}))'
    return re.sub(pattern, _replace, value)


def _resolve_env_vars_recursive(obj: Any) -> Any:
    """Recursively resolve environment variables in dicts, lists, and strings."""
    if isinstance(obj, dict):
        return {k: _resolve_env_vars_recursive(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_resolve_env_vars_recursive(v) for v in obj]
    elif isinstance(obj, str):
        return _resolve_env_vars(obj)
    return obj


def load_config() -> dict:
    """Load configuration from YAML file.

    Returns:
        Configuration dictionary with environment variables resolved.
    """
    config_path = _find_config_file()

    if config_path is None:
        return {}

    config_text = config_path.read_text(encoding="utf-8")
    config_data = yaml.safe_load(config_text) or {}
    config_data = _resolve_env_vars_recursive(config_data)

    return config_data


# ── Nested config models ───────────────────────────────────────────


class ModelEntry(BaseModel):
    """A single model entry in the models list."""

    name: str = "openai/qwen3.6-plus"
    display_name: str = ""
    api_key: Optional[str] = ""
    api_base: Optional[str] = ""
    reasoning_effort: Optional[str] = None
    max_iterations: int = 500


class SolverConfig(BaseModel):
    """Solver configuration."""

    default: str = "highs"
    timeout: int = 3600


class SessionConfig(BaseModel):
    """Session persistence configuration."""

    save: bool = True
    auto_save_interval: int = 1
    log_dir: str = "session_logs"
    heartbeat_interval: int = 60


class ApprovalConfig(BaseModel):
    """Approval policy configuration."""

    yolo_mode: bool = False
    cost_cap_usd: float = 1.0
    confirm_expensive: bool = True


# ── Messaging config types ─────────────────────────────────────────

_DESTINATION_NAME_CHARS = set("abcdefghijklmnopqrstuvwxyz0123456789._-")
SUPPORTED_AUTO_EVENT_TYPES = {"approval_required", "error", "turn_complete"}


class SlackDestinationConfig(BaseModel):
    """Configuration for a Slack notification destination."""

    provider: Literal["slack"] = "slack"
    token: str
    channel: str
    allow_agent_tool: bool = False
    allow_auto_events: bool = False
    username: str | None = None
    icon_emoji: str | None = None

    @field_validator("token", "channel")
    @classmethod
    def _require_non_empty(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be empty")
        return value


DestinationConfig = Annotated[SlackDestinationConfig, Field(discriminator="provider")]


class MessagingConfig(BaseModel):
    """Configuration for the notification messaging subsystem.

    Controls whether and how the agent sends notifications to external
    channels (Slack, etc.) during execution.
    """

    enabled: bool = False
    auto_event_types: list[str] = Field(
        default_factory=lambda: ["approval_required", "error", "turn_complete"]
    )
    destinations: dict[str, DestinationConfig] = Field(default_factory=dict)

    @field_validator("destinations")
    @classmethod
    def _validate_destination_names(
        cls, destinations: dict[str, DestinationConfig]
    ) -> dict[str, DestinationConfig]:
        for name in destinations:
            if not name or any(char not in _DESTINATION_NAME_CHARS for char in name):
                raise ValueError(
                    "destination names must use lowercase letters, digits, '.', '_' or '-'"
                )
        return destinations

    @field_validator("auto_event_types")
    @classmethod
    def _validate_auto_event_types(cls, event_types: list[str]) -> list[str]:
        if not event_types:
            return []
        normalized: list[str] = []
        seen: set[str] = set()
        for event_type in event_types:
            if event_type not in SUPPORTED_AUTO_EVENT_TYPES:
                raise ValueError(f"unsupported auto event type '{event_type}'")
            if event_type not in seen:
                normalized.append(event_type)
                seen.add(event_type)
        return normalized

    @model_validator(mode="after")
    def _require_destinations_when_enabled(self) -> "MessagingConfig":
        if self.enabled and not self.destinations:
            raise ValueError("messaging.enabled requires at least one destination")
        return self

    def get_destination(self, name: str) -> DestinationConfig | None:
        return self.destinations.get(name)

    def can_agent_tool_send(self, name: str) -> bool:
        destination = self.get_destination(name)
        return bool(destination and destination.allow_agent_tool)

    def can_auto_send(self, name: str) -> bool:
        destination = self.get_destination(name)
        return bool(destination and destination.allow_auto_events)

    def default_auto_destinations(self) -> list[str]:
        if not self.enabled:
            return []
        return [name for name in self.destinations if self.can_auto_send(name)]


# ── Root config ────────────────────────────────────────────────────


class Config(BaseModel):
    """OR-Intern runtime configuration."""

    models: list[ModelEntry] = Field(default_factory=lambda: [ModelEntry()])
    active_model_index: int = 0
    solver: SolverConfig = Field(default_factory=SolverConfig)
    session: SessionConfig = Field(default_factory=SessionConfig)
    approval: ApprovalConfig = Field(default_factory=ApprovalConfig)
    tool_runtime: str = "local"
    mcp_servers: dict = Field(default_factory=dict)
    messaging: MessagingConfig = Field(default_factory=MessagingConfig)

    @property
    def current_model(self) -> ModelEntry:
        """Return the currently active model entry."""
        if not self.models:
            return ModelEntry()
        idx = max(0, min(self.active_model_index, len(self.models) - 1))
        return self.models[idx]

    @classmethod
    def from_config_file(cls) -> "Config":
        """Load Config from config.yaml."""
        data = load_config()
        return cls(**data)

    @classmethod
    def from_env(cls) -> "Config":
        """Load Config from config.yaml (with $VAR resolution from environment)."""
        return cls.from_config_file()
