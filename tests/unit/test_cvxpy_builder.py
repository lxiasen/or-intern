"""Unit tests for cvxpy_builder tool."""

import pytest
from pathlib import Path


class TestCvxpyBuilderSpec:
    """Test tool specification."""

    def test_spec_has_required_fields(self):
        from agent.tools.cvxpy_builder import CVXPY_BUILDER_TOOL_SPEC
        spec = CVXPY_BUILDER_TOOL_SPEC
        assert spec["name"] == "cvxpy_builder"
        assert "parameters" in spec
        assert "description" in spec["parameters"]["properties"]

    def test_spec_has_description_param(self):
        from agent.tools.cvxpy_builder import CVXPY_BUILDER_TOOL_SPEC
        props = CVXPY_BUILDER_TOOL_SPEC["parameters"]["properties"]
        assert "description" in props
        assert "solver" in props


class TestDetectDirection:
    """Test optimization direction detection."""

    def test_minimize(self):
        from agent.tools.cvxpy_builder import _detect_direction
        assert _detect_direction("minimize x + y") == "minimize"

    def test_maximize(self):
        from agent.tools.cvxpy_builder import _detect_direction
        assert _detect_direction("maximize 3x + 2y") == "maximize"

    def test_default_maximize(self):
        from agent.tools.cvxpy_builder import _detect_direction
        assert _detect_direction("find the best x") == "maximize"


class TestExtractVariables:
    """Test variable extraction."""

    def test_basic_variables(self):
        from agent.tools.cvxpy_builder import _extract_variables
        desc = "minimize x + y subject to x >= 0"
        variables = _extract_variables(desc)
        assert "x" in variables
        assert "y" in variables


class TestExtractConstraints:
    """Test constraint extraction."""

    def test_inequality_constraints(self):
        from agent.tools.cvxpy_builder import _extract_constraints
        desc = "minimize x + y subject to x + y <= 10, x >= 0"
        constraints = _extract_constraints(desc)
        assert len(constraints) >= 1


class TestExtractObjective:
    """Test objective extraction."""

    def test_minimize_objective(self):
        from agent.tools.cvxpy_builder import _extract_objective
        desc = "minimize x + y subject to x + y >= 1"
        obj = _extract_objective(desc)
        assert "x" in obj


class TestGenerateCvxpyCode:
    """Test cvxpy code generation."""

    def test_basic_linear(self):
        from agent.tools.cvxpy_builder import generate_cvxpy_code
        code = generate_cvxpy_code("minimize x + y subject to x + y >= 1")
        assert "import cvxpy" in code
        assert "cp.Variable" in code
        assert "cp.Minimize" in code

    def test_linear_program(self):
        from agent.tools.cvxpy_builder import generate_cvxpy_code
        code = generate_cvxpy_code("minimize x + y subject to x + y <= 10")
        assert "import cvxpy" in code
        assert "cp.Minimize" in code

    def test_maximize_objective(self):
        from agent.tools.cvxpy_builder import generate_cvxpy_code
        code = generate_cvxpy_code("maximize 3x + 2y subject to x + y <= 10")
        assert "cp.Maximize" in code

    def test_code_is_valid_python(self):
        from agent.tools.cvxpy_builder import generate_cvxpy_code
        code = generate_cvxpy_code("minimize x + y subject to x + y >= 1")
        compile(code, "<test>", "exec")

    def test_solver_specified(self):
        from agent.tools.cvxpy_builder import generate_cvxpy_code
        code = generate_cvxpy_code("minimize x + y", solver="SCS")
        assert "SCS" in code


class TestCvxpyBuilderHandler:
    """Test the async handler."""

    @pytest.mark.asyncio
    async def test_empty_description(self):
        from agent.tools.cvxpy_builder import cvxpy_builder_handler
        output, is_error = await cvxpy_builder_handler({"description": ""})
        assert is_error

    @pytest.mark.asyncio
    async def test_generates_model(self, temp_dir, monkeypatch):
        import agent.tools.cvxpy_builder as cb
        monkeypatch.setattr(cb, "get_workspace_dir", lambda session=None: temp_dir)
        output, is_error = await cb.cvxpy_builder_handler({
            "description": "minimize x + y subject to x + y >= 1",
        })
        assert not is_error
        assert "cvxpy" in output.lower() or "Convex" in output

    @pytest.mark.asyncio
    async def test_model_file_created(self, temp_dir, monkeypatch):
        import agent.tools.cvxpy_builder as cb
        monkeypatch.setattr(cb, "get_workspace_dir", lambda session=None: temp_dir)
        output, is_error = await cb.cvxpy_builder_handler({
            "description": "minimize x + y",
        })
        assert not is_error
        py_files = list(temp_dir.glob("*.py"))
        assert len(py_files) >= 1


class TestProblemTypeDetection:
    """Test problem type detection in model_builder."""

    def test_lp_detection(self):
        from agent.tools.model_builder import detect_problem_type
        assert detect_problem_type("maximize 3x + 2y subject to x + y <= 10") == "LP"

    def test_mip_detection(self):
        from agent.tools.model_builder import detect_problem_type
        assert detect_problem_type("maximize x + y subject to x binary") == "MIP"

    def test_nlp_detection(self):
        from agent.tools.model_builder import detect_problem_type
        assert detect_problem_type("minimize x^2 + y^2") == "Convex"

    def test_convex_detection(self):
        from agent.tools.model_builder import detect_problem_type
        assert detect_problem_type("minimize x^2 subject to x >= 0") == "Convex"


class TestFrameworkRecommendation:
    """Test framework recommendation."""

    def test_lp_uses_pyomo(self):
        from agent.tools.model_builder import recommend_framework
        framework, solver = recommend_framework("LP")
        assert framework == "pyomo"
        assert solver == "highs"

    def test_convex_uses_cvxpy(self):
        from agent.tools.model_builder import recommend_framework
        framework, solver = recommend_framework("Convex")
        assert framework == "cvxpy"
        assert solver == "ECOS"

    def test_nlp_uses_pyomo(self):
        from agent.tools.model_builder import recommend_framework
        framework, solver = recommend_framework("NLP")
        assert framework == "pyomo"
        assert solver == "ipopt"