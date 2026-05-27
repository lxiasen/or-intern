"""model_builder tool for OR-Intern Phase 1.

Analyzes problem descriptions and generates correct Pyomo model code.
"""

import logging
import re
import time
from pathlib import Path
from typing import Any

from agent.tools._output_dir import get_run_dir

logger = logging.getLogger(__name__)


def _parse_simple_lp(description: str) -> dict:
    """Parse a simple LP/MIP from natural language.

    Handles: 'maximize/minimize AX+BY subject to CX+DY<=E, X>=0, Y>=0'
    """
    desc = description.strip()

    # Direction
    direction = "maximize"
    if re.search(r"minimize|minimise", desc, re.IGNORECASE):
        direction = "minimize"

    # Extract variables from objective
    obj_match = re.search(
        r"(?:maximize|minimize|max|min)\s*[:]?\s*(.+?)(?:subject to|s\.t\.|such that|\n|$)",
        desc, re.IGNORECASE
    )
    obj_expr_raw = obj_match.group(1).strip() if obj_match else "x + y"

    # Extract variable names with coefficients
    var_coeffs = {}
    for m in re.finditer(r'(\d*\.?\d*)\s*\*?\s*([a-zA-Z_]\w*)', obj_expr_raw):
        coeff = float(m.group(1)) if m.group(1) and m.group(1) != '' else 1.0
        name = m.group(2)
        var_coeffs[name] = coeff

    if not var_coeffs:
        var_coeffs = {"x": 1.0, "y": 1.0}

    # Look for integer/binary
    var_types = {}
    for name in var_coeffs:
        if re.search(rf"{name}.*(?:integer|binary|0-1)", desc, re.IGNORECASE):
            var_types[name] = "integer"

    # Extract constraints
    constraints = []
    # Focus on the part after "subject to" or "s.t."
    st_part = re.split(r"subject to|s\.t\.|such that", desc, flags=re.IGNORECASE)
    if len(st_part) > 1:
        constraint_text = st_part[1]
    else:
        constraint_text = desc

    # Split on commas, newlines, or semicolons
    for part in re.split(r'[,\n;；]', constraint_text):
        part = part.strip()
        if not part:
            continue
        # Skip non-constraint lines
        if part.startswith(("maximize", "minimize", "max ", "min ")):
            continue
        const_match = re.search(
            r'([\d\w\s*+.\-]+?)\s*(<=|>=|=|≤|≥)\s*([\d\w\s*+.\-]+)',
            part
        )
        if const_match:
            lhs = const_match.group(1).strip()
            op = const_match.group(2).replace("≤", "<=").replace("≥", ">=")
            rhs = const_match.group(3).strip()
            constraints.append((lhs, op, rhs))

    # If still none, try on the whole string
    if not constraints:
        for match in re.finditer(
            r'([\d\w\s*+.\-]+?)\s*(<=|>=|=)\s*([\d\w\s*+.\-]+)',
            desc
        ):
            lhs = match.group(1).strip()
            op = match.group(2).strip()
            rhs = match.group(3).strip()
            if not any(lhs.strip().startswith(w) for w in ("maximize", "minimize", "max", "min")):
                constraints.append((lhs, op, rhs))

    return {
        "direction": direction,
        "variables": {name: var_types.get(name, "continuous") for name in var_coeffs},
        "coeffs": var_coeffs,
        "constraints": constraints,
    }


