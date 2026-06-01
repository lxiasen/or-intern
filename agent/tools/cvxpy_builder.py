"""cvxpy_builder tool for OR-Intern v1.0.

Generates cvxpy code for convex optimization problems.
Supports: linear, quadratic, SOCP, SDP, and general convex problems.
"""

import logging
import re
from pathlib import Path
from typing import Any

from agent.tools._output_dir import get_workspace_dir, suggest_filename, record_file

logger = logging.getLogger(__name__)

# ── cvxpy code templates ──

CVXPY_SCALAR_VAR = "{name} = cp.Variable(name='{name}')"
CVXPY_VECTOR_VAR = "{name} = cp.Variable({size}, name='{name}')"
CVXPY_MATRIX_VAR = "{name} = cp.Variable(({rows}, {cols}), name='{name}')"
CVXPY_NONNEG_VAR = "{name} = cp.Variable(name='{name}', nonneg=True)"
CVXPY_BINARY_VAR = "{name} = cp.Variable(name='{name}', boolean=True)"
CVXPY_INTEGER_VAR = "{name} = cp.Variable(name='{name}', integer=True)"

CVXPY_TEMPLATE = '''import cvxpy as cp
import numpy as np

# ===== Decision Variables =====
{variables}

# ===== Constraints =====
constraints = [
{constraints}
]

# ===== Objective Function =====
objective = {objective}

# ===== Solve =====
problem = cp.Problem(objective, constraints)
problem.solve(solver="{solver}")

# ===== Results =====
print("STATUS:", problem.status)
print("OPTIMAL VALUE:", problem.value)
{result_output}
'''


def _detect_direction(desc: str) -> str:
    """Detect optimization direction."""
    if re.search(r"minimize|minimise|min\b", desc, re.I):
        return "minimize"
    return "maximize"


def _extract_variables(desc: str) -> dict[str, dict]:
    """Extract variable definitions from description."""
    variables = {}

    var_pattern = re.compile(
        r"(\w+)\s+(?:is\s+)?(?:a\s+)?(?:scalar|vector|matrix|nonneg|binary|integer)?",
        re.I,
    )

    for match in var_pattern.finditer(desc):
        name = match.group(1)
        if name.lower() in ("minimize", "maximize", "subject", "where", "given"):
            continue
        if name not in variables:
            variables[name] = {"type": "scalar", "domain": "real"}

    size_pattern = re.compile(r"(\w+)\s*(?:is|∈)\s*R\^?(\d+)", re.I)
    for match in size_pattern.finditer(desc):
        name = match.group(1)
        size = int(match.group(2))
        variables[name] = {"type": "vector", "size": size, "domain": "real"}

    if not variables:
        for name in re.findall(r"\b([a-zA-Z_]\w*)\b", desc):
            if name.lower() not in ("minimize", "maximize", "subject", "to",
                                      "where", "given", "the", "and", "or",
                                      "constraint", "constraints", "such",
                                      "that", "with", "find", "optimal"):
                if name not in variables and len(name) <= 3 and name.isalpha():
                    variables[name] = {"type": "scalar", "domain": "real"}

    return variables


def _extract_constraints(desc: str) -> list[tuple[str, str, str]]:
    """Extract constraints from description."""
    constraints = []

    st_part = re.split(r"subject to|s\.t\.|such that|where", desc, flags=re.I)
    text = st_part[1] if len(st_part) > 1 else desc

    for part in re.split(r"[,\n;；]", text):
        part = part.strip()
        if not part or part.startswith(("minimize", "maximize")):
            continue

        m = re.search(
            r"([\d\w\s*+.\-^/()]+?)\s*(<=|>=|=|≤|≥)\s*([\d\w\s*+.\-^/()]+)",
            part,
        )
        if m:
            lhs = m.group(1).strip()
            op = m.group(2).replace("≤", "<=").replace("≥", ">=")
            rhs = m.group(3).strip()
            if not any(lhs.startswith(w) for w in ("minimize", "maximize")):
                constraints.append((lhs, op, rhs))

    return constraints


def _extract_objective(desc: str) -> str:
    """Extract objective function expression."""
    m = re.search(
        r"(?:minimize|maximize|min|max)\s*[:]?\s*(.+?)(?:subject to|s\.t\.|such that|\n|$)",
        desc, re.I,
    )
    return m.group(1).strip() if m else "x"


def _convert_to_cvxpy_expr(expr: str, variables: dict) -> str:
    """Convert mathematical expression to cvxpy syntax."""
    result = expr.strip()

    for vname in variables:
        result = re.sub(
            rf"(?<![a-zA-Z_]){re.escape(vname)}(?![a-zA-Z0-9_])",
            vname,
            result,
        )

    result = re.sub(r"(\w+)\s*\^\s*2", r"cp.square(\1)", result)
    result = re.sub(r"(\w+)\s*\^\s*3", r"cp.power(\1, 3)", result)
    result = re.sub(r"\|(\w+)\|", r"cp.norm(\1, 1)", result)
    result = re.sub(r"\|\|(\w+)\|\|", r"cp.norm(\1, 2)", result)

    result = re.sub(r"sqrt\(([^)]+)\)", r"cp.sqrt(\1)", result)
    result = re.sub(r"abs\(([^)]+)\)", r"cp.abs(\1)", result)
    result = re.sub(r"log\(([^)]+)\)", r"cp.log(\1)", result)
    result = re.sub(r"exp\(([^)]+)\)", r"cp.exp(\1)", result)

    return result


