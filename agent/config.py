"""OR-Intern configuration management.

Simplified from ML-Intern — no Hugging Face specific fields.
Loads from JSON config file with environment variable interpolation.
"""

import json
import os
import re
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field


# ── Config file paths ──
_PACKAGE_CONFIG = Path(__file__).parent.parent / "configs" / "cli_config.json"
_USER_CONFIG_DIR = Path.home() / ".config" / "or-intern"
_USER_CONFIG = _USER_CONFIG_DIR / "cli_config.json"


def _resolve_env_vars(value: str) -> str:
    """Resolve ${VAR_NAME} and ${VAR_NAME:-default} patterns in string values."""
    def _replace(match):
        expr = match.group(1)
        if ":-" in expr:
            var, default = expr.split(":-", 1)
            return os.getenv(var.strip(), default.strip())
        return os.getenv(expr.strip(), "")
    return re.sub(r'\$\{([^}]+)\}', _replace, value)


def _resolve_env_vars_recursive(obj):
    """Recursively resolve env vars in dicts and lists."""
    if isinstance(obj, dict):
        return {k: _resolve_env_vars_recursive(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_resolve_env_vars_recursive(v) for v in obj]
    elif isinstance(obj, str):
        return _resolve_env_vars(obj)
    return obj


def load_config() -> dict:
    """Load configuration from file, with user override support."""
    config_data = {}

    # 1. Load packaged default
    if _PACKAGE_CONFIG.exists():
        with open(_PACKAGE_CONFIG) as f:
            config_data = json.load(f)

    # 2. Override with user config
    if _USER_CONFIG.exists():
        with open(_USER_CONFIG) as f:
            user_data = json.load(f)
            _deep_merge(config_data, user_data)

    # 3. Resolve env vars
    config_data = _resolve_env_vars_recursive(config_data)

    return config_data


def _deep_merge(base: dict, override: dict):
    """Deep merge override into base dict."""
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value


# ── Pydantic config models ──

class MessagingConfig(BaseModel):
    """Notification messaging configuration."""
    enabled: bool = False
    slack_bot_token: Optional[str] = None
    slack_channel_id: Optional[str] = None


class Config(BaseModel):
    """OR-Intern runtime configuration."""

    # ── Model ──
    model_name: str = "anthropic/claude-sonnet-4-6"
    api_base: Optional[str] = None  # Custom API base URL for OpenAI-compatible endpoints
    reasoning_effort: Optional[str] = "high"
    max_iterations: int = 500

    # ── MCP Servers (optional) ──
    mcp_servers: dict = Field(default_factory=dict)

    # ── Session ──
    save_sessions: bool = True
    auto_save_interval: int = 1  # Save every N turns
    heartbeat_interval_s: int = 60
    session_log_dir: str = "session_logs"

    # ── Tool Runtime ──
    tool_runtime: str = "local"  # "local" or "sandbox"

    # ── Approval ──
    yolo_mode: bool = False
    auto_approval_cost_cap_usd: float = 1.0
    confirm_expensive_solves: bool = True

    # ── Messaging ──
    messaging: MessagingConfig = Field(default_factory=MessagingConfig)

    # ── Solver (OR-specific) ──
    default_solver: str = "highs"  # Default open-source solver
    solver_timeout: int = 3600     # Default solver timeout (seconds)

    @classmethod
    def from_config_file(cls) -> "Config":
        """Load Config from config file."""
        data = load_config()
        return cls(**data)

    @classmethod
    def from_env(cls) -> "Config":
        """Load Config from file, with environment overrides."""
        config = cls.from_config_file()

        # Override with environment variables
        if os.getenv("OR_INTERN_MODEL"):
            config.model_name = os.getenv("OR_INTERN_MODEL")
        if os.getenv("OR_INTERN_MAX_ITERATIONS"):
            config.max_iterations = int(os.getenv("OR_INTERN_MAX_ITERATIONS"))
        if os.getenv("OR_INTERN_YOLO"):
            config.yolo_mode = os.getenv("OR_INTERN_YOLO").lower() in ("1", "true", "yes")

        return config
