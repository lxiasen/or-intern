"""Unit tests for agent.core.telemetry."""

import asyncio
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import AsyncMock

import pytest

from agent.core.telemetry import (
    HeartbeatSaver,
    TelemetryStore,
    _compute_cost,
    _extract_usage,
    _store,
    get_session_summary,
    record_llm_call,
    record_solve,
    record_tool_call,
    reset_session,
)


@dataclass
class _FakeUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    prompt_tokens_details: Any = None


@dataclass
class _FakeResponse:
    usage: _FakeUsage | None = None


@dataclass
class _FakeSession:
    session_id: str = "test-session-1"
    events: list = field(default_factory=list)

    async def send_event(self, event):
        self.events.append(event)


class TestExtractUsage:
    def test_none_response(self):
        usage = _extract_usage(None)
        assert usage["prompt_tokens"] == 0
        assert usage["completion_tokens"] == 0
        assert usage["total_tokens"] == 0

    def test_no_usage_attr(self):
        usage = _extract_usage(object())
        assert usage["prompt_tokens"] == 0

    def test_valid_usage(self):
        resp = _FakeResponse(usage=_FakeUsage(
            prompt_tokens=100, completion_tokens=50, total_tokens=150
        ))
        usage = _extract_usage(resp)
        assert usage["prompt_tokens"] == 100
        assert usage["completion_tokens"] == 50
        assert usage["total_tokens"] == 150

    def test_none_values_treated_as_zero(self):
        resp = _FakeResponse(usage=_FakeUsage(
            prompt_tokens=None, completion_tokens=None, total_tokens=None
        ))
        usage = _extract_usage(resp)
        assert usage["prompt_tokens"] == 0


class TestComputeCost:
    def test_known_model(self):
        cost = _compute_cost("gpt-4o", 1_000_000, 1_000_000)
        assert cost > 0

    def test_unknown_model_uses_default(self):
        cost = _compute_cost("unknown-model-xyz", 1000, 1000)
        assert cost > 0

    def test_zero_tokens(self):
        cost = _compute_cost("gpt-4o", 0, 0)
        assert cost == 0.0


class TestRecordLLMCall:
    @pytest.fixture(autouse=True)
    def cleanup(self):
        _store.clear()
        yield
        _store.clear()

    @pytest.mark.asyncio
    async def test_returns_usage_dict(self):
        session = _FakeSession()
        resp = _FakeResponse(usage=_FakeUsage(
            prompt_tokens=100, completion_tokens=50, total_tokens=150
        ))
        usage = await record_llm_call(
            session, model="gpt-4o", response=resp,
            latency_ms=500, finish_reason="stop",
        )
        assert usage["prompt_tokens"] == 100
        assert usage["completion_tokens"] == 50
        assert "cost_usd" in usage
        assert "model" in usage

    @pytest.mark.asyncio
    async def test_sends_event(self):
        session = _FakeSession()
        resp = _FakeResponse(usage=_FakeUsage(
            prompt_tokens=10, completion_tokens=5, total_tokens=15
        ))
        await record_llm_call(
            session, model="test-model", response=resp,
            latency_ms=100, finish_reason="stop", kind="agent_loop",
        )
        assert len(session.events) == 1
        event = session.events[0]
        assert event.event_type == "llm_call"
        assert event.data["model"] == "test-model"
        assert event.data["kind"] == "agent_loop"

    @pytest.mark.asyncio
    async def test_updates_store(self):
        session = _FakeSession()
        resp = _FakeResponse(usage=_FakeUsage(
            prompt_tokens=100, completion_tokens=50, total_tokens=150
        ))
        await record_llm_call(
            session, model="gpt-4o", response=resp,
            latency_ms=200, finish_reason="stop",
        )
        await record_llm_call(
            session, model="gpt-4o", response=resp,
            latency_ms=300, finish_reason="tool_calls", kind="compaction",
        )
        summary = get_session_summary(session)
        assert summary["llm"]["total_calls"] == 2
        assert summary["llm"]["total_input_tokens"] == 200
        assert summary["llm"]["total_output_tokens"] == 100
        assert summary["llm"]["avg_latency_ms"] == 250
        assert summary["llm"]["calls_by_kind"]["agent_loop"] == 1
        assert summary["llm"]["calls_by_kind"]["compaction"] == 1
        assert summary["llm"]["calls_by_model"]["gpt-4o"] == 2

    @pytest.mark.asyncio
    async def test_none_session(self):
        resp = _FakeResponse(usage=_FakeUsage(
            prompt_tokens=10, completion_tokens=5, total_tokens=15
        ))
        usage = await record_llm_call(
            None, model="test", response=resp,
            latency_ms=100, finish_reason="stop",
        )
        assert usage["prompt_tokens"] == 10

    @pytest.mark.asyncio
    async def test_none_response(self):
        session = _FakeSession()
        usage = await record_llm_call(
            session, model="test", response=None,
            latency_ms=100, finish_reason=None,
        )
        assert usage["prompt_tokens"] == 0
        assert usage["cost_usd"] == 0.0


