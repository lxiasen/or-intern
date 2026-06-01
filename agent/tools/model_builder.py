"""model_builder tool for OR-Intern v0.5.

Generates Pyomo model code from natural language problem descriptions.
Supports LP, MIP, SOS1/SOS2, semi-continuous, indicator, and piecewise constraints.
"""

import logging
import re
import time
from pathlib import Path
from typing import Any

from agent.tools._output_dir import get_workspace_dir, suggest_filename, record_file

logger = logging.getLogger(__name__)

VAR_TYPE_PATTERNS = {
    "binary": re.compile(r"\bbinary\b|0-1\s*integer|{0,\s*1}", re.I),
    "integer": re.compile(r"\binteger\b|\bint\b", re.I),
    "semi_continuous": re.compile(r"\bsemi[- ]?continuous\b|\bsemi[- ]?cont\b", re.I),
    "sos1": re.compile(r"\bSOS[- ]?1\b|special ordered set\s*1", re.I),
    "sos2": re.compile(r"\bSOS[- ]?2\b|special ordered set\s*2", re.I),
}

INDICATOR_RE = re.compile(
    r"(?:if|when)\s+(\w+)\s*(?:==|=|is)\s*(\d+)\s+then\s+(.+?)(?:;|$)",
    re.I,
)

PIECEWISE_RE = re.compile(
    r"piecewise\s*\(\s*\[(.+?)\]\s*,\s*\[(.+?)\]\s*,\s*(\w+)\s*\)",
    re.I,
)

SOS_RE = re.compile(
    r"(SOS[- ]?[12])\s*\(\s*\[([^\]]+)\]\s*(?:,\s*weights?\s*=\s*\[([^\]]*)\])?\s*\)",
    re.I,
)


def _detect_direction(desc: str) -> str:
    if re.search(r"minimize|minimise", desc, re.I):
        return "minimize"
    return "maximize"


# ── Problem type detection (v1.0: NLP/Convex support) ──

NONLINEAR_PATTERNS = [
    re.compile(r"\b\w+\s*\^\s*[2-9]"),  # x^2, y^3
    re.compile(r"\b\w+\s*\*\*\s*[2-9]"),  # x**2, y**3
    re.compile(r"\b(sin|cos|tan|exp|log|sqrt|abs)\b", re.I),  # Math functions
    re.compile(r"\b\w+\s*\^\s*2"),  # x^2 specifically
]

CONVEX_KEYWORDS = ["minimize", "convex", "quadratic", "norm", "least squares", "qp", "square"]
SOCP_KEYWORDS = ["second order cone", "socp", "norm2", "norm2("]
SDP_KEYWORDS = ["semidefinite", "sdp", "positive semidefinite"]


def detect_problem_type(description: str) -> str:
    """Detect problem type: LP, MIP, NLP, Convex, SOCP, SDP.

    Returns:
        Problem type string
    """
    desc_lower = description.lower()

    if any(kw in desc_lower for kw in SDP_KEYWORDS):
        return "SDP"
    if any(kw in desc_lower for kw in SOCP_KEYWORDS):
        return "SOCP"

    has_nonlinear = any(p.search(desc_lower) for p in NONLINEAR_PATTERNS)

    if has_nonlinear:
        is_likely_convex = any(kw in desc_lower for kw in CONVEX_KEYWORDS)
        if is_likely_convex:
            return "Convex"
        return "NLP"

    _, coeffs = _extract_objective(description)
    var_types = _detect_var_types(description, list(coeffs.keys()))
    is_mip = any(v != "continuous" for v in var_types.values())

    if is_mip:
        return "MIP"
    return "LP"


def recommend_framework(problem_type: str) -> tuple[str, str]:
    """Recommend modeling framework and solver for problem type.

    Returns:
        (framework, solver) tuple
    """
    recommendations = {
        "LP": ("pyomo", "highs"),
        "MIP": ("pyomo", "highs"),
        "NLP": ("pyomo", "ipopt"),
        "Convex": ("cvxpy", "ECOS"),
        "SOCP": ("cvxpy", "ECOS"),
        "SDP": ("cvxpy", "SCS"),
        "QP": ("cvxpy", "OSQP"),
    }
    return recommendations.get(problem_type, ("pyomo", "highs"))


def _extract_objective(desc: str) -> tuple[str, dict[str, float]]:
    m = re.search(
        r"(?:maximize|minimize|max|min)\s*[:]?\s*(.+?)(?:subject to|s\.t\.|such that|\n|$)",
        desc, re.I,
    )
    raw = m.group(1).strip() if m else "x + y"
    coeffs: dict[str, float] = {}
    for m in re.finditer(r"(\d*\.?\d*)\s*\*?\s*([a-zA-Z_]\w*)", raw):
        c = float(m.group(1)) if m.group(1) and m.group(1) != "" else 1.0
        coeffs[m.group(2)] = c
    if not coeffs:
        coeffs = {"x": 1.0, "y": 1.0}
    return raw, coeffs


