"""Error recovery utilities for OR-Intern.

Provides retry logic, fallback strategies, and error diagnosis
for optimization workflow failures.
"""

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_DELAY = 2.0


async def retry_on_failure(
    func,
    *args,
    max_retries: int = MAX_RETRIES,
    retry_delay: float = RETRY_DELAY,
    **kwargs,
) -> tuple[Any, bool]:
    """Retry an async function on failure.

    Args:
        func: Async function to retry
        *args: Positional arguments for func
        max_retries: Maximum number of retry attempts
        retry_delay: Delay between retries in seconds
        **kwargs: Keyword arguments for func

    Returns:
        Tuple of (result, is_error)
    """
    last_error = None

    for attempt in range(max_retries + 1):
        try:
            result = await func(*args, **kwargs)
            if isinstance(result, tuple) and len(result) == 2:
                output, is_error = result
                if not is_error:
                    return result
                last_error = output
                if attempt < max_retries:
                    logger.warning(
                        "Attempt %d/%d failed: %s. Retrying in %.1fs...",
                        attempt + 1,
                        max_retries + 1,
                        output[:100],
                        retry_delay,
                    )
                    await asyncio.sleep(retry_delay)
            else:
                return result, False
        except Exception as e:
            last_error = str(e)
            if attempt < max_retries:
                logger.warning(
                    "Attempt %d/%d raised exception: %s. Retrying in %.1fs...",
                    attempt + 1,
                    max_retries + 1,
                    str(e)[:100],
                    retry_delay,
                )
                await asyncio.sleep(retry_delay)

    return f"Error after {max_retries + 1} attempts: {last_error}", True


def diagnose_solve_failure(status: str, error_msg: str = "") -> dict[str, Any]:
    """Diagnose common solve failures and suggest fixes.

    Args:
        status: Solver status string
        error_msg: Optional error message

    Returns:
        Dict with diagnosis and suggested fixes
    """
    status_upper = status.upper()
    diagnosis = {
        "status": status,
        "cause": "Unknown",
        "suggestions": [],
        "auto_fix": None,
    }

    if "INFEASIBLE" in status_upper:
        diagnosis["cause"] = "No feasible solution exists"
        diagnosis["suggestions"] = [
            "Check constraint definitions for conflicts",
            "Use sensitivity_analysis to identify conflicting constraints",
            "Relax constraints or add slack variables",
            "Verify data inputs are correct",
        ]
        diagnosis["auto_fix"] = "relax_constraints"

    elif "UNBOUNDED" in status_upper:
        diagnosis["cause"] = "Objective can improve without limit"
        diagnosis["suggestions"] = [
            "Add bounds to decision variables",
            "Check if constraints are missing",
            "Verify objective function direction (max/min)",
        ]

    elif "TIME_LIMIT" in status_upper or "TIMEOUT" in status_upper:
        diagnosis["cause"] = "Solver exceeded time limit"
        diagnosis["suggestions"] = [
            "Increase timeout parameter",
            "Use a faster solver (Gurobi, HiGHS)",
            "Simplify the model or reduce problem size",
            "Adjust solver parameters (MIPFocus, Presolve)",
        ]
        diagnosis["auto_fix"] = "increase_timeout"

    elif "NUMERIC" in status_upper or "INF" in error_msg.upper():
        diagnosis["cause"] = "Numerical issues in model"
        diagnosis["suggestions"] = [
            "Check for division by zero",
            "Scale coefficients to similar magnitudes",
            "Use bounds instead of large penalty values",
            "Check for degenerate constraints",
        ]

    elif "SOLVER" in status_upper and "NOT" in status_upper:
        diagnosis["cause"] = "Solver not available"
        diagnosis["suggestions"] = [
            "Install the solver: pip install highspy (HiGHS)",
            "Use solver_selector to find available solvers",
            "Try alternative solver: SCIP, GLPK",
        ]
        diagnosis["auto_fix"] = "switch_solver"

    elif "IMPORT" in status_upper or "MODULE" in error_msg.upper():
        diagnosis["cause"] = "Import error in model code"
        diagnosis["suggestions"] = [
            "Check Pyomo installation: pip install pyomo",
            "Verify model syntax with model_checker",
            "Check for missing imports in model file",
        ]

    return diagnosis


def suggest_solver_switch(
    current_solver: str,
    problem_type: str,
    attempt: int,
) -> str:
    """Suggest an alternative solver after failure.

    Args:
        current_solver: Current solver that failed
        problem_type: Problem type (LP, MIP, NLP, etc.)
        attempt: Current attempt number (0-based)

    Returns:
        Suggested solver name
    """
    solver_priority = {
        "LP": ["highs", "glpk", "scip", "cplex", "gurobi"],
        "MIP": ["highs", "scip", "glpk", "cplex", "gurobi"],
        "NLP": ["ipopt", "scip", "gurobi"],
        "MINLP": ["scip", "gurobi"],
    }

    candidates = solver_priority.get(problem_type.upper(), ["highs", "scip", "glpk"])

    for solver in candidates:
        if solver != current_solver.lower():
            return solver

    return "highs"


def format_recovery_report(
    original_error: str,
    diagnosis: dict,
    recovery_attempts: list[dict],
    final_status: str,
) -> str:
    """Format a recovery report for the user.

    Args:
        original_error: Original error message
        diagnosis: Diagnosis dict from diagnose_solve_failure
        recovery_attempts: List of recovery attempt results
        final_status: Final status after recovery

    Returns:
        Formatted recovery report
    """
    report = "## Error Recovery Report\n\n"
    report += f"**Original Error**: {original_error}\n\n"
    report += f"**Diagnosis**: {diagnosis['cause']}\n\n"

    if diagnosis["suggestions"]:
        report += "### Suggested Fixes\n\n"
        for i, suggestion in enumerate(diagnosis["suggestions"], 1):
            report += f"{i}. {suggestion}\n"
        report += "\n"

    if recovery_attempts:
        report += "### Recovery Attempts\n\n"
        for attempt in recovery_attempts:
            status_icon = "✅" if attempt.get("success") else "❌"
            report += f"{status_icon} **Attempt {attempt['number']}**: "
            report += f"{attempt.get('description', 'N/A')}\n"
            if attempt.get("error"):
                report += f"   Error: {attempt['error'][:100]}\n"
        report += "\n"

    report += f"**Final Status**: {final_status}\n"

    return report
