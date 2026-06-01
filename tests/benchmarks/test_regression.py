"""Regression test suite for OR-Intern.

Deterministic tests that verify tool chain correctness without LLM calls.
Covers: model generation, type detection, solver selection, model checking,
template matching, data handling, and edge cases.

Run: uv run pytest tests/benchmarks/test_regression.py -v
"""

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


# ═══════════════════════════════════════════════════════════════════════
# 1. Problem Type Detection
# ═══════════════════════════════════════════════════════════════════════

TYPE_DETECTION_CASES = [
    ("maximize x + y subject to x + y <= 10, x >= 0, y >= 0", "LP"),
    ("maximize 3x + 2y subject to x + y <= 5, x binary, y binary", "MIP"),
    ("minimize x^2 + y^2 subject to x + y >= 1", "Convex"),
    ("maximize sin(x) + cos(y) subject to x >= 0", "NLP"),
    ("minimize norm2(x) subject to x >= 0", "SOCP"),
    ("minimize x + y subject to x >= 0, y integer", "MIP"),
    ("minimize x + y subject to x >= 0, y binary", "MIP"),
    ("maximize 10x + 15y subject to 2x + 3y <= 100, x >= 0, y >= 0", "LP"),
    ("minimize 4a + 3b subject to 2a + b >= 10, a + 2b >= 8, a >= 0, b >= 0", "LP"),
    ("maximize x1 + x2 + x3 subject to x1 + x2 + x3 <= 100, x1 >= 0, x2 >= 0, x3 >= 0", "LP"),
]


class TestProblemTypeDetection:

    @pytest.mark.parametrize("desc,expected_type", TYPE_DETECTION_CASES,
                             ids=[c[0][:50] for c in TYPE_DETECTION_CASES])
    def test_detect_problem_type(self, desc, expected_type):
        from agent.tools.model_builder import detect_problem_type
        result = detect_problem_type(desc)
        assert result == expected_type, f"Expected {expected_type}, got {result} for: {desc}"


# ═══════════════════════════════════════════════════════════════════════
# 2. Model Code Generation — Syntax Validity
# ═══════════════════════════════════════════════════════════════════════

LP_PROBLEMS = [
    "maximize x + y subject to x + y <= 10, x >= 0, y >= 0",
    "maximize 5x + 3y subject to 2x + y <= 20, x + 3y <= 30, x >= 0, y >= 0",
    "minimize 4x + 6y subject to x + 2y >= 8, 3x + 2y >= 12, x >= 0, y >= 0",
    "maximize 10a + 15b subject to 2a + 3b <= 100, 4a + 2b <= 120, a >= 0, b >= 0",
    "minimize 2f1 + 3f2 + f3 subject to f1 + f2 + f3 >= 10, 2f1 + f2 >= 15, f1 >= 0, f2 >= 0, f3 >= 0",
    "maximize 3x + 2y + z subject to x + y + z <= 20, 2x + y <= 15, x >= 0, y >= 0, z >= 0",
    "minimize x + y subject to x >= 5, y >= 3, x + y >= 10",
    "maximize 7x + 5y subject to 3x + 2y <= 18, x <= 4, y <= 6, x >= 0, y >= 0",
]

MIP_PROBLEMS = [
    "maximize 60*x1 + 100*x2 + 120*x3 subject to 10*x1 + 20*x2 + 30*x3 <= 50, x1 binary, x2 binary, x3 binary",
    "maximize 5x + 4y subject to 2x + 3y <= 12, x integer, y integer, x >= 0, y >= 0",
    "maximize x + y + z subject to x + y + z <= 10, x binary, y binary, z binary",
    "minimize 4*a + 2*b + 8*c subject to a + b + c >= 5, a binary, b binary, c binary",
]

ALL_GENERATION_PROBLEMS = LP_PROBLEMS + MIP_PROBLEMS


