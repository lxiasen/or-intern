"""Telemetry module for OR-Intern.

Tracks LLM API calls, tool executions, solver operations, and session
health.  All data is kept in an in-memory store keyed by session_id and
optionally flushed to the session trajectory for downstream analysis.

Integration points
------------------
* ``agent_loop.py``          – ``record_llm_call`` (streaming + non-streaming)
* ``context_manager/manager.py`` – ``record_llm_call(kind="compaction")``
* ``effort_probe.py``        – ``record_llm_call(kind="effort_probe")``
* ``session.send_event``     – ``HeartbeatSaver.maybe_fire``
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


# ── Per-session statistics ──────────────────────────────────────────

@dataclass
class _LLMCallStats:
    total_calls: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cached_tokens: int = 0
    total_cost_usd: float = 0.0
    total_latency_ms: int = 0
    calls_by_kind: dict[str, int] = field(default_factory=dict)
    calls_by_model: dict[str, int] = field(default_factory=dict)


@dataclass
class _ToolCallStats:
    total_calls: int = 0
    total_duration_ms: int = 0
    calls_by_tool: dict[str, int] = field(default_factory=dict)
    errors_by_tool: dict[str, int] = field(default_factory=dict)


@dataclass
class _SolveStats:
    total_solves: int = 0
    successful_solves: int = 0
    failed_solves: int = 0
    total_solve_time_s: float = 0.0
    solves_by_solver: dict[str, int] = field(default_factory=dict)
    solves_by_status: dict[str, int] = field(default_factory=dict)


@dataclass
class _SessionStore:
    llm: _LLMCallStats = field(default_factory=_LLMCallStats)
    tools: _ToolCallStats = field(default_factory=_ToolCallStats)
    solves: _SolveStats = field(default_factory=_SolveStats)
    session_start: str = field(default_factory=lambda: datetime.now().isoformat())
    last_heartbeat: float | None = None


class TelemetryStore:
    """In-memory telemetry store keyed by session_id."""

    def __init__(self):
        self._sessions: dict[str, _SessionStore] = {}

    def get_session(self, session_id: str) -> _SessionStore:
        if session_id not in self._sessions:
            self._sessions[session_id] = _SessionStore()
        return self._sessions[session_id]

    def remove_session(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

    def clear(self) -> None:
        self._sessions.clear()


_store = TelemetryStore()


# ── Token extraction from LiteLLM response ─────────────────────────

def _extract_usage(response: Any) -> dict[str, int]:
    """Extract token usage from a LiteLLM completion response.

    Returns a dict with ``prompt_tokens``, ``completion_tokens``,
    ``total_tokens``, and ``cached_tokens``.
    """
    usage = {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "cached_tokens": 0,
    }

    if response is None:
        return usage

    resp_usage = getattr(response, "usage", None)
    if resp_usage is None:
        return usage

    usage["prompt_tokens"] = int(
        getattr(resp_usage, "prompt_tokens", 0) or 0
    )
    usage["completion_tokens"] = int(
        getattr(resp_usage, "completion_tokens", 0) or 0
    )
    usage["total_tokens"] = int(
        getattr(resp_usage, "total_tokens", 0) or 0
    )

    details = getattr(resp_usage, "prompt_tokens_details", None)
    if details is not None:
        usage["cached_tokens"] = int(
            getattr(details, "cached_tokens", 0) or 0
        )

    return usage


def _compute_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Compute USD cost using the cost_estimation pricing table."""
    try:
        from agent.core.cost_estimation import estimate_llm_cost

        result = estimate_llm_cost(model, input_tokens, output_tokens)
        return result.estimated_cost_usd or 0.0
    except Exception:
        return 0.0


# ── Core recording functions ────────────────────────────────────────