def _detect_var_types(desc: str, var_names: list[str]) -> dict[str, str]:
    types: dict[str, str] = {}
    clauses = re.split(r"[,;]", desc)
    for name in var_names:
        for vtype, pat in VAR_TYPE_PATTERNS.items():
            found = False
            for clause in clauses:
                if re.search(rf"\b{re.escape(name)}\b", clause) and pat.search(clause):
                    found = True
                    break
            if found:
                types[name] = vtype
                break
        if name not in types:
            types[name] = "continuous"
    return types


def _extract_constraints(desc: str) -> list[tuple[str, str, str]]:
    st_part = re.split(r"subject to|s\.t\.|such that", desc, flags=re.I)
    text = st_part[1] if len(st_part) > 1 else desc
    constraints: list[tuple[str, str, str]] = []
    for part in re.split(r"[,\n;；]", text):
        part = part.strip()
        if not part or part.startswith(("maximize", "minimize", "max ", "min ")):
            continue
        m = re.search(
            r"([\d\w\s*+.\-]+?)\s*(<=|>=|=|≤|≥)\s*([\d\w\s*+.\-]+)", part
        )
        if m:
            lhs = m.group(1).strip()
            op = m.group(2).replace("≤", "<=").replace("≥", ">=")
            rhs = m.group(3).strip()
            if not any(lhs.startswith(w) for w in ("maximize", "minimize", "max", "min")):
                constraints.append((lhs, op, rhs))
    return constraints


def _extract_indicators(desc: str) -> list[dict]:
    indicators = []
    for m in INDICATOR_RE.finditer(desc):
        indicators.append({
            "var": m.group(1),
            "val": int(m.group(2)),
            "constraint": m.group(3).strip(),
        })
    return indicators


def _extract_piecewise(desc: str) -> list[dict]:
    pieces = []
    for m in PIECEWISE_RE.finditer(desc):
        breakpoints = [float(x.strip()) for x in m.group(1).split(",")]
        values = [float(x.strip()) for x in m.group(2).split(",")]
        var_name = m.group(3)
        pieces.append({
            "breakpoints": breakpoints,
            "values": values,
            "var": var_name,
        })
    return pieces


def _extract_sos(desc: str) -> list[dict]:
    sos_list = []
    for m in SOS_RE.finditer(desc):
        sos_type = "SOS1" if "1" in m.group(1).upper() else "SOS2"
        vars_str = m.group(2)
        var_names = [v.strip().strip("'\"") for v in vars_str.split(",")]
        weights = None
        if m.group(3):
            weights = [float(w.strip()) for w in m.group(3).split(",")]
        sos_list.append({
            "type": sos_type,
            "vars": var_names,
            "weights": weights,
        })
    return sos_list


def _convert_lhs(expr: str, variables: dict) -> str:
    result = expr.strip()
    for vname in variables:
        result = re.sub(
            rf"(?<![a-zA-Z]){re.escape(vname)}(?![a-zA-Z0-9_])",
            f"model.{vname}",
            result,
        )
    result = re.sub(r"(\d+)model\.", r"\1*model.", result)
    result = re.sub(r"(\d+\.\d+)model\.", r"\1*model.", result)
    return result.replace("model.model.", "model.")


def _convert_rhs(expr: str, variables: dict) -> str:
    result = expr.strip()
    for vname in variables:
        result = re.sub(
            rf"(?<![a-zA-Z]){re.escape(vname)}(?![a-zA-Z0-9_])",
            f"model.{vname}",
            result,
        )
    return result