class TestModelCodeGeneration:

    @pytest.mark.parametrize("desc", ALL_GENERATION_PROBLEMS,
                             ids=[d[:50] for d in ALL_GENERATION_PROBLEMS])
    def test_generates_valid_python(self, desc):
        from agent.tools.model_builder import generate_pyomo_code
        code = generate_pyomo_code(desc)
        compile(code, "<test>", "exec")

    @pytest.mark.parametrize("desc", ALL_GENERATION_PROBLEMS,
                             ids=[d[:50] for d in ALL_GENERATION_PROBLEMS])
    def test_has_required_components(self, desc):
        from agent.tools.model_builder import generate_pyomo_code
        code = generate_pyomo_code(desc)
        assert "ConcreteModel" in code, "Missing ConcreteModel"
        assert "Objective" in code, "Missing Objective"
        assert "from pyomo.environ import" in code, "Missing pyomo import"

    @pytest.mark.parametrize("desc", LP_PROBLEMS,
                             ids=[d[:50] for d in LP_PROBLEMS])
    def test_lp_has_variables(self, desc):
        from agent.tools.model_builder import generate_pyomo_code
        code = generate_pyomo_code(desc)
        assert "Var(" in code, "No variables declared"

    @pytest.mark.parametrize("desc", MIP_PROBLEMS,
                             ids=[d[:50] for d in MIP_PROBLEMS])
    def test_mip_has_integer_or_binary(self, desc):
        from agent.tools.model_builder import generate_pyomo_code
        code = generate_pyomo_code(desc)
        has_binary = "Binary" in code
        has_integer = "Integer" in code or "NonNegativeIntegers" in code
        assert has_binary or has_integer, f"Neither Binary nor Integer in: {code[:300]}"


# ═══════════════════════════════════════════════════════════════════════
# 3. Objective Direction Detection
# ═══════════════════════════════════════════════════════════════════════

class TestDirectionDetection:

    def test_maximize(self):
        from agent.tools.model_builder import _detect_direction
        assert _detect_direction("maximize x + y") == "maximize"

    def test_minimize(self):
        from agent.tools.model_builder import _detect_direction
        assert _detect_direction("minimize x + y") == "minimize"

    def test_default_maximize(self):
        from agent.tools.model_builder import _detect_direction
        assert _detect_direction("x + y subject to x <= 5") == "maximize"

    def test_british_spelling(self):
        from agent.tools.model_builder import _detect_direction
        assert _detect_direction("minimise cost") == "minimize"


# ═══════════════════════════════════════════════════════════════════════
# 4. Constraint Extraction
# ═══════════════════════════════════════════════════════════════════════

class TestConstraintExtraction:

    def test_simple_inequality(self):
        from agent.tools.model_builder import _extract_constraints
        constraints = _extract_constraints(
            "maximize x + y subject to x + y <= 10, x >= 0, y >= 0"
        )
        assert len(constraints) >= 1
        ops = [c[1] for c in constraints]
        assert "<=" in ops or ">=" in ops

    def test_multiple_constraints(self):
        from agent.tools.model_builder import _extract_constraints
        constraints = _extract_constraints(
            "maximize 3x + 2y subject to 2x + y <= 20, x + 3y <= 30, x >= 0, y >= 0"
        )
        assert len(constraints) >= 2

    def test_no_subject_to(self):
        from agent.tools.model_builder import _extract_constraints
        constraints = _extract_constraints("x + y <= 10, x >= 0")
        assert len(constraints) >= 1


# ═══════════════════════════════════════════════════════════════════════
# 5. Solver Selection
# ═══════════════════════════════════════════════════════════════════════

SOLVER_RECOMMENDATION_CASES = [
    ("LP", "small", "highs"),
    ("MIP", "small", "highs"),
    ("MIP", "large", "highs"),
    ("LP", "large", "highs"),
    ("NLP", "small", "ipopt"),
]


