"""Cost estimation for OR-Intern.

Estimates costs for solver operations and LLM API calls.
No HuggingFace dependencies — purely OR-domain.
"""

import logging
import time
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

# ── Solver cost model ──

SOLVER_COST_PER_HOUR: dict[str, float] = {
    "highs": 0.0,
    "scip": 0.0,
    "glpk": 0.0,
    "cbc": 0.0,
    "ipopt": 0.0,
    "gurobi": 2.50,
    "cplex": 2.50,
    "xpress": 3.00,
    "mosek": 2.00,
}

COMMERCIAL_SOLVERS = {"gurobi", "cplex", "xpress", "mosek", "baron"}

# ── LLM cost model (USD per 1M tokens) ──

LLM_COST_PER_1M_TOKENS: dict[str, dict[str, float]] = {
    "default": {"input": 3.0, "output": 15.0},
    "gpt-4o": {"input": 2.5, "output": 10.0},
    "gpt-4o-mini": {"input": 0.15, "output": 0.6},
    "claude-sonnet-4-20250514": {"input": 3.0, "output": 15.0},
    "claude-haiku": {"input": 0.25, "output": 1.25},
}

# OR task-specific token budgets
OR_TASK_TOKEN_ESTIMATES = {
    "model_building": {"input": 5000, "output": 3000},
    "solve_monitoring": {"input": 1000, "output": 500},
    "sensitivity_analysis": {"input": 2000, "output": 1500},
    "report_generation": {"input": 3000, "output": 5000},
    "research": {"input": 4000, "output": 2000},
}


@dataclass(frozen=True)
class CostEstimate:
    """Estimated cost for an operation."""
    estimated_cost_usd: float | None
    billable: bool
    block_reason: str | None = None
    label: str | None = None


def _match_model_pricing(model_name: str) -> dict[str, float]:
    """Find pricing for a model, falling back to default."""
    name_lower = model_name.lower()
    for key, prices in LLM_COST_PER_1M_TOKENS.items():
        if key in name_lower:
            return prices
    return LLM_COST_PER_1M_TOKENS["default"]


def estimate_solver_cost(solver_name: str, timeout_s: int,
                         problem_size: int = 0) -> CostEstimate:
    """Estimate cost for a solver run."""
    name = solver_name.strip().lower()
    hourly_rate = SOLVER_COST_PER_HOUR.get(name)

    if hourly_rate is None:
        return CostEstimate(
            estimated_cost_usd=None,
            billable=True,
            block_reason=f"Unknown solver '{solver_name}'. Cannot estimate cost.",
            label=solver_name,
        )

    if hourly_rate == 0.0:
        return CostEstimate(
            estimated_cost_usd=0.0,
            billable=False,
            label=f"{name} (open source)",
        )

    hours = timeout_s / 3600.0
    cost = hourly_rate * hours
    scale = 1.0 + (problem_size / 100000) if problem_size > 0 else 1.0
    cost *= scale

    return CostEstimate(
        estimated_cost_usd=round(cost, 4),
        billable=True,
        label=f"{name} ({timeout_s}s)",
    )


def estimate_llm_cost(model_name: str, input_tokens: int,
                      output_tokens: int) -> CostEstimate:
    """Estimate cost for an LLM API call."""
    prices = _match_model_pricing(model_name)
    cost = (input_tokens * prices["input"] + output_tokens * prices["output"]) / 1_000_000

    return CostEstimate(
        estimated_cost_usd=round(cost, 6),
        billable=cost > 0,
        label=f"{model_name} ({input_tokens}+{output_tokens} tokens)",
    )


def estimate_task_cost(task_type: str, model_name: str = "default",
                       solver_name: str = "highs",
                       timeout_s: int = 300) -> CostEstimate:
    """Estimate total cost for an OR task (LLM + solver)."""
    tokens = OR_TASK_TOKEN_ESTIMATES.get(task_type, {"input": 2000, "output": 1000})
    llm_cost = estimate_llm_cost(model_name, tokens["input"], tokens["output"])
    solver_cost = estimate_solver_cost(solver_name, timeout_s)

    total = 0.0
    if llm_cost.estimated_cost_usd:
        total += llm_cost.estimated_cost_usd
    if solver_cost.estimated_cost_usd:
        total += solver_cost.estimated_cost_usd

    return CostEstimate(
        estimated_cost_usd=round(total, 4),
        billable=total > 0,
        label=f"{task_type}: LLM={model_name}, solver={solver_name}",
    )


async def estimate_tool_cost(
    tool_name: str, args: dict[str, Any], *, session: Any = None
) -> CostEstimate:
    """Estimate cost for a tool call (async interface for compatibility)."""
    if tool_name == "solve_job":
        solver = args.get("solver", "highs")
        timeout = args.get("timeout", 300)
        return estimate_solver_cost(solver, timeout)
    if tool_name in ("model_builder", "research", "report_generator",
                      "sensitivity_analysis"):
        model_name = "default"
        if session and hasattr(session, "config"):
            model_name = getattr(session.config, "model_name", "default")
        tokens = OR_TASK_TOKEN_ESTIMATES.get(tool_name, {"input": 3000, "output": 2000})
        return estimate_llm_cost(model_name, tokens["input"], tokens["output"])
    return CostEstimate(estimated_cost_usd=0.0, billable=False)