def generate_pyomo_code(description: str, solver: str = "highs") -> str:
    """Generate valid Pyomo model code with advanced MIP support."""
    direction = _detect_direction(description)
    _, coeffs = _extract_objective(description)
    var_names = list(coeffs.keys())
    var_types = _detect_var_types(description, var_names)
    constraints = _extract_constraints(description)
    indicators = _extract_indicators(description)
    piecewise = _extract_piecewise(description)
    sos_list = _extract_sos(description)

    lines = [
        "# OR-Intern generated Pyomo model",
        "from pyomo.environ import *",
        "import pyomo.kernel as pmo",
        "",
        "model = ConcreteModel()",
        "",
        "# Variables",
    ]

    for vname in var_names:
        vtype = var_types.get(vname, "continuous")
        if vtype == "binary":
            lines.append(f"model.{vname} = Var(domain=Binary)")
        elif vtype == "integer":
            lines.append(f"model.{vname} = Var(domain=NonNegativeIntegers)")
        elif vtype == "semi_continuous":
            lines.append(f"model.{vname} = Var(domain=NonNegativeReals, bounds=(0, None))")
            lines.append(f"# NOTE: {vname} is semi-continuous — must be 0 or in [lb, ub]")
            lines.append(f"# User should set explicit bounds: model.{vname}.setlb(lb)")
        elif vtype == "sos1":
            lines.append(f"model.{vname} = Var(domain=NonNegativeReals)")
        elif vtype == "sos2":
            lines.append(f"model.{vname} = Var(domain=NonNegativeReals)")
        else:
            lines.append(f"model.{vname} = Var(domain=NonNegativeReals)")

    obj_terms = []
    for vname, coeff in coeffs.items():
        if coeff == 1.0:
            obj_terms.append(f"model.{vname}")
        else:
            obj_terms.append(f"{coeff}*model.{vname}")
    obj_expr = " + ".join(obj_terms)
    sense = "maximize" if direction == "maximize" else "minimize"

    lines.append("")
    lines.append(f"# Objective: {direction} {obj_expr}")
    lines.append(f"model.obj = Objective(expr={obj_expr}, sense={sense})")

    lines.append("")
    lines.append("# Constraints")
    for i, (lhs, op, rhs) in enumerate(constraints, 1):
        lhs_pyomo = _convert_lhs(lhs, var_types)
        rhs_pyomo = _convert_rhs(rhs, var_types)
        pyomo_op = "==" if op == "=" else op
        lines.append(f"model.c{i} = Constraint(expr={lhs_pyomo} {pyomo_op} {rhs_pyomo})")

    if indicators:
        lines.append("")
        lines.append("# Indicator constraints")
        for i, ind in enumerate(indicators, 1):
            c_text = ind["constraint"]
            c_lhs_match = re.search(
                r"([\d\w\s*+.\-]+?)\s*(<=|>=|=|≤|≥)\s*([\d\w\s*+.\-]+)", c_text
            )
            if c_lhs_match:
                c_lhs = _convert_lhs(c_lhs_match.group(1), var_types)
                c_op = c_lhs_match.group(2).replace("≤", "<=").replace("≥", ">=")
                c_rhs = _convert_rhs(c_lhs_match.group(3), var_types)
                lines.append(f"model.ind_c{i} = Constraint(expr=")
                lines.append(f"    {c_lhs} {c_op} {c_rhs}")
                lines.append(f"    if model.{ind['var']} == {ind['val']} else True")
                lines.append(f")")

    if piecewise:
        lines.append("")
        lines.append("# Piecewise constraints")
        for i, pw in enumerate(piecewise, 1):
            bp_str = ", ".join(str(b) for b in pw["breakpoints"])
            val_str = ", ".join(str(v) for v in pw["values"])
            lines.append(f"model.pw_x{i} = Var()")
            lines.append(f"model.pw_y{i} = Var()")
            lines.append(f"model.pw{i} = Piecewise(")
            lines.append(f"    model.pw_y{i}, model.pw_x{i},")
            lines.append(f"    pw_pts=[{bp_str}],")
            lines.append(f"    f_rule=[{val_str}],")
            lines.append(f"    pw_constr_type='EQ',")
            lines.append(f")")

    if sos_list:
        lines.append("")
        lines.append("# SOS constraints")
        for i, sos in enumerate(sos_list, 1):
            vars_str = ", ".join(f"model.{v}" for v in sos["vars"])
            if sos["weights"]:
                w_str = ", ".join(str(w) for w in sos["weights"])
                lines.append(f"model.sos{i} = SOSConstraint(")
                lines.append(f"    var=[{vars_str}],")
                lines.append(f"    sos={1 if sos['type'] == 'SOS1' else 2},")
                lines.append(f"    weights=[{w_str}]")
                lines.append(f")")
            else:
                lines.append(f"model.sos{i} = SOSConstraint(")
                lines.append(f"    var=[{vars_str}],")
                lines.append(f"    sos={1 if sos['type'] == 'SOS1' else 2}")
                lines.append(f")")

    lines.append("")
    lines.append("# Solve")
    lines.append(f"solver = SolverFactory('{solver}')")
    lines.append(f"result = solver.solve(model, tee=False)")
    lines.append("")
    lines.append("# Output")
    lines.append('print("STATUS:", result.solver.termination_condition)')
    lines.append('print("OBJECTIVE:", value(model.obj))')
    lines.append('print("GAP:", getattr(result.problem, "upper_bound", 0) - getattr(result.problem, "lower_bound", 0))')
    lines.append('print("LOWER_BOUND:", getattr(result.problem, "lower_bound", "N/A"))')
    lines.append('print("UPPER_BOUND:", getattr(result.problem, "upper_bound", "N/A"))')
    lines.append('print("SOLVER_TIME:", getattr(result.solver, "time", "N/A"))')
    for vname in var_names:
        lines.append(f'print("  {vname} =", value(model.{vname}))')

    return "\n".join(lines)


