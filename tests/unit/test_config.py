"""Tests for configuration loading."""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from agent.config import (
    Config,
    MessagingConfig,
    SlackDestinationConfig,
    _find_config_file,
    _resolve_env_vars,
    load_config,
)


class TestEnvVarResolution:
    """Test environment variable substitution."""

    def test_simple_var(self):
        """Test $VAR syntax."""
        with patch.dict(os.environ, {"MY_KEY": "secret"}):
            assert _resolve_env_vars("$MY_KEY") == "secret"

    def test_braced_var(self):
        """Test ${VAR} syntax."""
        with patch.dict(os.environ, {"MY_KEY": "secret"}):
            assert _resolve_env_vars("${MY_KEY}") == "secret"

    def test_var_with_default(self):
        """Test ${VAR:-default} syntax."""
        with patch.dict(os.environ, {}, clear=True):
            assert _resolve_env_vars("${MY_KEY:-fallback}") == "fallback"

        with patch.dict(os.environ, {"MY_KEY": "actual"}):
            assert _resolve_env_vars("${MY_KEY:-fallback}") == "actual"

    def test_var_in_string(self):
        """Test variable embedded in string."""
        with patch.dict(os.environ, {"API_KEY": "abc123"}):
            assert _resolve_env_vars("Bearer $API_KEY") == "Bearer abc123"

    def test_multiple_vars(self):
        """Test multiple variables in one string."""
        with patch.dict(os.environ, {"HOST": "localhost", "PORT": "8080"}):
            assert _resolve_env_vars("http://$HOST:$PORT") == "http://localhost:8080"

    def test_no_var(self):
        """Test string without variables."""
        assert _resolve_env_vars("no variables here") == "no variables here"

    def test_url_not_resolved(self):
        """Test that URLs with $ in path are not resolved."""
        url = "https://example.com/path"
        assert _resolve_env_vars(url) == url

    def test_unset_var_empty(self):
        """Test that unset variables resolve to empty string."""
        with patch.dict(os.environ, {}, clear=True):
            assert _resolve_env_vars("$UNSET_VAR") == ""

    def test_empty_string(self):
        """Test empty string input."""
        assert _resolve_env_vars("") == ""


class TestConfigFileSearch:
    """Test config file search order."""

    def test_explicit_path(self, tmp_path):
        """Test OR_INTERN_CONFIG environment variable."""
        config_file = tmp_path / "custom.yaml"
        config_file.write_text("models:\n  - name: test")

        with patch.dict(os.environ, {"OR_INTERN_CONFIG": str(config_file)}):
            result = _find_config_file()
            assert result == config_file

    def test_explicit_path_not_found(self, tmp_path):
        """Test OR_INTERN_CONFIG with non-existent path."""
        with patch.dict(os.environ, {"OR_INTERN_CONFIG": str(tmp_path / "missing.yaml")}):
            result = _find_config_file()

    def test_cwd_config(self, tmp_path, monkeypatch):
        """Test config.yaml in current working directory."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("models:\n  - name: test")

        monkeypatch.chdir(tmp_path)
        with patch.dict(os.environ, {}, clear=True):
            result = _find_config_file()
            assert result == config_file


class TestYAMLLoading:
    """Test YAML configuration loading."""

    def test_load_yaml(self, tmp_path, monkeypatch):
        """Test loading a YAML config file."""
        config_data = {
            "models": [{"name": "openai/gpt-4", "max_iterations": 1000}],
            "solver": {"default": "scip"},
        }
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump(config_data))

        monkeypatch.chdir(tmp_path)
        with patch.dict(os.environ, {}, clear=True):
            result = load_config()
            assert result["models"][0]["name"] == "openai/gpt-4"
            assert result["models"][0]["max_iterations"] == 1000
            assert result["solver"]["default"] == "scip"

    def test_load_yaml_with_env_vars(self, tmp_path, monkeypatch):
        """Test YAML with environment variable references."""
        config_text = """
models:
  - name: openai/gpt-4
messaging:
  enabled: true
  destinations:
    slack:
      provider: slack
      token: $SLACK_TOKEN
      channel: C123456
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(config_text)

        monkeypatch.chdir(tmp_path)
        with patch.dict(os.environ, {"SLACK_TOKEN": "xoxb-test"}):
            result = load_config()
            assert result["messaging"]["destinations"]["slack"]["token"] == "xoxb-test"


