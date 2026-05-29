"""Model checker for OR-Intern v1.0.

Validates Pyomo and cvxpy model files for syntax, consistency, solver
compatibility, and DCP compliance before submission to solve_job.
"""

import ast
import logging
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _detect_framework(code: str) -> str:
    """Detect if code uses Pyomo or cvxpy."""
    if "import cvxpy" in code or "cp.Variable" in code:
        return "cvxpy"
    return "pyomo"


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
    framework = _detect_framework(code)

    if framework == "cvxpy":
        if "import cvxpy" not in code:
            warnings.append("Missing cvxpy import: add 'import cvxpy as cp'")
        if "cp.Variable" not in code:
            warnings.append("No cvxpy variables found: expected cp.Variable(...)")
    else:
        if "from pyomo.environ import" not in code and "import pyomo" not in code:
            warnings.append("Missing Pyomo import: add 'from pyomo.environ import *'")
        if "ConcreteModel" not in code and "AbstractModel" not in code:
            warnings.append("No model declaration found: expected ConcreteModel() or AbstractModel()")
    return warnings


def _check_variables(code: str) -> list[str]:
    """Check variable declarations."""
    warnings = []
    framework = _detect_framework(code)

    if framework == "cvxpy":
        var_pattern = re.compile(r"(\w+)\s*=\s*cp\.Variable\(")
        vars_found = var_pattern.findall(code)
        if not vars_found:
            warnings.append("No cvxpy variables found (X = cp.Variable(...))")
    else:
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
    framework = _detect_framework(code)

    if framework == "cvxpy":
        if "cp.Minimize" not in code and "cp.Maximize" not in code:
            errors.append("No cvxpy objective found: expected cp.Minimize(...) or cp.Maximize(...)")
        if "cp.Problem" not in code:
            errors.append("No cp.Problem found: expected problem = cp.Problem(objective, constraints)")
    else:
        if "Objective(" not in code and "Objective\n" not in code:
            errors.append("No objective function found: expected model.obj = Objective(...)")
        if "sense=" not in code:
            errors.append("Objective has no 'sense=' parameter — defaults to minimize")
    return errors


def _check_constraints(code: str) -> list[str]:
    """Check constraints."""
    warnings = []
    framework = _detect_framework(code)

    if framework == "cvxpy":
        if "constraints" not in code:
            warnings.append("No constraints variable found for cvxpy model")
    else:
        has_constraint = "Constraint(" in code or "ConstraintList" in code
        if not has_constraint:
            warnings.append("No constraints found — this may be an unconstrained problem")
    return warnings


def _check_dcp_compliance(code: str) -> list[str]:
    """Check DCP compliance for cvxpy models."""
    warnings = []
    framework = _detect_framework(code)

    if framework != "cvxpy":
        return warnings

    non_dcp_patterns = [
        (r"\bmax\s*\(", "max() is not DCP — use cp.maximum()"),
        (r"\bmin\s*\(", "min() is not DCP — use cp.minimum()"),
        (r"\babs\s*\(", "abs() without cp — use cp.abs()"),
        (r"\bsqrt\s*\(", "sqrt() without cp — use cp.sqrt()"),
        (r"\blog\s*\(", "log() without cp — use cp.log()"),
        (r"\bexp\s*\(", "exp() without cp — use cp.exp()"),
    ]

    for pattern, msg in non_dcp_patterns:
        if re.search(pattern, code) and not re.search(rf"cp\.{pattern[2:]}", code):
            warnings.append(f"Potential DCP violation: {msg}")

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
        "Validate a Pyomo or cvxpy model file for syntax, consistency, solver "
        "compatibility, and DCP compliance. Checks: Python syntax, imports, "
        "variables, objective, constraints, numeric issues. Use before solve_job "
        "to catch errors early."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "model_path": {
                "type": "string",
                "description": "Path to the model file to check (Pyomo or cvxpy)",
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

    framework = _detect_framework(code)

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

        if framework == "cvxpy":
            dcp_warnings = _check_dcp_compliance(code)
            all_warnings.extend(dcp_warnings)
        else:
            compat_warnings = _check_solver_compat(code, solver)
            all_warnings.extend(compat_warnings)

        numeric_warnings = _check_numeric(code)
        all_warnings.extend(numeric_warnings)

        if run_test:
            runtime_errors = _run_import_test(code)
            all_errors.extend(runtime_errors)

    out = "## Model Check Results\n\n"
    out += f"**Framework**: {framework}\n\n"

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