class TestSolverSelection:

    @pytest.mark.parametrize("ptype,size,expected_solver",
                             SOLVER_RECOMMENDATION_CASES,
                             ids=[f"{t[0]}_{t[1]}" for t in SOLVER_RECOMMENDATION_CASES])
    def test_recommend_solver(self, ptype, size, expected_solver):
        from agent.tools.solver_selector import recommend_solver
        rec = recommend_solver(ptype, size=size)
        assert rec["solver"] == expected_solver

    def test_list_solvers(self):
        from agent.tools.solver_selector import _SOLVERS
        assert "highs" in _SOLVERS
        assert "scip" in _SOLVERS
        assert "gurobi" in _SOLVERS
        assert "ipopt" in _SOLVERS

    def test_open_source_vs_commercial(self):
        from agent.tools.solver_selector import _SOLVERS
        for name, solver in _SOLVERS.items():
            assert solver["type"] in ("open_source", "commercial")

    def test_problem_size_detection(self):
        from agent.tools.solver_selector import _detect_problem_size
        assert _detect_problem_size("small problem with 10 variables") == "small"
        assert _detect_problem_size("large problem with thousands of variables") == "large"
        assert _detect_problem_size("medium problem with hundreds of items") == "medium"


# ═══════════════════════════════════════════════════════════════════════
# 6. Problem Template System
# ═══════════════════════════════════════════════════════════════════════

TEMPLATE_NAMES = [
    "tsp", "knapsack", "facility_location", "transportation",
    "blending", "portfolio", "workforce_scheduling", "vrp",
    "job_shop", "network_flow", "set_cover", "bin_packing",
    "production_planning", "assignment", "scheduling",
]


class TestTemplateSystem:

    @pytest.mark.parametrize("name", TEMPLATE_NAMES, ids=TEMPLATE_NAMES)
    def test_template_exists(self, name):
        from agent.tools.templates import TEMPLATES
        assert name in TEMPLATES, f"Template '{name}' not found"

    @pytest.mark.parametrize("name", TEMPLATE_NAMES, ids=TEMPLATE_NAMES)
    def test_template_generates_valid_python(self, name):
        from agent.tools.templates import TEMPLATES, generate_from_template
        tpl = TEMPLATES[name]
        code = generate_from_template(name, {})
        assert len(code) > 100, f"Template '{name}' generated too little code"
        compile(code, "<test>", "exec")

    def test_match_tsp(self):
        from agent.tools.templates import match_template
        result = match_template("Find the shortest route visiting all cities")
        assert result == "tsp"

    def test_match_knapsack(self):
        from agent.tools.templates import match_template
        result = match_template("0-1 knapsack problem with items and capacity")
        assert result == "knapsack"

    def test_match_no_match(self):
        from agent.tools.templates import match_template
        result = match_template("compute the fibonacci sequence")
        assert result is None

    def test_list_templates(self):
        from agent.tools.templates import list_templates
        output = list_templates()
        assert "tsp" in output.lower()
        assert "knapsack" in output.lower()


# ═══════════════════════════════════════════════════════════════════════
# 7. Model Checker
# ═══════════════════════════════════════════════════════════════════════

VALID_PYOMO_MODEL = '''\
from pyomo.environ import *
model = ConcreteModel()
model.x = Var(domain=NonNegativeReals)
model.y = Var(domain=NonNegativeReals)
model.obj = Objective(expr=3*model.x + 2*model.y, sense=maximize)
model.c1 = Constraint(expr=model.x + model.y <= 10)
'''

INVALID_SYNTAX_MODEL = '''\
from pyomo.environ import *
model = ConcreteModel(
model.x = Var(domain=NonNegativeReals)
'''

MISSING_OBJECTIVE_MODEL = '''\
from pyomo.environ import *
model = ConcreteModel()
model.x = Var(domain=NonNegativeReals)
model.c1 = Constraint(expr=model.x <= 10)
'''