# ── Tool spec and handler ──

MODEL_BUILDER_TOOL_SPEC = {
    "name": "model_builder",
    "description": (
        "Generate a Pyomo optimization model from a problem description. "
        "Supports LP, MIP, binary, integer, semi-continuous, SOS1/SOS2, "
        "indicator constraints, and piecewise functions. "
        "Input: natural language description. Output: Pyomo code file path.\n"
        "Use `filename` to choose a descriptive name (e.g., 'model_v1.py', "
        "'model_relaxed.py'). If omitted, an auto-versioned name is used."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "description": {
                "type": "string",
                "description": (
                    "Problem description, e.g. "
                    "'maximize 3x+2y subject to x+y<=10, x>=0, y>=0'"
                ),
            },
            "solver": {
                "type": "string",
                "description": "Solver to use (default: highs)",
                "default": "highs",
            },
            "filename": {
                "type": "string",
                "description": (
                    "Output filename (e.g., 'model_v1.py', 'model_production.py'). "
                    "If omitted, auto-versioned name is used."
                ),
            },
        },
        "required": ["description"],
    },
}


async def model_builder_handler(args: dict[str, Any], session=None) -> tuple[str, bool]:
    """Handler: analyze problem and write Pyomo model."""
    description = args.get("description", "")
    solver = args.get("solver") or (session.config.solver.default)
    filename = args.get("filename", "")

    if not description:
        return "Error: No problem description provided", True

    try:
        problem_type = detect_problem_type(description)
        framework, recommended_solver = recommend_framework(problem_type)

        if solver == "highs" and recommended_solver != "highs":
            solver = recommended_solver

        if framework == "cvxpy":
            from agent.tools.cvxpy_builder import cvxpy_builder_handler
            if not filename:
                args["filename"] = ""
            return await cvxpy_builder_handler(args, session=session)

        _, coeffs = _extract_objective(description)
        var_names = list(coeffs.keys())
        var_types = _detect_var_types(description, var_names)
        constraints = _extract_constraints(description)
        indicators = _extract_indicators(description)
        sos_list = _extract_sos(description)
        piecewise = _extract_piecewise(description)

        code = generate_pyomo_code(description, solver)

        workspace = get_workspace_dir(session)
        if filename:
            model_file = workspace / filename
        else:
            model_file = workspace / suggest_filename(workspace, "model", ".py")
        model_file.write_text(code, encoding="utf-8")

        verify_result = _verify_model(model_file, code)

        record_file(workspace, model_file.name, file_type="pyomo_model",
                     tool="model_builder", note=f"{problem_type}: {description[:60]}")

        detected_types = {k: v for k, v in var_types.items() if v != "continuous"}
        type_str = ", ".join(f"{k}={v}" for k, v in detected_types.items()) or "all continuous"

        features = []
        if detected_types:
            features.append(f"Advanced types: {type_str}")
        if indicators:
            features.append(f"Indicator constraints: {len(indicators)}")
        if sos_list:
            features.append(f"SOS constraints: {len(sos_list)}")
        if piecewise:
            features.append(f"Piecewise functions: {len(piecewise)}")

        result = (
            f"## Model Generated\n\n"
            f"**Problem type**: {problem_type}\n"
            f"**Framework**: {framework}\n"
            f"**Objective**: {direction if (direction := _detect_direction(description)) else 'maximize'}\n"
            f"**Variables**: {', '.join(var_names)}\n"
            f"**Constraints**: {len(constraints)}\n"
        )
        if features:
            result += f"**Features**: {'; '.join(features)}\n"
        result += f"**Model file**: {model_file}\n"

        if verify_result:
            result += f"\n**Verification**: {verify_result}\n"
            result += "The model has issues. Use `model_checker` for details, then fix before solving.\n"
        else:
            result += "\n**Verification**: Passed (syntax + import test OK)\n"

        result += f"\nNow use `solve_job` with model_path='{model_file}' to solve."

        return result, False

    except Exception as e:
        logger.error(f"model_builder failed: {e}")
        return f"Error building model: {e}", True


def _verify_model(model_file: Path, code: str) -> str | None:
    """Run quick verification on generated model code.

    Returns error description if verification fails, None if OK.
    """
    from agent.tools.model_checker import _check_syntax, _run_import_test

    syntax_errors = _check_syntax(code)
    if syntax_errors:
        return f"Syntax error: {syntax_errors[0]}"

    runtime_errors = _run_import_test(code)
    if runtime_errors:
        return f"Import/runtime error: {runtime_errors[0]}"

    return None