async def record_llm_call(
    session: Any,
    *,
    model: str = "",
    response: Any = None,
    latency_ms: int = 0,
    finish_reason: str | None = None,
    kind: str = "agent_loop",
) -> dict:
    """Record an LLM API call.

    Called from:

    * ``agent_loop._call_llm_streaming``
    * ``agent_loop._call_llm_non_streaming``
    * ``context_manager._summarize_messages``  (``kind="compaction"``)
    * ``effort_probe.probe_model``             (``kind="effort_probe"``)

    Parameters
    ----------
    session : Session
        Active session (used for event emission and store lookup).
    model : str
        Model identifier passed to LiteLLM.
    response : LiteLLM response
        The completion response object (may be ``None`` on failure).
    latency_ms : int
        Wall-clock latency in milliseconds.
    finish_reason : str or None
        LiteLLM finish reason (``stop``, ``tool_calls``, ``length``, …).
    kind : str
        Call category for breakdown: ``agent_loop``, ``compaction``,
        ``effort_probe``.

    Returns
    -------
    dict
        Token usage dict — used as ``LLMResult.usage``.
    """
    usage = _extract_usage(response)
    cost_usd = _compute_cost(
        model, usage["prompt_tokens"], usage["completion_tokens"]
    )

    usage["cost_usd"] = cost_usd
    usage["model"] = model

    if session is not None:
        session_id = getattr(session, "session_id", "unknown")
        store = _store.get_session(session_id)

        store.llm.total_calls += 1
        store.llm.total_input_tokens += usage["prompt_tokens"]
        store.llm.total_output_tokens += usage["completion_tokens"]
        store.llm.total_cached_tokens += usage["cached_tokens"]
        store.llm.total_cost_usd += cost_usd
        store.llm.total_latency_ms += latency_ms
        store.llm.calls_by_kind[kind] = store.llm.calls_by_kind.get(kind, 0) + 1
        store.llm.calls_by_model[model] = (
            store.llm.calls_by_model.get(model, 0) + 1
        )

        try:
            from agent.core.session import Event

            await session.send_event(Event(
                event_type="llm_call",
                data={
                    "model": model,
                    "prompt_tokens": usage["prompt_tokens"],
                    "completion_tokens": usage["completion_tokens"],
                    "total_tokens": usage["total_tokens"],
                    "cached_tokens": usage["cached_tokens"],
                    "cost_usd": cost_usd,
                    "latency_ms": latency_ms,
                    "finish_reason": finish_reason,
                    "kind": kind,
                },
            ))
        except Exception:
            logger.debug("Failed to send llm_call telemetry event", exc_info=True)

    return usage


async def record_tool_call(
    session: Any,
    *,
    tool_name: str = "",
    duration_ms: int = 0,
    is_error: bool = False,
    **metadata: Any,
) -> None:
    """Record a tool execution.

    Parameters
    ----------
    session : Session
        Active session.
    tool_name : str
        Name of the tool that was called.
    duration_ms : int
        Execution duration in milliseconds.
    is_error : bool
        Whether the tool returned an error.
    **metadata
        Additional context (solver name, model path, …).
    """
    if session is not None:
        session_id = getattr(session, "session_id", "unknown")
        store = _store.get_session(session_id)

        store.tools.total_calls += 1
        store.tools.total_duration_ms += duration_ms
        store.tools.calls_by_tool[tool_name] = (
            store.tools.calls_by_tool.get(tool_name, 0) + 1
        )
        if is_error:
            store.tools.errors_by_tool[tool_name] = (
                store.tools.errors_by_tool.get(tool_name, 0) + 1
            )

        try:
            from agent.core.session import Event

            await session.send_event(Event(
                event_type="tool_call_telemetry",
                data={
                    "tool_name": tool_name,
                    "duration_ms": duration_ms,
                    "is_error": is_error,
                    **metadata,
                },
            ))
        except Exception:
            logger.debug(
                "Failed to send tool_call telemetry event", exc_info=True
            )


async def record_solve(
    session: Any,
    *,
    solver: str = "",
    status: str = "",
    objective: float | None = None,
    gap: float | None = None,
    elapsed_s: float = 0.0,
    nodes: int | None = None,
    iterations: int | None = None,
) -> None:
    """Record a solver operation.

    Specifically designed for OR-Intern's solve workflow.  Tracks solver
    performance metrics (gap, bound convergence, solve time) that are
    critical for regression testing and solver selection tuning.

    Parameters
    ----------
    session : Session
        Active session.
    solver : str
        Solver name (highs, scip, gurobi, …).
    status : str
        Termination status (optimal, infeasible, time_limit, …).
    objective : float or None
        Objective function value.
    gap : float or None
        Optimality gap (0.0 for proven optimal).
    elapsed_s : float
        Wall-clock solve time in seconds.
    nodes : int or None
        Branch-and-bound nodes explored.
    iterations : int or None
        Simplex / interior-point iterations.
    """
    if session is not None:
        session_id = getattr(session, "session_id", "unknown")
        store = _store.get_session(session_id)

        store.solves.total_solves += 1
        store.solves.total_solve_time_s += elapsed_s
        store.solves.solves_by_solver[solver] = (
            store.solves.solves_by_solver.get(solver, 0) + 1
        )

        is_success = status.lower() in (
            "optimal", "feasible", "locallyoptimal",
        )
        if is_success:
            store.solves.successful_solves += 1
        else:
            store.solves.failed_solves += 1
        store.solves.solves_by_status[status] = (
            store.solves.solves_by_status.get(status, 0) + 1
        )

        try:
            from agent.core.session import Event

            await session.send_event(Event(
                event_type="solve",
                data={
                    "solver": solver,
                    "status": status,
                    "objective": objective,
                    "gap": gap,
                    "elapsed_s": elapsed_s,
                    "nodes": nodes,
                    "iterations": iterations,
                },
            ))
        except Exception:
            logger.debug(
                "Failed to send solve telemetry event", exc_info=True
            )


async def record_job_submission(*args: Any, **kwargs: Any) -> None:
    """Record a job submission (no-op — OR-Intern has no remote job system)."""
    pass


