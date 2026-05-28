"""Model checker for OR-Intern v0.5.

Validates Pyomo model files for syntax, consistency, and solver compatibility
before submission to solve_job. Catches common errors early.
"""

import ast
import logging
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _check_syntax(code: str) -> list[str]:
    """Check Python syntax of the model code."""
    errors = []
    try:
        ast.parse(code)
    except SyntaxError as e:
        errors.append(f"Syntax error at line {e.lineno}: {e.msg}")
    return errors


def _check_imports(code: str) -> list[str]:
    """Check that required imports are present."""
    warnings = []
    if "from pyomo.environ import" not in code and "import pyomo" not in code:
        warnings.append("Missing Pyomo import: add 'from pyomo.environ import *'")
    if "ConcreteModel" not in code and "AbstractModel" not in code:
        warnings.append("No model declaration found: expected ConcreteModel() or AbstractModel()")
    return warnings


def _check_variables(code: str) -> list[str]:
    """Check variable declarations."""
    warnings = []
    var_pattern = re.compile(r"model\.(\w+)\s*=\s*Var\(")
    vars_found = var_pattern.findall(code)
    if not vars_found:
        warnings.append("No decision variables found (model.X = Var(...))")

    for v in vars_found:
        if not re.search(rf"model\.{v}\s*=\s*Var\([^)]*domain\s*=", code):
            warnings.append(f"Variable '{v}' has no explicit domain — defaults to Reals")

    return warnings


def _check_objective(code: str) -> list[str]:
    """Check objective function."""
    errors = []
    if "Objective(" not in code and "Objective\n" not in code:
        errors.append("No objective function found: expected model.obj = Objective(...)")
    if "sense=" not in code:
        errors.append("Objective has no 'sense=' parameter — defaults to minimize")
    return errors


def _check_constraints(code: str) -> list[str]:
    """Check constraints."""
    warnings = []
    has_constraint = "Constraint(" in code or "ConstraintList" in code
    if not has_constraint:
        warnings.append("No constraints found — this may be an unconstrained problem")
    return warnings


def _check_solver_compat(code: str, solver: str = "") -> list[str]:
    """Check solver compatibility."""
    warnings = []
    if not solver:
        m = re.search(r"SolverFactory\(['\"](\w+)['\"]\)", code)
        if m:
            solver = m.group(1)

    if solver:
        if solver.lower() == "highs":
            if "Nonlinear" in code or "sin(" in code or "cos(" in code or "**" in code:
                warnings.append("HiGHS does not support nonlinear constraints — consider SCIP or IPOPT")
        if solver.lower() == "glpk":
            if "SOSConstraint" in code:
                warnings.append("GLPK has limited SOS support — consider HiGHS or SCIP")

    return warnings


def _check_numeric(code: str) -> list[str]:
    """Check for potential numeric issues."""
    warnings = []
    if re.search(r"float\(['\"]inf['\"]\)", code):
        warnings.append("Using float('inf') — may cause solver issues, use large finite bounds instead")
    if code.count("**") > 5:
        warnings.append("Many power operations (**) — may cause numerical issues for some solvers")
    return warnings


def _run_import_test(code: str) -> list[str]:
    """Try importing the model to verify it's valid Pyomo."""
    errors = []
    tmpdir = Path(tempfile.gettempdir()) / "or-intern"
    tmpdir.mkdir(exist_ok=True)
    test_file = tmpdir / "_model_check.py"
    test_file.write_text(code, encoding="utf-8")

    try:
        import subprocess
        result = subprocess.run(
            [sys.executable, str(test_file)],
            capture_output=True, text=True, timeout=10,
            cwd=str(tmpdir),
        )
        if result.returncode != 0:
            stderr = result.stderr.strip()
            if stderr:
                last_lines = stderr.split("\n")[-3:]
                errors.append(f"Runtime error:\n  " + "\n  ".join(last_lines))
    except subprocess.TimeoutExpired:
        errors.append("Model import timed out (>10s) — possible infinite loop")
    except Exception as e:
        errors.append(f"Import test failed: {e}")
    finally:
        test_file.unlink(missing_ok=True)

    return errors


# ── Tool spec ──

MODEL_CHECKER_TOOL_SPEC = {
    "name": "model_checker",
    "description": (
        "Validate a Pyomo model file for syntax, consistency, and solver "
        "compatibility. Checks: Python syntax, imports, variables, objective, "
        "constraints, numeric issues. Use before solve_job to catch errors early."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "model_path": {
                "type": "string",
                "description": "Path to the Pyomo model file to check",
            },
            "solver": {
                "type": "string",
                "description": "Target solver for compatibility check (optional)",
                "default": "",
            },
            "run_import_test": {
                "type": "boolean",
                "description": "Also try importing the model (default: true)",
                "default": True,
            },
        },
        "required": ["model_path"],
    },
}


async def model_checker_handler(args: dict[str, Any]) -> tuple[str, bool]:
    model_path_str = args.get("model_path", "")
    solver = args.get("solver", "")
    run_test = args.get("run_import_test", True)

    if not model_path_str:
        return "Error: No model path provided", True

    model_path = Path(model_path_str)
    if not model_path.exists():
        return f"Error: Model file not found: {model_path}", True

    code = model_path.read_text(encoding="utf-8")
    if not code.strip():
        return "Error: Model file is empty", True

    all_errors: list[str] = []
    all_warnings: list[str] = []

    syntax_errors = _check_syntax(code)
    all_errors.extend(syntax_errors)

    if not syntax_errors:
        import_warnings = _check_imports(code)
        all_warnings.extend(import_warnings)

        var_warnings = _check_variables(code)
        all_warnings.extend(var_warnings)

        obj_errors = _check_objective(code)
        all_errors.extend(obj_errors)

        con_warnings = _check_constraints(code)
        all_warnings.extend(con_warnings)

        compat_warnings = _check_solver_compat(code, solver)
        all_warnings.extend(compat_warnings)

        numeric_warnings = _check_numeric(code)
        all_warnings.extend(numeric_warnings)

        if run_test:
            runtime_errors = _run_import_test(code)
            all_errors.extend(runtime_errors)

    out = "## Model Check Results\n\n"
    if not all_errors and not all_warnings:
        out += "✅ **All checks passed!** Model is ready for solving.\n"
    else:
        if all_errors:
            out += f"### ❌ Errors ({len(all_errors)})\n\n"
            for e in all_errors:
                out += f"- {e}\n"
            out += "\n"
        if all_warnings:
            out += f"### ⚠️ Warnings ({len(all_warnings)})\n\n"
            for w in all_warnings:
                out += f"- {w}\n"

    is_error = len(all_errors) > 0
    return out, is_error
