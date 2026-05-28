"""compare_solvers tool for OR-Intern v0.5.

Runs multiple solvers on the same model in parallel and compares performance:
solve time, objective value, gap, status. Supports HiGHS/SCIP/GLPK/Gurobi.
"""

import asyncio
import logging
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 300


def _build_solve_script(model_code: str, solver_name: str, model_dir: str) -> str:
    return f'''\
import sys, time as _time
sys.path.insert(0, r"{model_dir}")
from pyomo.environ import *

{model_code}

solver = SolverFactory("{solver_name}")
if not solver.available():
    print("SOLVER_UNAVAILABLE")
    sys.exit(0)

t0 = _time.monotonic()
try:
    result = solver.solve(model, tee=False)
    elapsed = _time.monotonic() - t0
    status = str(result.solver.termination_condition)
    try:
        obj = value(model.obj)
    except:
        obj = None
    gap = None
    try:
        gap = getattr(result.problem, "upper_bound", 0) - getattr(result.problem, "lower_bound", 0)
    except:
        pass
    print(f"SOLVE_RESULT|{{status}}|{{elapsed:.4f}}|{{obj}}|{{gap}}")
except Exception as e:
    elapsed = _time.monotonic() - t0
    print(f"SOLVE_ERROR|{{str(e)[:200]}}|{{elapsed:.4f}}")
'''


async def _run_single_solver(
    model_path: Path, solver_name: str, timeout: int
) -> dict:
    """Run a single solver and return result dict."""
    import sys
    model_code = model_path.read_text(encoding="utf-8")
    script = _build_solve_script(model_code, solver_name, str(model_path.parent))

    tmpdir = Path(__import__("tempfile").gettempdir()) / "or-intern"
    tmpdir.mkdir(exist_ok=True)
    script_path = tmpdir / f"bench_{solver_name}.py"
    script_path.write_text(script, encoding="utf-8")

    t0 = time.monotonic()
    result = {
        "solver": solver_name,
        "status": "ERROR",
        "elapsed_s": 0.0,
        "objective": None,
        "gap": None,
        "error": None,
    }

    try:
        process = await asyncio.create_subprocess_exec(
            sys.executable, str(script_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(model_path.parent),
        )
        stdout, stderr = await asyncio.wait_for(
            process.communicate(), timeout=timeout
        )
        elapsed = time.monotonic() - t0
        result["elapsed_s"] = elapsed

        out = stdout.decode("utf-8", errors="replace").strip()

        if "SOLVER_UNAVAILABLE" in out:
            result["status"] = "UNAVAILABLE"
            return result

        if "SOLVE_ERROR" in out:
            parts = out.split("|", 2)
            result["status"] = "ERROR"
            result["error"] = parts[1] if len(parts) > 1 else "unknown"
            return result

        if "SOLVE_RESULT" in out:
            parts = out.split("|")
            if len(parts) >= 5:
                result["status"] = parts[1]
                try:
                    result["elapsed_s"] = float(parts[2])
                except ValueError:
                    pass
                try:
                    result["objective"] = float(parts[3]) if parts[3] != "None" else None
                except ValueError:
                    pass
                try:
                    result["gap"] = float(parts[4]) if parts[4] != "None" else None
                except ValueError:
                    pass
            return result

        result["status"] = "UNKNOWN"
        result["error"] = out[:500]
        return result

    except asyncio.TimeoutError:
        result["elapsed_s"] = time.monotonic() - t0
        result["status"] = "TIMEOUT"
        try:
            process.kill()
        except Exception:
            pass
        return result
    except Exception as e:
        result["elapsed_s"] = time.monotonic() - t0
        result["error"] = str(e)[:200]
        return result


async def _run_parallel_benchmarks(
    model_path: Path, solvers: list[str], timeout: int
) -> list[dict]:
    """Run multiple solvers in parallel."""
    tasks = [
        _run_single_solver(model_path, s, timeout)
        for s in solvers
    ]
    return await asyncio.gather(*tasks)


# ── Tool spec ──

COMPARE_SOLVERS_TOOL_SPEC = {
    "name": "compare_solvers",
    "description": (
        "Run multiple solvers on the same model in parallel and compare "
        "performance: solve time, objective value, gap, status. "
        "Supports HiGHS, SCIP, GLPK, Gurobi, CPLEX. "
        "Use for solver selection and performance benchmarking."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "model_path": {
                "type": "string",
                "description": "Path to the Pyomo model file",
            },
            "solvers": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of solvers to compare (default: highs, scip, glpk)",
                "default": ["highs", "scip", "glpk"],
            },
            "timeout": {
                "type": "integer",
                "description": "Timeout per solver in seconds (default: 300)",
                "default": DEFAULT_TIMEOUT,
            },
        },
        "required": ["model_path"],
    },
}


async def compare_solvers_handler(args: dict[str, Any]) -> tuple[str, bool]:
    model_path_str = args.get("model_path", "")
    solvers = args.get("solvers", ["highs", "scip", "glpk"])
    timeout = args.get("timeout", DEFAULT_TIMEOUT)

    if not model_path_str:
        return "Error: No model path provided", True

    model_path = Path(model_path_str)
    if not model_path.exists():
        return f"Error: Model file not found: {model_path}", True

    results = await _run_parallel_benchmarks(model_path, solvers, timeout)

    available = [r for r in results if r["status"] not in ("UNAVAILABLE", "ERROR")]
    unavailable = [r for r in results if r["status"] in ("UNAVAILABLE", "ERROR")]

    best_obj = None
    best_solver = None
    for r in available:
        if r["status"] in ("Optimal", "optimal", "OPTIMAL", "Feasible", "FEASIBLE"):
            if r["objective"] is not None:
                if best_obj is None or r["objective"] > best_obj:
                    best_obj = r["objective"]
                    best_solver = r["solver"]

    out = "## Solver Comparison\n\n"
    out += "| Solver | Status | Time (s) | Objective | Gap |\n"
    out += "|--------|--------|----------|-----------|-----|\n"

    for r in sorted(results, key=lambda x: x["elapsed_s"]):
        status = r["status"]
        time_s = f"{r['elapsed_s']:.2f}"
        obj = f"{r['objective']:.4g}" if r["objective"] is not None else "—"
        gap = f"{r['gap']:.4g}" if r.get("gap") is not None else "—"
        marker = " ⭐" if r["solver"] == best_solver else ""
        out += f"| {r['solver']}{marker} | {status} | {time_s} | {obj} | {gap} |\n"

    if best_solver:
        fastest = min(available, key=lambda x: x["elapsed_s"])
        out += f"\n**Best objective**: {best_solver} ({best_obj:.4g})\n"
        out += f"**Fastest**: {fastest['solver']} ({fastest['elapsed_s']:.2f}s)\n"

    if unavailable:
        out += f"\n**Unavailable**: {', '.join(r['solver'] for r in unavailable)}\n"
        for r in unavailable:
            if r.get("error"):
                out += f"  - {r['solver']}: {r['error']}\n"

    return out, False
