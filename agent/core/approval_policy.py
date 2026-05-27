"""Approval policy for OR-Intern.

Defines when OR-specific operations require user approval:
- Commercial solver calls (Gurobi, CPLEX)
- Large-scale solves exceeding cost/time budget
- Auto-approval for open-source solvers on small problems
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)

# ── Configuration ──

# Solvers that always require approval (commercial, license-gated)
_COMMERCIAL_SOLVERS = {"gurobi", "cplex", "xpress", "mosek", "baron"}

# Open-source solvers that can be auto-approved
_OPEN_SOURCE_SOLVERS = {"highs", "scip", "glpk", "cbc", "ipopt"}

# Default auto-approval thresholds
_DEFAULT_MAX_SOLVE_TIME_S = 300  # 5 minutes
_DEFAULT_MAX_SOLVE_COST_USD = 1.0
_DEFAULT_MAX_ITERATIONS_AUTO = 500


def normalize_tool_operation(operation: Any) -> str:
    """Normalize operation string for comparison."""
    return str(operation or "").strip().lower()


def is_scheduled_operation(operation: Any) -> bool:
    """Check if operation is scheduled (requires approval)."""
    return normalize_tool_operation(operation).startswith("scheduled ")


# ── OR-specific approval rules ──

def is_commercial_solver(solver_name: str) -> bool:
    """Check if the solver requires a commercial license."""
    name = solver_name.strip().lower()
    return name in _COMMERCIAL_SOLVERS


def is_open_source_solver(solver_name: str) -> bool:
    """Check if the solver is open-source and can be auto-approved."""
    name = solver_name.strip().lower()
    return name in _OPEN_SOURCE_SOLVERS


def needs_solver_approval(solver_name: str, timeout: int = 0,
                           estimated_cost: float = 0.0,
                           config: Any = None) -> tuple[bool, str]:
    """Determine if a solve_job operation needs approval.

    Returns: (needs_approval: bool, reason: str)
    """
    name = solver_name.strip().lower()

    # Rule 1: Commercial solver → always require approval
    if is_commercial_solver(name):
        return True, (
            f"Solver '{solver_name}' requires a commercial license. "
            "Confirm you have a valid license before proceeding."
        )

    # Rule 2: Large timeout → require approval
    max_time = _DEFAULT_MAX_SOLVE_TIME_S
    if config and hasattr(config, "solver_timeout"):
        max_time = config.solver_timeout

    if timeout > max_time:
        return True, (
            f"Solve time limit ({timeout}s) exceeds auto-approval "
            f"threshold ({max_time}s). Please confirm."
        )

    # Rule 3: High estimated cost → require approval
    max_cost = _DEFAULT_MAX_SOLVE_COST_USD
    if config and hasattr(config, "auto_approval_cost_cap_usd"):
        max_cost = config.auto_approval_cost_cap_usd

    if estimated_cost > max_cost:
        return True, (
            f"Estimated cost (${estimated_cost:.2f}) exceeds auto-approval "
            f"cap (${max_cost:.2f}). Please confirm."
        )

    # Rule 4: Unknown solver → require approval
    if not is_open_source_solver(name) and not is_commercial_solver(name):
        return True, (
            f"Unknown solver '{solver_name}'. Confirm before proceeding."
        )

    # Auto-approve
    return False, f"Auto-approved: {solver_name} (open source, within budget)"


def estimate_solve_cost(solver_name: str, timeout: int,
                         model_variables: int = 0,
                         model_constraints: int = 0) -> float:
    """Estimate solve cost in USD.

    Simple heuristic based on solver type and problem size.
    """
    name = solver_name.strip().lower()
    problem_size = model_variables + model_constraints

    if is_commercial_solver(name):
        # Commercial: rough estimate based on size and time
        base_cost = 0.50 if name in ("gurobi", "cplex") else 1.00
        scale = 1.0 + (problem_size / 10000)  # Larger problems cost more
        time_factor = timeout / 3600  # Normalize to hours
        return base_cost * scale * max(time_factor, 0.01)
    else:
        # Open source: essentially free compute
        return 0.0


def auto_approval_allowed(config: Any) -> bool:
    """Check if auto-approval is globally enabled."""
    if config and hasattr(config, "yolo_mode") and config.yolo_mode:
        return True
    return False


def get_approval_summary(config: Any) -> str:
    """Generate a human-readable approval policy summary."""
    lines = [
        "## Approval Policy",
        "",
        "| Rule | Threshold | Status |",
        "|------|-----------|--------|",
    ]

    # Commercial solvers
    lines.append(
        "| Commercial solvers | Gurobi, CPLEX, etc. | "
        "Requires approval |"
    )

    # Auto-approval
    if auto_approval_allowed(config):
        lines.append(
            "| Auto-approval | Enabled (YOLO mode) | "
            "All tools auto-approved |"
        )
    else:
        max_time = getattr(config, "solver_timeout", _DEFAULT_MAX_SOLVE_TIME_S)
        max_cost = getattr(config, "auto_approval_cost_cap_usd", _DEFAULT_MAX_SOLVE_COST_USD)
        lines.append(
            f"| Solve timeout | < {max_time}s | Auto-approved |"
        )
        lines.append(
            f"| Solve cost | < ${max_cost:.2f} | Auto-approved |"
        )
        lines.append(
            "| Open-source solvers | HiGHS, SCIP, GLPK | Auto-approved |"
        )

    return "\n".join(lines)