class TestModelChecker:

    @pytest.mark.asyncio
    async def test_valid_model_passes(self, tmp_path):
        from agent.tools.model_checker import model_checker_handler
        model_file = tmp_path / "valid_model.py"
        model_file.write_text(VALID_PYOMO_MODEL, encoding="utf-8")
        output, is_error = await model_checker_handler({
            "model_path": str(model_file), "run_import_test": False,
        })
        assert not is_error
        assert "ERROR" not in output or "0 error" in output.lower()

    @pytest.mark.asyncio
    async def test_syntax_error_detected(self, tmp_path):
        from agent.tools.model_checker import model_checker_handler
        model_file = tmp_path / "bad_syntax.py"
        model_file.write_text(INVALID_SYNTAX_MODEL, encoding="utf-8")
        output, is_error = await model_checker_handler({
            "model_path": str(model_file), "run_import_test": False,
        })
        assert "syntax" in output.lower() or "error" in output.lower()

    @pytest.mark.asyncio
    async def test_missing_objective_detected(self, tmp_path):
        from agent.tools.model_checker import model_checker_handler
        model_file = tmp_path / "no_obj.py"
        model_file.write_text(MISSING_OBJECTIVE_MODEL, encoding="utf-8")
        output, is_error = await model_checker_handler({
            "model_path": str(model_file), "run_import_test": False,
        })
        assert "objective" in output.lower() or "warning" in output.lower()

    @pytest.mark.asyncio
    async def test_missing_file(self):
        from agent.tools.model_checker import model_checker_handler
        output, is_error = await model_checker_handler({
            "model_path": "/nonexistent/model.py",
        })
        assert is_error

    @pytest.mark.asyncio
    async def test_empty_file(self, tmp_path):
        from agent.tools.model_checker import model_checker_handler
        model_file = tmp_path / "empty.py"
        model_file.write_text("", encoding="utf-8")
        output, is_error = await model_checker_handler({
            "model_path": str(model_file),
        })
        assert is_error


# ═══════════════════════════════════════════════════════════════════════
# 8. Framework Detection (Pyomo vs cvxpy)
# ═══════════════════════════════════════════════════════════════════════

class TestFrameworkDetection:

    def test_detect_pyomo(self):
        from agent.tools.model_checker import _detect_framework
        assert _detect_framework("from pyomo.environ import *") == "pyomo"

    def test_detect_cvxpy(self):
        from agent.tools.model_checker import _detect_framework
        assert _detect_framework("import cvxpy as cp") == "cvxpy"

    def test_default_pyomo(self):
        from agent.tools.model_checker import _detect_framework
        assert _detect_framework("x = 1") == "pyomo"


# ═══════════════════════════════════════════════════════════════════════
# 9. Data Handler
# ═══════════════════════════════════════════════════════════════════════

class TestDataHandler:

    @pytest.mark.asyncio
    async def test_csv_inspect(self, tmp_path):
        from agent.tools.data_handler import data_handler_handler
        csv_file = tmp_path / "data.csv"
        csv_file.write_text("name,weight,value\nA,10,60\nB,20,100\nC,30,120\n",
                            encoding="utf-8")
        output, is_error = await data_handler_handler({
            "file_path": str(csv_file), "operation": "inspect",
        })
        assert not is_error
        assert "tabular" in output.lower() or "rows" in output.lower()

    @pytest.mark.asyncio
    async def test_json_inspect(self, tmp_path):
        from agent.tools.data_handler import data_handler_handler
        json_file = tmp_path / "data.json"
        json_file.write_text('[{"x": 1, "y": 2}, {"x": 3, "y": 4}]',
                             encoding="utf-8")
        output, is_error = await data_handler_handler({
            "file_path": str(json_file), "operation": "inspect",
        })
        assert not is_error
        assert "list" in output.lower() or "items" in output.lower()

    @pytest.mark.asyncio
    async def test_missing_file(self):
        from agent.tools.data_handler import data_handler_handler
        output, is_error = await data_handler_handler({
            "file_path": "/nonexistent/data.csv",
        })
        assert is_error

    @pytest.mark.asyncio
    async def test_unsupported_format(self, tmp_path):
        from agent.tools.data_handler import data_handler_handler
        bad_file = tmp_path / "data.xyz"
        bad_file.write_text("some data", encoding="utf-8")
        output, is_error = await data_handler_handler({
            "file_path": str(bad_file),
        })
        assert is_error

    @pytest.mark.asyncio
    async def test_csv_convert(self, tmp_path):
        from agent.tools.data_handler import data_handler_handler
        csv_file = tmp_path / "data.csv"
        csv_file.write_text("a,b\n1,2\n3,4\n", encoding="utf-8")
        output, is_error = await data_handler_handler({
            "file_path": str(csv_file), "operation": "convert",
        })
        assert not is_error


