"""End-to-end tests that call the real LLM.

These tests are SKIPPED by default because they:
  1. Require a real API key (OPENAI_API_KEY or equivalent)
  2. Cost money per run
  3. Are slow (10-30s per test)

To run them explicitly:
  uv run pytest tests/e2e/test_llm_e2e.py -v --run-e2e

To run with a specific model:
  OR_INTERN_MODEL=openai/gpt-4o uv run pytest tests/e2e/test_llm_e2e.py -v --run-e2e
"""

import asyncio
import os
import re

import pytest
from dotenv import load_dotenv

load_dotenv()

# Skip all tests in this module unless --run-e2e is passed
pytestmark = pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY") and not os.getenv("OR_INTERN_RUN_E2E"),
    reason="E2E tests require OPENAI_API_KEY or OR_INTERN_RUN_E2E=1",
)


def _collect_tools_called(events: list) -> set[str]:
    """Extract tool names from tool_call events."""
    tools = set()
    for event in events:
        if event.event_type == "tool_call":
            name = event.data.get("tool", "")
            if name:
                tools.add(name)
    return tools


def _collect_final_response(events: list) -> str:
    """Collect all assistant text chunks into one string."""
    chunks = []
    for event in events:
        if event.event_type == "assistant_chunk":
            chunks.append(event.data.get("content", ""))
        elif event.event_type == "tool_output":
            chunks.append(event.data.get("output", ""))
    return "\n".join(chunks)


async def _run_agent(prompt: str, config=None) -> tuple[list, str, set[str]]:
    """Run the agent loop with a real LLM and return (events, response, tools_called)."""
    from agent.config import Config
    from agent.core.agent_loop import submission_loop
    from agent.core.session import OpType
    from agent.main import Operation, Submission
    from agent.core.tools import ToolRouter, create_builtin_tools

    if config is None:
        config = Config.from_env()
    config.approval.yolo_mode = True

    print(f"  [e2e] model: {config.current_model.name}")
    print(f"  [e2e] api_base: {config.current_model.api_base}")

    tool_router = ToolRouter()
    for tool in create_builtin_tools():
        tool_router.register(tool)

    submission_queue = asyncio.Queue()
    event_queue = asyncio.Queue()

    agent_task = asyncio.create_task(
        submission_loop(
            submission_queue,
            event_queue,
            config=config,
            tool_router=tool_router,
            local_mode=True,
            stream=True,
        )
    )

    sub = Submission(
        id="e2e_1",
        operation=Operation(
            op_type=OpType.USER_INPUT,
            data={"text": prompt},
        ),
    )
    await submission_queue.put(sub)

    events = []
    timeout = 300  # 5 minutes max
    try:
        await asyncio.wait_for(_collect_events(event_queue, events), timeout=timeout)
    except asyncio.TimeoutError:
        pass
    finally:
        agent_task.cancel()
        try:
            await agent_task
        except asyncio.CancelledError:
            pass

    tools_called = _collect_tools_called(events)
    response = _collect_final_response(events)
    return events, response, tools_called


async def _collect_events(event_queue, events):
    """Collect events until turn_complete."""
    while True:
        event = await event_queue.get()
        events.append(event)
        print(f"  [e2e] event: {event.event_type} | {str(event.data)[:200]}")
        if event.event_type in ("turn_complete",):
            break
        if event.event_type == "error":
            print(f"  [e2e] ERROR: {event.data}")
            break


@pytest.mark.asyncio
async def test_simple_lp_solve():
    """Test that agent solves a simple LP and calls expected tools."""
    events, response, tools = await _run_agent(
        "Solve: maximize 3x + 2y subject to x + y <= 10, x >= 0, y >= 0"
    )

    assert "model_builder" in tools or "problem_templates" in tools, \
        f"Expected model_builder or problem_templates in tools, got: {tools}"
    assert "solve_job" in tools, \
        f"Expected solve_job in tools, got: {tools}"
    assert "OPTIMAL" in response or "optimal" in response.lower() or "30" in response, \
        f"Expected OPTIMAL or 30 in response, got: {response[:500]}"


@pytest.mark.asyncio
async def test_full_pipeline_lp():
    """Test that agent goes through all 6 phases for a simple LP."""
    events, response, tools = await _run_agent(
        "Maximize 5x + 3y subject to 2x + y <= 20, x + 3y <= 30, x >= 0, y >= 0. "
        "Please solve this problem completely with validation, sensitivity analysis, "
        "visualization, and a report."
    )

    assert "model_builder" in tools or "problem_templates" in tools
    assert "solve_job" in tools
    assert "validate_solution" in tools, \
        f"Expected validate_solution (Phase 3), got tools: {tools}"
    assert "sensitivity_analysis" in tools, \
        f"Expected sensitivity_analysis (Phase 4), got tools: {tools}"


@pytest.mark.asyncio
async def test_template_matching():
    """Test that agent recognizes a known problem type and uses templates."""
    events, response, tools = await _run_agent(
        "I need to solve a classic knapsack problem. "
        "Capacity is 50. Items have weights [10, 20, 30, 15, 25] "
        "and values [60, 100, 120, 70, 90]. Maximize total value."
    )

    assert "model_builder" in tools or "problem_templates" in tools, \
        f"Expected modeling tool, got: {tools}"
    assert "solve_job" in tools, \
        f"Expected solve_job, got: {tools}"


@pytest.mark.asyncio
async def test_paper_search():
    """Test that agent can search for OR papers."""
    events, response, tools = await _run_agent(
        "Search for recent papers on 'vehicle routing problem with time windows' "
        "and summarize the top 2 results."
    )

    assert "or_papers" in tools, \
        f"Expected or_papers tool, got: {tools}"
    assert len(response) > 200, \
        f"Expected substantial response about papers, got: {response[:200]}"


@pytest.mark.asyncio
async def test_solver_comparison():
    """Test that agent can compare multiple solvers."""
    events, response, tools = await _run_agent(
        "Solve this LP with 3 different solvers and compare their performance: "
        "maximize x + y subject to x + y <= 100, x <= 60, y <= 80, x >= 0, y >= 0"
    )

    assert "model_builder" in tools or "problem_templates" in tools
    assert "solve_job" in tools or "compare_solvers" in tools, \
        f"Expected solve_job or compare_solvers, got: {tools}"
    assert "compare_solvers" in tools, \
        f"Expected compare_solvers, got: {tools}"


@pytest.mark.asyncio
async def test_infeasibility_diagnosis():
    """Test that agent diagnoses infeasible problems instead of just reporting INFEASIBLE."""
    events, response, tools = await _run_agent(
        "Solve: maximize x + y subject to x + y <= 5, x + y >= 10, x >= 0, y >= 0"
    )

    assert "model_builder" in tools or "problem_templates" in tools
    assert "solve_job" in tools
    response_lower = response.lower()
    has_diagnosis = any(word in response_lower for word in [
        "infeasible", "conflict", "constraint", "relax", "contradict",
    ])
    assert has_diagnosis, \
        f"Expected infeasibility diagnosis in response, got: {response[:500]}"


@pytest.mark.asyncio
async def test_mip_problem():
    """Test that agent handles a mixed-integer problem."""
    events, response, tools = await _run_agent(
        "A factory makes chairs (profit $50, needs 2 wood + 3 labor hours) "
        "and tables (profit $80, needs 5 wood + 2 labor hours). "
        "100 wood and 90 labor hours available. Chairs and tables must be integers. "
        "Maximize profit."
    )

    assert "model_builder" in tools or "problem_templates" in tools
    assert "solve_job" in tools
