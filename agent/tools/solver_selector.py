"""solver_selector tool for OR-Intern v0.5.

Recommends the best solver and parameters for a given problem type.
Supports Gurobi academic license detection and parameter tuning.
"""

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


def _check_solver(name: str) -> bool:
    try:
        from pyomo.environ import SolverFactory
        s = SolverFactory(name)
        return s.available()
    except Exception:
        return False


def _detect_gurobi_license() -> dict:
    """Detect Gurobi license status and type."""
    info = {
        "available": False,
        "license_type": "none",
        "expires": None,
        "message": "",
    }
    try:
        import gurobipy as gp
    except ImportError:
        info["message"] = "gurobipy not installed. Run: pip install gurobipy"
        return info

    try:
        m = gp.Model()
        info["available"] = True
        attrs = m.getAttr("LicenseExpiration") if hasattr(m, "getAttr") else None
        if attrs:
            info["expires"] = str(attrs)
        info["license_type"] = "commercial"
        env = gp.Env()
        if hasattr(env, "getAttr"):
            try:
                info["license_type"] = env.getAttr("LicenseType") or "commercial"
            except Exception:
                pass
        m.dispose()
        env.dispose()
    except gp.GurobiError as e:
        msg = str(e).lower()
        if "license" in msg:
            info["message"] = (
                "Gurobi license not found or expired. "
                "Academic users: visit https://www.gurobi.com/academia/academic-program-and-licenses/ "
                "for a free license. "
                "Commercial users: set GRB_LICENSE_FILE or install license to default location."
            )
        else:
            info["message"] = f"Gurobi error: {e}"
    except Exception as e:
        info["message"] = f"Gurobi check failed: {e}"
    return info


def _gurobi_params_for_problem(problem_type: str, size: str) -> dict:
    """Return recommended Gurobi parameters based on problem type and size."""
    params = {"TimeLimit": 3600}

    if problem_type in ("MIP", "MIQP", "MIQCP"):
        if size == "large":
            params.update({
                "MIPFocus": 2,
                "Presolve": 2,
                "Cuts": 2,
                "Heuristics": 0.15,
                "Threads": 0,
                "NodefileStart": 0.5,
            })
        elif size == "medium":
            params.update({
                "MIPFocus": 1,
                "Presolve": 2,
                "Cuts": 1,
                "Heuristics": 0.05,
            })
        else:
            params.update({
                "MIPFocus": 0,
                "Presolve": -1,
            })

    elif problem_type in ("LP",):
        if size == "large":
            params.update({
                "Method": 2,
                "Presolve": 2,
                "ScaleFlag": 2,
                "Threads": 0,
            })
        else:
            params.update({
                "Method": -1,
                "Presolve": -1,
            })

    elif problem_type in ("QP", "QCP"):
        params.update({
            "NonConvex": 2,
            "Presolve": 2,
        })

    return params


def _highs_params_for_problem(problem_type: str, size: str) -> dict:
    params = {}
    if problem_type in ("MIP",):
        if size == "large":
            params = {"threads": 0, "presolve": "on", "mip_rel_gap": 0.01}
        else:
            params = {"presolve": "on"}
    return params


def _scip_params_for_problem(problem_type: str, size: str) -> dict:
    params = {}
    if problem_type in ("MIP", "MINLP"):
        if size == "large":
            params = {"limits/time": 3600, "presolving/maxrounds": 100}
        else:
            params = {"limits/time": 600}
    return params


_SOLVERS = {
    "highs": {
        "name": "HiGHS",
        "type": "open_source",
        "supports": ["LP", "MIP"],
        "install": "pip install highspy",
        "pyomo_name": "highs",
        "strengths": "Fast, free, excellent for LP and MIP up to medium scale",
        "limitations": "No NLP support, may be slower than Gurobi for very large MIPs",
        "param_tuner": _highs_params_for_problem,
    },
    "scip": {
        "name": "SCIP",
        "type": "open_source",
        "supports": ["LP", "MIP", "MINLP"],
        "install": "pip install pyscipopt",
        "pyomo_name": "scip",
        "strengths": "Free, supports nonlinear constraints, constraint programming",
        "limitations": "Slower than commercial solvers for large pure LP/MIP",
        "param_tuner": _scip_params_for_problem,
    },
    "glpk": {
        "name": "GLPK",
        "type": "open_source",
        "supports": ["LP", "MIP"],
        "install": "pip install glpk (or system package)",
        "pyomo_name": "glpk",
        "strengths": "Classic open-source solver, widely available",
        "limitations": "Slower, less actively maintained",
        "param_tuner": lambda pt, sz: {},
    },
    "gurobi": {
        "name": "Gurobi",
        "type": "commercial",
        "supports": ["LP", "MIP", "QP", "MIQP", "MIQCP", "NLP"],
        "install": "pip install gurobipy (requires license)",
        "pyomo_name": "gurobi",
        "strengths": "Industry-leading MIP performance, excellent parallel support, NLP via Gurobi 11+",
        "limitations": "Requires commercial/academic license",
        "requires_approval": True,
        "param_tuner": _gurobi_params_for_problem,
    },
    "cplex": {
        "name": "CPLEX",
        "type": "commercial",
        "supports": ["LP", "MIP", "QP", "MIQP"],
        "install": "pip install cplex (requires license)",
        "pyomo_name": "cplex",
        "strengths": "Excellent for large-scale LP, strong cutting planes",
        "limitations": "Requires commercial/academic license",
        "requires_approval": True,
        "param_tuner": lambda pt, sz: {"timelimit": 3600},
    },
}