# ═══════════════════════════════════════════════════════════════════════
# 10. Visualization
# ═══════════════════════════════════════════════════════════════════════

class TestVisualization:

    @pytest.mark.asyncio
    async def test_variable_chart(self):
        from agent.tools.visualization import visualization_handler
        output, is_error = await visualization_handler({
            "variables": {"x": 10.0, "y": 5.0},
            "objective": 50.0,
            "chart_type": "variables",
        })
        if is_error and "matplotlib" in str(output):
            pytest.skip("matplotlib not installed")
        assert not is_error

    @pytest.mark.asyncio
    async def test_sensitivity_chart(self):
        from agent.tools.visualization import visualization_handler
        output, is_error = await visualization_handler({
            "param_data": [
                {"delta": -10, "objective": 20},
                {"delta": 0, "objective": 30},
                {"delta": 10, "objective": 40},
            ],
            "var_name": "x",
            "chart_type": "sensitivity",
        })
        if is_error and "matplotlib" in str(output):
            pytest.skip("matplotlib not installed")
        assert not is_error

    @pytest.mark.asyncio
    async def test_empty_data(self):
        from agent.tools.visualization import visualization_handler
        output, is_error = await visualization_handler({
            "chart_type": "variables",
        })


# ═══════════════════════════════════════════════════════════════════════
# 11. Report Generator
# ═══════════════════════════════════════════════════════════════════════

class TestReportGenerator:

    @pytest.mark.asyncio
    async def test_markdown_report(self):
        from agent.tools.report_generator import report_generator_handler
        output, is_error = await report_generator_handler({
            "problem_description": "Maximize profit",
            "problem_type": "LP",
            "objective": 100.0,
            "variables": {"x": 10.0, "y": 5.0},
            "status": "OPTIMAL",
            "format": "markdown",
        })
        assert not is_error
        assert "Report" in output or "report" in output

    @pytest.mark.asyncio
    async def test_latex_report(self):
        from agent.tools.report_generator import report_generator_handler
        output, is_error = await report_generator_handler({
            "problem_description": "Minimize cost",
            "problem_type": "LP",
            "objective": 50.0,
            "variables": {"a": 3.0},
            "status": "OPTIMAL",
            "format": "latex",
        })
        assert not is_error
        assert "document" in output.lower() or "Report" in output


# ═══════════════════════════════════════════════════════════════════════
# 12. Solve Progress Parsing
# ═══════════════════════════════════════════════════════════════════════

class TestSolveProgressParsing:

    def test_parse_highs_mip_line(self):
        from agent.tools.solve_job import _parse_hipghs_progress
        line = "    10    25    15 5.00%   1.00000000e+02  9.50000000e+01  1.00000000e+02"
        snap = _parse_hipghs_progress(line, 0.0)
        assert snap is not None
        assert snap.nodes == 10
        assert snap.iterations == 25
        assert snap.best_bound == 100.0
        assert snap.best_sol == 95.0

    def test_parse_empty_line(self):
        from agent.tools.solve_job import _parse_hipghs_progress
        assert _parse_hipghs_progress("", 0.0) is None

    def test_parse_generic_status(self):
        from agent.tools.solve_job import _parse_generic_progress
        line = "Status: optimal"
        snap = _parse_generic_progress(line, 0.0)

    def test_format_result(self):
        from agent.tools.solve_job import SolveResult, _format_result
        result = SolveResult(
            status="OPTIMAL",
            objective=42.0,
            gap=0.0,
            elapsed_s=1.5,
            variables={"x": 10.0},
        )
        returned_result, output = _format_result(result, "highs")
        assert "OPTIMAL" in output
        assert "42" in output


