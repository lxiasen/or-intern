"""Stub prompt caching module for OR-Intern.

ML-Intern uses Anthropic prompt caching to reduce costs.
OR-Intern replaces this with a pass-through stub.
"""

from typing import Any


def with_prompt_caching(messages: list, tools: Any, model: str) -> tuple[list, Any]:
    """No-op stub: pass messages and tools through unchanged."""
    return messages, tools