class TestConfigModel:
    """Test Config Pydantic model."""

    def test_default_values(self):
        """Test Config with default values."""
        config = Config()
        assert config.current_model.name == "openai/qwen3.6-plus"
        assert config.current_model.max_iterations == 500
        assert config.solver.default == "highs"
        assert config.messaging.enabled is False

    def test_from_dict(self):
        """Test Config from dictionary."""
        data = {
            "models": [{"name": "openai/gpt-4", "max_iterations": 1000}],
            "messaging": {"enabled": False},
        }
        config = Config(**data)
        assert config.current_model.name == "openai/gpt-4"
        assert config.current_model.max_iterations == 1000

    def test_env_overrides(self, tmp_path, monkeypatch):
        """Test environment variable resolution via YAML $VAR syntax."""
        config_data = {
            "models": [{
                "name": "${OR_INTERN_MODEL:-openai/gpt-4}",
                "max_iterations": "${OR_INTERN_MAX_ITERATIONS:-1000}",
            }],
            "approval": {
                "yolo_mode": "${OR_INTERN_YOLO:-false}",
            },
        }
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump(config_data))

        monkeypatch.chdir(tmp_path)
        with patch.dict(
            os.environ,
            {
                "OR_INTERN_MODEL": "anthropic/claude-3",
                "OR_INTERN_MAX_ITERATIONS": "2000",
                "OR_INTERN_YOLO": "true",
            },
        ):
            config = Config.from_env()
            assert config.current_model.name == "anthropic/claude-3"
            assert config.current_model.max_iterations == 2000
            assert config.approval.yolo_mode is True

    def test_env_defaults(self, tmp_path, monkeypatch):
        """Test that YAML defaults work when env vars are not set."""
        config_data = {
            "models": [{
                "name": "${OR_INTERN_MODEL:-openai/gpt-4}",
                "max_iterations": "${OR_INTERN_MAX_ITERATIONS:-1000}",
            }],
        }
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump(config_data))

        monkeypatch.chdir(tmp_path)
        env = {k: v for k, v in os.environ.items()
               if k not in ("OR_INTERN_MODEL", "OR_INTERN_MAX_ITERATIONS", "OR_INTERN_YOLO")}
        with patch.dict(os.environ, env, clear=True):
            config = Config.from_config_file()
            assert config.current_model.name == "openai/gpt-4"
            assert config.current_model.max_iterations == 1000


class TestMessagingConfig:
    """Test MessagingConfig validation."""

    def test_default_disabled(self):
        """Test messaging is disabled by default."""
        config = MessagingConfig()
        assert config.enabled is False
        assert config.auto_event_types == ["approval_required", "error", "turn_complete"]

    def test_enabled_requires_destinations(self):
        """Test that enabling messaging requires at least one destination."""
        with pytest.raises(ValueError, match="requires at least one destination"):
            MessagingConfig(enabled=True, destinations={})

    def test_valid_destination(self):
        """Test valid Slack destination config."""
        dest = SlackDestinationConfig(
            token="xoxb-test",
            channel="C123456",
            allow_agent_tool=True,
            allow_auto_events=True,
        )
        assert dest.provider == "slack"
        assert dest.token == "xoxb-test"

    def test_invalid_destination_name(self):
        """Test that invalid destination names are rejected."""
        with pytest.raises(ValueError, match="destination names must use"):
            MessagingConfig(
                enabled=True,
                destinations={"Invalid Name!": {"provider": "slack", "token": "x", "channel": "C1"}},
            )

    def test_invalid_auto_event_type(self):
        """Test that invalid auto event types are rejected."""
        with pytest.raises(ValueError, match="unsupported auto event type"):
            MessagingConfig(auto_event_types=["invalid_event"])

    def test_can_auto_send(self):
        """Test can_auto_send method."""
        config = MessagingConfig(
            enabled=True,
            destinations={
                "slack": {
                    "provider": "slack",
                    "token": "xoxb-test",
                    "channel": "C123456",
                    "allow_auto_events": True,
                }
            },
        )
        assert config.can_auto_send("slack") is True
        assert config.can_auto_send("nonexistent") is False


class TestConfigIntegration:
    """Integration tests for config loading."""

    def test_full_config_with_messaging(self, tmp_path, monkeypatch):
        """Test loading a complete config with messaging enabled."""
        config_text = """
models:
  - name: openai/gpt-4
    max_iterations: 1000
solver:
  default: scip
messaging:
  enabled: true
  auto_event_types:
    - approval_required
    - error
  destinations:
    slack_ops:
      provider: slack
      token: $SLACK_BOT_TOKEN
      channel: C0123456789
      allow_agent_tool: true
      allow_auto_events: true
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(config_text)

        monkeypatch.chdir(tmp_path)
        with patch.dict(os.environ, {"SLACK_BOT_TOKEN": "xoxb-secret-token"}):
            config = Config.from_config_file()
            assert config.current_model.name == "openai/gpt-4"
            assert config.current_model.max_iterations == 1000
            assert config.solver.default == "scip"
            assert config.messaging.enabled is True
            assert len(config.messaging.auto_event_types) == 2
            assert config.messaging.can_auto_send("slack_ops") is True
            dest = config.messaging.get_destination("slack_ops")
            assert dest.token == "xoxb-secret-token"