# ═══════════════════════════════════════════════════════════════════════
# 13. Cost Estimation
# ═══════════════════════════════════════════════════════════════════════

class TestCostEstimation:

    def test_open_source_solver_free(self):
        from agent.core.cost_estimation import estimate_solver_cost
        result = estimate_solver_cost("highs", 300)
        assert result.estimated_cost_usd == 0.0
        assert not result.billable

    def test_commercial_solver_has_cost(self):
        from agent.core.cost_estimation import estimate_solver_cost
        result = estimate_solver_cost("gurobi", 3600)
        assert result.estimated_cost_usd > 0.0
        assert result.billable

    def test_llm_cost_positive(self):
        from agent.core.cost_estimation import estimate_llm_cost
        result = estimate_llm_cost("gpt-4o", 10000, 5000)
        assert result.estimated_cost_usd > 0.0

    def test_unknown_solver(self):
        from agent.core.cost_estimation import estimate_solver_cost
        result = estimate_solver_cost("nonexistent_solver_xyz", 300)
        assert result.block_reason is not None


# ═══════════════════════════════════════════════════════════════════════
# 14. Approval Policy
# ═══════════════════════════════════════════════════════════════════════

class TestApprovalPolicy:

    def test_commercial_solver_requires_approval(self):
        from agent.core.approval_policy import is_commercial_solver
        assert is_commercial_solver("gurobi")
        assert is_commercial_solver("cplex")

    def test_open_source_auto_approved(self):
        from agent.core.approval_policy import is_open_source_solver
        assert is_open_source_solver("highs")
        assert is_open_source_solver("scip")
        assert not is_open_source_solver("gurobi")


# ═══════════════════════════════════════════════════════════════════════
# 15. Edge Cases
# ═══════════════════════════════════════════════════════════════════════

class TestEdgeCases:

    def test_empty_description(self):
        from agent.tools.model_builder import generate_pyomo_code
        code = generate_pyomo_code("")
        compile(code, "<test>", "exec")

    def test_single_variable(self):
        from agent.tools.model_builder import generate_pyomo_code
        code = generate_pyomo_code("maximize x subject to x <= 10, x >= 0")
        compile(code, "<test>", "exec")
        assert "Var(" in code

    def test_many_constraints(self):
        from agent.tools.model_builder import _extract_constraints
        desc = "maximize x subject to x <= 10, x >= 0, x <= 5, x >= 1"
        constraints = _extract_constraints(desc)
        assert len(constraints) >= 2

    @pytest.mark.asyncio
    async def test_solve_nonexistent_model(self, session):
        from agent.tools.solve_job import solve_job_handler
        output, is_error = await solve_job_handler({
            "model_path": "/nonexistent/model.py",
        }, session=session)
        assert is_error

    @pytest.mark.asyncio
    async def test_validate_nonexistent_model(self):
        from agent.tools.validate_solution import validate_solution_handler
        output, is_error = await validate_solution_handler({
            "model_path": "/nonexistent/model.py",
        })
        assert is_error

    @pytest.mark.asyncio
    async def test_sensitivity_nonexistent_model(self, session):
        from agent.tools.sensitivity_analysis import sensitivity_analysis_handler
        output, is_error = await sensitivity_analysis_handler({
            "model_path": "/nonexistent/model.py",
        }, session=session)
        assert is_error