def generate_pyomo_code(description: str, solver: str = "highs") -> str:
    """Generate valid Pyomo model code."""
    parsed = _parse_simple_lp(description)

    lines = [
        f"# OR-Intern generated Pyomo model",
        f"from pyomo.environ import *",
        f"",
        f"model = ConcreteModel()",
        f"",
        f"# Variables",
    ]

    for vname, vtype in parsed["variables"].items():
        if vtype == "integer":
            lines.append(f"model.{vname} = Var(domain=NonNegativeIntegers)")
        elif vtype == "binary":
            lines.append(f"model.{vname} = Var(domain=Binary)")
        else:
            lines.append(f"model.{vname} = Var(domain=NonNegativeReals)")

    # Objective
    obj_terms = []
    for vname, coeff in parsed["coeffs"].items():
        if coeff == 1.0:
            obj_terms.append(f"model.{vname}")
        else:
            obj_terms.append(f"{coeff}*model.{vname}")

    obj_expr = " + ".join(obj_terms)
    sense = "maximize" if parsed["direction"] == "maximize" else "minimize"

    lines.append(f"")
    lines.append(f"# Objective: {parsed['direction']} {obj_expr}")
    lines.append(f"model.obj = Objective(expr={obj_expr}, sense={sense})")

    # Constraints
    lines.append(f"")
    lines.append(f"# Constraints")
    for i, (lhs, op, rhs) in enumerate(parsed["constraints"], 1):
        lhs_pyomo = _convert_lhs(lhs, parsed["variables"])
        rhs_pyomo = _convert_rhs(rhs, parsed["variables"])
        lines.append(f"model.c{i} = Constraint(expr={lhs_pyomo} {op} {rhs_pyomo})")

    # Solve
    lines.append(f"")
    lines.append(f"# Solve")
    lines.append(f"solver = SolverFactory('{solver}')")
    lines.append(f"result = solver.solve(model, tee=False)")
    lines.append(f"")
    lines.append(f"# Output")
    lines.append(f'print("STATUS:", result.solver.termination_condition)')
    lines.append(f'print("OBJECTIVE:", value(model.obj))')
    lines.append(f'print("GAP:", getattr(result.problem, "upper_bound", 0) - getattr(result.problem, "lower_bound", 0))')
    lines.append(f'print("LOWER_BOUND:", getattr(result.problem, "lower_bound", "N/A"))')
    lines.append(f'print("UPPER_BOUND:", getattr(result.problem, "upper_bound", "N/A"))')
    lines.append(f'print("SOLVER_TIME:", getattr(result.solver, "time", "N/A"))')
    for vname in parsed["variables"]:
        lines.append(f'print("  {vname} =", value(model.{vname}))')

    return "\n".join(lines)


def _convert_lhs(expr: str, variables: dict) -> str:
    """Convert left-hand side to Pyomo expression."""
    result = expr.strip()
    for vname in variables:
        # Use lookbehind/lookahead instead of \b (which fails on "2x")
        result = re.sub(rf'(?<![a-zA-Z]){re.escape(vname)}(?![a-zA-Z0-9_])', f'model.{vname}', result)
    # Add * between coefficient and model.var
    result = re.sub(r'(\d+)model\.', r'\1*model.', result)
    result = re.sub(r'(\d+\.\d+)model\.', r'\1*model.', result)
    result = result.replace("model.model.", "model.")
    return result


def _convert_rhs(expr: str, variables: dict) -> str:
    """Convert right-hand side to Pyomo expression."""
    result = expr.strip()
    for vname in variables:
        result = re.sub(rf'(?<![a-zA-Z]){re.escape(vname)}(?![a-zA-Z0-9_])', f'model.{vname}', result)
    return result


# ── Tool spec and handler ──

MODEL_BUILDER_TOOL_SPEC = {
    "name": "model_builder",
    "description": (
        "Generate a Pyomo optimization model from a problem description. "
        "Input: natural language description of LP/MIP problem. "
        "Output: Pyomo code file path. Then use solve_job to execute."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "description": {
                "type": "string",
                "description": "Problem description, e.g. 'maximize 3x+2y subject to x+y<=10, x>=0, y>=0'",
            },
            "solver": {
                "type": "string",
                "description": "Solver to use (default: highs)",
                "default": "highs",
            },
        },
        "required": ["description"],
    },
}


async def model_builder_handler(args: dict[str, Any]) -> tuple[str, bool]:
    """Handler: analyze problem and write Pyomo model."""
    description = args.get("description", "")
    solver = args.get("solver", "highs")

    if not description:
        return "Error: No problem description provided", True

    try:
        parsed = _parse_simple_lp(description)
        code = generate_pyomo_code(description, solver)

        # Write model file to run directory
        rundir = get_run_dir()
        model_file = rundir / "model.py"
        model_file.write_text(code, encoding="utf-8")

        result = (
            f"## Model Generated\n\n"
            f"**Problem type**: {'MIP' if any(v == 'integer' for v in parsed['variables'].values()) else 'LP'}\n"
            f"**Objective**: {parsed['direction']}\n"
            f"**Variables**: {', '.join(parsed['variables'])}\n"
            f"**Constraints**: {len(parsed['constraints'])}\n"
            f"**Model file**: {model_file}\n\n"
            f"Now use `solve_job` with model_path='{model_file}' to solve."
        )
        return result, False

    except Exception as e:
        logger.error(f"model_builder failed: {e}")
        return f"Error building model: {e}", True