class TestRecordToolCall:
    @pytest.fixture(autouse=True)
    def cleanup(self):
        _store.clear()
        yield
        _store.clear()

    @pytest.mark.asyncio
    async def test_updates_store(self):
        session = _FakeSession()
        await record_tool_call(
            session, tool_name="model_builder",
            duration_ms=500, is_error=False,
        )
        await record_tool_call(
            session, tool_name="solve_job",
            duration_ms=2000, is_error=True,
        )
        summary = get_session_summary(session)
        assert summary["tools"]["total_calls"] == 2
        assert summary["tools"]["total_duration_ms"] == 2500
        assert summary["tools"]["calls_by_tool"]["model_builder"] == 1
        assert summary["tools"]["calls_by_tool"]["solve_job"] == 1
        assert summary["tools"]["errors_by_tool"]["solve_job"] == 1

    @pytest.mark.asyncio
    async def test_sends_event(self):
        session = _FakeSession()
        await record_tool_call(
            session, tool_name="bash",
            duration_ms=100, is_error=False,
        )
        assert len(session.events) == 1
        assert session.events[0].event_type == "tool_call_telemetry"


class TestRecordSolve:
    @pytest.fixture(autouse=True)
    def cleanup(self):
        _store.clear()
        yield
        _store.clear()

    @pytest.mark.asyncio
    async def test_successful_solve(self):
        session = _FakeSession()
        await record_solve(
            session, solver="highs", status="optimal",
            objective=42.0, gap=0.0, elapsed_s=1.5,
            nodes=10, iterations=100,
        )
        summary = get_session_summary(session)
        assert summary["solves"]["total_solves"] == 1
        assert summary["solves"]["successful_solves"] == 1
        assert summary["solves"]["failed_solves"] == 0
        assert summary["solves"]["success_rate"] == 1.0
        assert summary["solves"]["solves_by_solver"]["highs"] == 1

    @pytest.mark.asyncio
    async def test_failed_solve(self):
        session = _FakeSession()
        await record_solve(
            session, solver="highs", status="infeasible",
            elapsed_s=0.5,
        )
        summary = get_session_summary(session)
        assert summary["solves"]["failed_solves"] == 1
        assert summary["solves"]["success_rate"] == 0.0

    @pytest.mark.asyncio
    async def test_multiple_solvers(self):
        session = _FakeSession()
        await record_solve(session, solver="highs", status="optimal", elapsed_s=1.0)
        await record_solve(session, solver="scip", status="optimal", elapsed_s=2.0)
        await record_solve(session, solver="highs", status="time_limit", elapsed_s=300.0)
        summary = get_session_summary(session)
        assert summary["solves"]["total_solves"] == 3
        assert summary["solves"]["solves_by_solver"]["highs"] == 2
        assert summary["solves"]["solves_by_solver"]["scip"] == 1
        assert summary["solves"]["solves_by_status"]["optimal"] == 2
        assert summary["solves"]["solves_by_status"]["time_limit"] == 1

    @pytest.mark.asyncio
    async def test_sends_event(self):
        session = _FakeSession()
        await record_solve(
            session, solver="highs", status="optimal",
            objective=10.0, elapsed_s=1.0,
        )
        assert len(session.events) == 1
        assert session.events[0].event_type == "solve"
        assert session.events[0].data["solver"] == "highs"
        assert session.events[0].data["objective"] == 10.0


class TestGetSessionSummary:
    @pytest.fixture(autouse=True)
    def cleanup(self):
        _store.clear()
        yield
        _store.clear()

    def test_none_session(self):
        assert get_session_summary(None) == {}

    def test_empty_session(self):
        session = _FakeSession()
        summary = get_session_summary(session)
        assert summary["llm"]["total_calls"] == 0
        assert summary["tools"]["total_calls"] == 0
        assert summary["solves"]["total_solves"] == 0


class TestResetSession:
    @pytest.fixture(autouse=True)
    def cleanup(self):
        _store.clear()
        yield
        _store.clear()

    @pytest.mark.asyncio
    async def test_reset_clears_data(self):
        session = _FakeSession()
        await record_tool_call(session, tool_name="bash", duration_ms=100)
        summary_before = get_session_summary(session)
        assert summary_before["tools"]["total_calls"] == 1

        reset_session(session)
        summary_after = get_session_summary(session)
        assert summary_after["tools"]["total_calls"] == 0

    def test_reset_none_session(self):
        reset_session(None)


class TestTelemetryStore:
    def test_get_session_creates_new(self):
        store = TelemetryStore()
        s = store.get_session("abc")
        assert s.llm.total_calls == 0

    def test_get_session_returns_same(self):
        store = TelemetryStore()
        s1 = store.get_session("abc")
        s1.llm.total_calls = 5
        s2 = store.get_session("abc")
        assert s2.llm.total_calls == 5

    def test_remove_session(self):
        store = TelemetryStore()
        store.get_session("abc")
        store.remove_session("abc")
        s = store.get_session("abc")
        assert s.llm.total_calls == 0

    def test_clear(self):
        store = TelemetryStore()
        store.get_session("a")
        store.get_session("b")
        store.clear()
        s = store.get_session("a")
        assert s.llm.total_calls == 0


class TestHeartbeatSaver:
    def test_maybe_fire_none_session(self):
        HeartbeatSaver.maybe_fire(None)

    def test_resolve_interval_default(self):
        session = _FakeSession()
        interval = HeartbeatSaver._resolve_interval(session)
        assert interval == 60

    def test_resolve_interval_from_config(self):
        session = _FakeSession()

        class FakeConfig:
            heartbeat_interval_s = 30

        session.config = FakeConfig()
        interval = HeartbeatSaver._resolve_interval(session)
        assert interval == 30
