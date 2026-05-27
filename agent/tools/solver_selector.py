"""solver_selector tool for OR-Intern Phase 1.

Recommends the best solver and parameters for a given problem type.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


def _check_solver(name: str) -> bool:
    """Check if a solver is available via Pyomo."""
    try:
        from pyomo.environ import SolverFactory
        s = SolverFactory(name)
        return s.available()
    except Exception:
        return False


# ── Solver registry ──

_SOLVERS = {
    "highs": {
        "name": "HiGHS",
        "type": "open_source",
        "supports": ["LP", "MIP"],
        "install": "pip install highspy",
        "pyomo_name": "highs",
        "strengths": "Fast, free, excellent for LP and MIP up to medium scale",
        "limitations": "No NLP support, may be slower than Gurobi for very large MIPs",
        "default_params": {},
    },
    "scip": {
        "name": "SCIP",
        "type": "open_source",
        "supports": ["LP", "MIP", "MINLP"],
        "install": "pip install pyscipopt",
        "pyomo_name": "scip",
        "strengths": "Free, supports nonlinear constraints, constraint programming. Excellent for MINLP.",
        "limitations": "Slower than commercial solvers for large pure LP/MIP",
        "default_params": {},
        "available_check": lambda: _check_solver("scip"),
    },
    "glpk": {
        "name": "GLPK",
        "type": "open_source",
        "supports": ["LP", "MIP"],
        "install": "pip install glpk (or system package)",
        "pyomo_name": "glpk",
        "strengths": "Classic open-source solver, widely available",
        "limitations": "Slower, less actively maintained",
        "default_params": {},
    },
    "gurobi": {
        "name": "Gurobi",
        "type": "commercial",
        "supports": ["LP", "MIP", "QP", "MIQP", "MIQCP"],
        "install": "pip install gurobipy (requires license)",
        "pyomo_name": "gurobi",
        "strengths": "Industry-leading performance for MIP, excellent parallel support",
        "limitations": "Requires commercial/academic license",
        "requires_approval": True,
        "default_params": {"TimeLimit": 3600},
    },
    "cplex": {
        "name": "CPLEX",
        "type": "commercial",
        "supports": ["LP", "MIP", "QP", "MIQP"],
        "install": "pip install cplex (requires license)",
        "pyomo_name": "cplex",
        "strengths": "Industry-leading, excellent for large-scale LP",
        "limitations": "Requires commercial/academic license",
        "requires_approval": True,
        "default_params": {"timelimit": 3600},
    },
}


# ── Solver recommendation logic ──

def _detect_problem_size(description: str) -> str:
    """Heuristically estimate problem size from description."""
    desc_lower = description.lower()
    if any(kw in desc_lower for kw in ["thousands", "large", "huge", "massive",
                                         "10000", "100000", "million"]):
        return "large"
    if any(kw in desc_lower for kw in ["hundreds", "medium", "moderate",
                                         "1000", "5000"]):
        return "medium"
    return "small"


def recommend_solver(problem_type: str, size: str = "small",
                     prefer_open_source: bool = True) -> dict:
    """Recommend a solver for the given problem type and size.

    Returns:
      dict with solver name, Pyomo name, params, reasoning
    """
    # Filter by problem type support
    candidates = []
    for key, solver in _SOLVERS.items():
        if problem_type in solver["supports"]:
            if prefer_open_source and solver["type"] == "commercial":
                continue
            candidates.append((key, solver))

    if not candidates:
        # Fall back to any solver
        candidates = [(k, v) for k, v in _SOLVERS.items()
                      if problem_type in v["supports"]]

    if not candidates:
        return {"solver": "highs", "pyomo_name": "highs",
                "params": {}, "reasoning": "Default fallback"}

    # Score candidates
    def score(solver_info):
        s = 0
        if solver_info["type"] == "open_source":
            s += 10  # Prefer open source by default
        if size == "large" and solver_info["type"] == "commercial":
            s += 5   # Commercial solvers better for large problems
        if size == "small":
            s += 3   # Any solver works
        return s

    best_key, best_solver = max(candidates, key=lambda x: score(x[1]))

    return {
        "solver": best_key,
        "pyomo_name": best_solver["pyomo_name"],
        "name": best_solver["name"],
        "type": best_solver["type"],
        "params": best_solver["default_params"],
        "reasoning": (
            f"Selected {best_solver['name']} because: {best_solver['strengths']}. "
            f"Problem size estimated as '{size}'. "
            f"{'Requires license approval.' if best_solver.get('requires_approval') else ''}"
        ),
        "requires_approval": best_solver.get("requires_approval", False),
    }


def list_available_solvers() -> list[dict]:
    """List all known solvers with their capabilities."""
    result = []
    for key, solver in _SOLVERS.items():
        try:
            __import__(solver["pyomo_name"])
            available = "available"
        except ImportError:
            available = "not installed"

        result.append({
            "name": solver["name"],
            "key": key,
            "type": solver["type"],
            "supports": solver["supports"],
            "available": available,
            "strengths": solver["strengths"],
        })
    return result


# ── Tool spec and handler ──

SOLVER_SELECTOR_TOOL_SPEC = {
    "name": "solver_selector",
    "description": (
        "Recommend the best optimization solver for a given problem. "
        "Input: problem type (LP, MIP, NLP, etc.) and optional size estimate. "
        "Output: recommended solver with parameters and reasoning. "
        "Use 'list' operation to see all available solvers."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "operation": {
                "type": "string",
                "enum": ["recommend", "list"],
                "description": "Operation: 'recommend' for solver recommendation, 'list' to show all solvers",
                "default": "recommend",
            },
            "problem_type": {
                "type": "string",
                "description": "Problem type: LP, MIP, NLP, MINLP, QP, etc.",
            },
            "problem_description": {
                "type": "string",
                "description": "Problem description for size estimation",
            },
            "prefer_open_source": {
                "type": "boolean",
                "description": "Prefer open-source solvers (default: true)",
                "default": True,
            },
        },
    },
}


async def solver_selector_handler(args: dict[str, Any]) -> tuple[str, bool]:
    """Handler for solver_selector tool."""
    operation = args.get("operation", "recommend")

    if operation == "list":
        solvers = list_available_solvers()
        lines = ["## Available Solvers\n"]
        for s in solvers:
            status = "[OK]" if s["available"] == "available" else "[NOT AVAILABLE]"
            lines.append(
                f"- {status} **{s['name']}** ({s['type']}) — "
                f"Supports: {', '.join(s['supports'])} — {s['strengths']}"
            )
        return "\n".join(lines), False

    # Recommend
    problem_type = args.get("problem_type", "LP").upper()
    description = args.get("problem_description", "")
    prefer_os = args.get("prefer_open_source", True)

    size = _detect_problem_size(description)
    rec = recommend_solver(problem_type, size, prefer_os)

    result = f"""## Solver Recommendation

**Problem type**: {problem_type}
**Estimated size**: {size}
**Prefer open-source**: {prefer_os}

### Recommended: {rec['name']}

- **Pyomo name**: `{rec['pyomo_name']}`
- **Type**: {rec['type']}
- **Reasoning**: {rec['reasoning']}
- **Default parameters**: {rec['params']}
- **Requires approval**: {'⚠️ Yes' if rec['requires_approval'] else '✅ No'}

### Usage in Pyomo
```python
solver = SolverFactory('{rec['pyomo_name']}')
result = solver.solve(model)
```
"""
    return result, False