def _detect_problem_size(description: str) -> str:
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
    """Recommend a solver with tuned parameters."""
    pt = problem_type.upper()
    candidates = []
    for key, solver in _SOLVERS.items():
        if pt in solver["supports"]:
            if prefer_open_source and solver["type"] == "commercial":
                continue
            candidates.append((key, solver))

    if not candidates:
        candidates = [(k, v) for k, v in _SOLVERS.items()
                      if pt in v["supports"]]

    if not candidates:
        return {
            "solver": "highs", "pyomo_name": "highs", "name": "HiGHS",
            "type": "open_source", "params": {},
            "reasoning": "Default fallback — no solver found for this problem type",
            "requires_approval": False,
        }

    def score(item):
        k, s = item
        v = 0
        if s["type"] == "open_source":
            v += 10
        if size == "large" and s["type"] == "commercial":
            v += 5
        if k == "highs":
            v += 2
        return v

    best_key, best_solver = max(candidates, key=score)
    tuner = best_solver.get("param_tuner", lambda pt, sz: {})
    params = tuner(pt, size)

    license_info = {}
    if best_key == "gurobi":
        license_info = _detect_gurobi_license()

    return {
        "solver": best_key,
        "pyomo_name": best_solver["pyomo_name"],
        "name": best_solver["name"],
        "type": best_solver["type"],
        "params": params,
        "reasoning": (
            f"Selected {best_solver['name']} for {pt} ({size} scale). "
            f"{best_solver['strengths']}."
        ),
        "requires_approval": best_solver.get("requires_approval", False),
        "license_info": license_info,
    }


def list_available_solvers() -> list[dict]:
    result = []
    for key, solver in _SOLVERS.items():
        available = _check_solver(solver["pyomo_name"])
        license_info = {}
        if key == "gurobi" and available:
            license_info = _detect_gurobi_license()

        result.append({
            "name": solver["name"],
            "key": key,
            "type": solver["type"],
            "supports": solver["supports"],
            "available": available,
            "strengths": solver["strengths"],
            "license_info": license_info,
        })
    return result


# ── Tool spec and handler ──

SOLVER_SELECTOR_TOOL_SPEC = {
    "name": "solver_selector",
    "description": (
        "Recommend the best optimization solver for a given problem. "
        "Provides tuned parameters, license detection (Gurobi academic), "
        "and reasoning. Use 'list' to see all available solvers."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "operation": {
                "type": "string",
                "enum": ["recommend", "list"],
                "description": "'recommend' for recommendation, 'list' to show all solvers",
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
    operation = args.get("operation", "recommend")

    if operation == "list":
        solvers = list_available_solvers()
        lines = ["## Available Solvers\n"]
        for s in solvers:
            status = "✅" if s["available"] else "❌"
            lic = ""
            if s.get("license_info"):
                lt = s["license_info"].get("license_type", "")
                if lt:
                    lic = f" (license: {lt})"
            lines.append(
                f"- {status} **{s['name']}** ({s['type']}){lic} — "
                f"Supports: {', '.join(s['supports'])} — {s['strengths']}"
            )
        return "\n".join(lines), False

    problem_type = args.get("problem_type", "LP").upper()
    description = args.get("problem_description", "")
    prefer_os = args.get("prefer_open_source", True)

    size = _detect_problem_size(description)
    rec = recommend_solver(problem_type, size, prefer_os)

    result = f"## Solver Recommendation\n\n"
    result += f"**Problem type**: {problem_type}\n"
    result += f"**Estimated size**: {size}\n"
    result += f"**Prefer open-source**: {prefer_os}\n\n"
    result += f"### Recommended: {rec['name']}\n\n"
    result += f"- **Pyomo name**: `{rec['pyomo_name']}`\n"
    result += f"- **Type**: {rec['type']}\n"
    result += f"- **Reasoning**: {rec['reasoning']}\n"

    if rec.get("params"):
        result += f"- **Tuned parameters**:\n"
        for k, v in rec["params"].items():
            result += f"  - `{k}`: {v}\n"

    result += f"- **Requires approval**: {'⚠️ Yes' if rec['requires_approval'] else '✅ No'}\n"

    if rec.get("license_info"):
        li = rec["license_info"]
        if li.get("message"):
            result += f"\n### License Info\n\n{li['message']}\n"
        elif li.get("available"):
            result += f"\n### License Info\n\n✅ Gurobi license detected (type: {li.get('license_type', 'unknown')})\n"

    result += f"\n### Usage\n```python\nsolver = SolverFactory('{rec['pyomo_name']}')\n"
    if rec.get("params"):
        for k, v in rec["params"].items():
            result += f"solver.options['{k}'] = {v!r}\n"
    result += f"result = solver.solve(model)\n```\n"

    return result, False