def generate_cvxpy_code(description: str, solver: str = "ECOS") -> str:
    """Generate cvxpy code from natural language description."""
    variables = _extract_variables(description)
    constraints = _extract_constraints(description)
    objective_expr = _extract_objective(description)
    direction = _detect_direction(description)

    var_lines = []
    for name, info in variables.items():
        if info["domain"] == "nonneg":
            var_lines.append(CVXPY_NONNEG_VAR.format(name=name))
        elif info["domain"] == "binary":
            var_lines.append(CVXPY_BINARY_VAR.format(name=name))
        elif info["domain"] == "integer":
            var_lines.append(CVXPY_INTEGER_VAR.format(name=name))
        elif info["type"] == "vector":
            var_lines.append(CVXPY_VECTOR_VAR.format(name=name, size=info["size"]))
        elif info["type"] == "matrix":
            var_lines.append(CVXPY_MATRIX_VAR.format(
                name=name, rows=info["rows"], cols=info["cols"]
            ))
        else:
            var_lines.append(CVXPY_SCALAR_VAR.format(name=name))

    constr_lines = []
    for lhs, op, rhs in constraints:
        cvxpy_lhs = _convert_to_cvxpy_expr(lhs, variables)
        cvxpy_rhs = _convert_to_cvxpy_expr(rhs, variables)
        if op == "<=":
            constr_lines.append(f"    {cvxpy_lhs} <= {cvxpy_rhs},")
        elif op == ">=":
            constr_lines.append(f"    {cvxpy_lhs} >= {cvxpy_rhs},")
        elif op == "=":
            constr_lines.append(f"    {cvxpy_lhs} == {cvxpy_rhs},")

    cvxpy_obj = _convert_to_cvxpy_expr(objective_expr, variables)
    if direction == "minimize":
        objective = f"cp.Minimize({cvxpy_obj})"
    else:
        objective = f"cp.Maximize({cvxpy_obj})"

    result_lines = []
    for name in variables:
        result_lines.append(f"print('{name} =', {name}.value)")

    code = CVXPY_TEMPLATE.format(
        variables="\n".join(var_lines),
        constraints="\n".join(constr_lines),
        objective=objective,
        solver=solver,
        result_output="\n".join(result_lines),
    )

    return code


# ── Tool spec and handler ──

CVXPY_BUILDER_TOOL_SPEC = {
    "name": "cvxpy_builder",
    "description": (
        "Generate cvxpy code for convex optimization problems. "
        "Supports: linear programming, quadratic programming, SOCP, SDP, "
        "and general convex problems with automatic DCP compliance checking. "
        "Input: natural language description. Output: cvxpy code file path.\n"
        "Use `filename` to choose a descriptive name. If omitted, auto-versioned."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "description": {
                "type": "string",
                "description": (
                    "Problem description, e.g. "
                    "'minimize x^2 + y^2 subject to x + y >= 1'"
                ),
            },
            "solver": {
                "type": "string",
                "description": "Solver to use: ECOS, SCS, OSQP, MOSEK (default: ECOS)",
                "default": "ECOS",
            },
            "filename": {
                "type": "string",
                "description": "Output filename (e.g., 'model_convex.py'). Auto-versioned if omitted.",
            },
        },
        "required": ["description"],
    },
}


async def cvxpy_builder_handler(args: dict[str, Any], session=None) -> tuple[str, bool]:
    """Handler for cvxpy_builder tool."""
    description = args.get("description", "")
    solver = args.get("solver", "ECOS")
    filename = args.get("filename", "")

    if not description:
        return "Error: No problem description provided", True

    try:
        code = generate_cvxpy_code(description, solver)

        workspace = get_workspace_dir(session)
        if filename:
            model_file = workspace / filename
        else:
            model_file = workspace / suggest_filename(workspace, "model_cvxpy", ".py")
        model_file.write_text(code, encoding="utf-8")
        record_file(workspace, model_file.name, file_type="cvxpy_model",
                     tool="cvxpy_builder", note=description[:60])

        direction = _detect_direction(description)
        variables = _extract_variables(description)
        constraints = _extract_constraints(description)

        result = (
            f"## Convex Optimization Model Generated\n\n"
            f"**Framework**: cvxpy\n"
            f"**Direction**: {direction}\n"
            f"**Variables**: {', '.join(variables.keys())}\n"
            f"**Constraints**: {len(constraints)}\n"
            f"**Solver**: {solver}\n"
            f"**Model file**: {model_file}\n\n"
            f"### DCP Compliance\n\n"
            f"cvxpy enforces DCP (Disciplined Convex Programming) rules. "
            f"If the problem is not convex, cvxpy will raise an error.\n\n"
            f"Now use `solve_job` with model_path='{model_file}' to solve."
        )

        return result, False

    except Exception as e:
        logger.error(f"cvxpy_builder failed: {e}")
        return f"Error building cvxpy model: {e}", True
