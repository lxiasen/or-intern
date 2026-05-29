"""Unit tests for context_manager."""

import pytest
from litellm import Message


class TestContextManager:
    """Test context manager basic operations."""

    def test_init(self):
        from agent.context_manager.manager import ContextManager
        cm = ContextManager()
        assert cm is not None

    def test_init_with_params(self):
        from agent.context_manager.manager import ContextManager
        cm = ContextManager(
            model_max_tokens=100000,
            compact_size=0.1,
            untouched_messages=5,
        )
        assert cm.model_max_tokens == 100000

    def test_add_message(self):
        from agent.context_manager.manager import ContextManager
        cm = ContextManager()
        msg = Message(role="user", content="hello")
        cm.add_message(msg)
        assert len(cm.get_messages()) > 0

    def test_get_messages_returns_list(self):
        from agent.context_manager.manager import ContextManager
        cm = ContextManager()
        messages = cm.get_messages()
        assert isinstance(messages, list)

    def test_token_count_tracking(self):
        from agent.context_manager.manager import ContextManager
        cm = ContextManager()
        msg = Message(role="user", content="hello world")
        cm.add_message(msg, token_count=10)
        assert cm.running_context_usage == 10


class TestContextCompression:
    """Test context compression behavior."""

    def test_has_compact_prompt(self):
        from agent.context_manager.manager import ContextManager
        cm = ContextManager()
        assert hasattr(cm, 'compact_prompt')
        assert len(cm.compact_prompt) > 0

    def test_messages_preserved_after_add(self):
        from agent.context_manager.manager import ContextManager
        cm = ContextManager()
        msg1 = Message(role="user", content="first")
        msg2 = Message(role="assistant", content="second")
        cm.add_message(msg1)
        cm.add_message(msg2)
        messages = cm.get_messages()
        assert len(messages) >= 2

    def test_system_message_handling(self):
        from agent.context_manager.manager import ContextManager
        cm = ContextManager()
        system_msg = Message(role="system", content="You are OR-Intern")
        cm.add_message(system_msg)
        messages = cm.get_messages()
        assert any(m.role == "system" for m in messages)

    def test_compact_size_calculation(self):
        from agent.context_manager.manager import ContextManager
        cm = ContextManager(model_max_tokens=100000, compact_size=0.1)
        assert cm.compact_size == 10000


class TestORSpecificPrompts:
    """Test OR-specific compaction prompts."""

    def test_or_compact_prompt_exists(self):
        from agent.context_manager.manager import _COMPACT_PROMPT_OR
        assert "optimization" in _COMPACT_PROMPT_OR.lower()

    def test_solve_log_compact_prompt_exists(self):
        from agent.context_manager.manager import _SOLVE_LOG_COMPACT_PROMPT
        assert "solver" in _SOLVE_LOG_COMPACT_PROMPT.lower()