async def record_heartbeat(session: Any) -> None:
    """Record a heartbeat event.

    Parameters
    ----------
    session : Session
        Active session.
    """
    if session is not None:
        session_id = getattr(session, "session_id", "unknown")
        store = _store.get_session(session_id)
        store.last_heartbeat = time.monotonic()

        try:
            from agent.core.session import Event

            await session.send_event(Event(
                event_type="heartbeat",
                data={
                    "timestamp": datetime.now().isoformat(),
                    "status": "alive",
                },
            ))
        except Exception:
            logger.debug(
                "Failed to send heartbeat telemetry event", exc_info=True
            )


# ── Session summary ─────────────────────────────────────────────────

def get_session_summary(session: Any) -> dict:
    """Return aggregated telemetry statistics for a session.

    This is intended for end-of-session reporting: total cost, token
    usage, tool usage, and solve success rates.

    Parameters
    ----------
    session : Session
        Active session.

    Returns
    -------
    dict
        Aggregated statistics.
    """
    if session is None:
        return {}

    session_id = getattr(session, "session_id", "unknown")
    store = _store.get_session(session_id)

    avg_latency_ms = 0
    if store.llm.total_calls > 0:
        avg_latency_ms = store.llm.total_latency_ms // store.llm.total_calls

    solve_success_rate = 0.0
    if store.solves.total_solves > 0:
        solve_success_rate = (
            store.solves.successful_solves / store.solves.total_solves
        )

    return {
        "session_id": session_id,
        "llm": {
            "total_calls": store.llm.total_calls,
            "total_input_tokens": store.llm.total_input_tokens,
            "total_output_tokens": store.llm.total_output_tokens,
            "total_cached_tokens": store.llm.total_cached_tokens,
            "total_cost_usd": round(store.llm.total_cost_usd, 6),
            "avg_latency_ms": avg_latency_ms,
            "calls_by_kind": dict(store.llm.calls_by_kind),
            "calls_by_model": dict(store.llm.calls_by_model),
        },
        "tools": {
            "total_calls": store.tools.total_calls,
            "total_duration_ms": store.tools.total_duration_ms,
            "calls_by_tool": dict(store.tools.calls_by_tool),
            "errors_by_tool": dict(store.tools.errors_by_tool),
        },
        "solves": {
            "total_solves": store.solves.total_solves,
            "successful_solves": store.solves.successful_solves,
            "failed_solves": store.solves.failed_solves,
            "success_rate": round(solve_success_rate, 4),
            "total_solve_time_s": round(store.solves.total_solve_time_s, 2),
            "solves_by_solver": dict(store.solves.solves_by_solver),
            "solves_by_status": dict(store.solves.solves_by_status),
        },
    }


def reset_session(session: Any) -> None:
    """Remove all telemetry data for a session (e.g. on /new)."""
    if session is not None:
        session_id = getattr(session, "session_id", "unknown")
        _store.remove_session(session_id)


# ── HeartbeatSaver ──────────────────────────────────────────────────

_HEARTBEAT_INTERVAL_S: int = 60


class HeartbeatSaver:
    """Periodic session persistence during long-running operations.

    ``maybe_fire`` is called synchronously from ``Session.send_event``
    on every event.  It checks whether enough wall-clock time has passed
    since the last save and, if so, schedules an async
    ``save_and_upload_detached`` task on the running event loop.
    """

    @staticmethod
    def _resolve_interval(session: Any) -> int:
        """Read heartbeat interval from config, fall back to default."""
        try:
            cfg = getattr(session, "config", None)
            if cfg is not None:
                return int(getattr(cfg, "heartbeat_interval_s", _HEARTBEAT_INTERVAL_S))
        except Exception:
            pass
        return _HEARTBEAT_INTERVAL_S

    @classmethod
    def maybe_fire(cls, session: Any) -> None:
        """Conditionally trigger a background session save.

        Called synchronously from ``Session.send_event``.  If the elapsed
        time since the last heartbeat exceeds the configured interval, a
        fire-and-forget task is created on the current event loop.
        """
        if session is None:
            return

        now = time.monotonic()
        last_ts = getattr(session, "_last_heartbeat_ts", None)
        interval = cls._resolve_interval(session)

        if last_ts is not None and (now - last_ts) < interval:
            return

        session._last_heartbeat_ts = now

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(
                cls._save(session),
                name=f"telemetry-heartbeat-{getattr(session, 'session_id', '?')}",
            )
        except RuntimeError:
            logger.debug("HeartbeatSaver: no running event loop, skipping")

    @staticmethod
    async def _save(session: Any) -> None:
        """Persist session state (fire-and-forget)."""
        try:
            save_fn = getattr(session, "save_and_upload_detached", None)
            if save_fn is not None:
                await save_fn()
        except Exception:
            logger.debug("HeartbeatSaver: save failed", exc_info=True)

    async def save(self, *args: Any, **kwargs: Any) -> None:
        """Instance-level save — delegates to the static helper."""
        pass
