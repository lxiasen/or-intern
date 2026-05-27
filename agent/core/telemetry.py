"""Stub telemetry module for OR-Intern.

ML-Intern uses telemetry for tracking LLM calls and job submissions to HF.
OR-Intern replaces this with a no-op stub.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def record_llm_call(*args: Any, **kwargs: Any) -> dict:
    """No-op stub for LLM call recording."""
    return {}


async def record_tool_call(*args: Any, **kwargs: Any) -> None:
    """No-op stub for tool call recording."""
    pass


async def record_job_submission(*args: Any, **kwargs: Any) -> None:
    """No-op stub for job submission recording."""
    pass


async def record_heartbeat(*args: Any, **kwargs: Any) -> None:
    """No-op stub for heartbeat recording."""
    pass


class HeartbeatSaver:
    """No-op stub for heartbeat saving."""
    def __init__(self, *args, **kwargs):
        pass

    async def save(self, *args, **kwargs):
        pass

    @classmethod
    def maybe_fire(cls, *args, **kwargs):
        """No-op stub for maybe_fire."""
        pass
