"""Unit tests for model_checker tool."""

import pytest
from pathlib import Path


class TestModelCheckerSpec:
    """Test tool specification."""

    def test_spec_has_required_fields(self):
        from agent.tools.model_checker import MODEL_CHECKER_TOOL_SPEC
        spec = MODEL_CHECKER_TOOL_SPEC
        assert spec["name"] == "model_checker"
        assert "parameters" in spec

    def test_spec_has_model_path(self):
        from agent.tools.model_checker import MODEL_CHECKER_TOOL_SPEC
        props = MODEL_CHECKER_TOOL_SPEC["parameters"]["properties"]
        assert "model_path" in props


class TestCheckSyntax:
    """Test syntax checking."""

    def test_valid_python(self):
        from agent.tools.model_checker import _check_syntax
        errors = _check_syntax("x = 1\ny = 2")
        assert len(errors) == 0

    def test_invalid_python(self):
        from agent.tools.model_checker import _check_syntax
        errors = _check_syntax("def foo(\n    pass")
        assert len(errors) > 0


class TestCheckImports:
    """Test import checking."""

    def test_has_pyomo_import(self):
        from agent.tools.model_checker import _check_imports
        warnings = _check_imports("from pyomo.environ import *\nmodel = ConcreteModel()")
        assert len(warnings) == 0

    def test_missing_pyomo_import(self):
        from agent.tools.model_checker import _check_imports
        warnings = _check_imports("model = ConcreteModel()")
        assert any("Pyomo" in w for w in warnings)

    def test_missing_model_declaration(self):
        from agent.tools.model_checker import _check_imports
        warnings = _check_imports("from pyomo.environ import *")
        assert any("model" in w.lower() for w in warnings)


class TestCheckVariables:
    """Test variable checking."""

    def test_has_variables(self):
        from agent.tools.model_checker import _check_variables
        code = "model.x = Var(domain=NonNegativeReals)"
        warnings = _check_variables(code)
        assert len(warnings) == 0

    def test_no_variables(self):
        from agent.tools.model_checker import _check_variables
        warnings = _check_variables("model = ConcreteModel()")
        assert any("variable" in w.lower() for w in warnings)

    def test_variable_without_domain(self):
        from agent.tools.model_checker import _check_variables
        warnings = _check_variables("model.x = Var()")
        assert any("domain" in w.lower() for w in warnings)


class TestCheckObjective:
    """Test objective checking."""

    def test_has_objective(self):
        from agent.tools.model_checker import _check_objective
        code = "model.obj = Objective(expr=model.x, sense=maximize)"
        errors = _check_objective(code)
        assert len(errors) == 0

    def test_missing_objective(self):
        from agent.tools.model_checker import _check_objective
        errors = _check_objective("model = ConcreteModel()")
        assert any("objective" in e.lower() for e in errors)

    def test_missing_sense(self):
        from agent.tools.model_checker import _check_objective
        errors = _check_objective("model.obj = Objective(expr=model.x)")
        assert any("sense" in e.lower() for e in errors)


class TestCheckConstraints:
    """Test constraint checking."""

    def test_has_constraints(self):
        from agent.tools.model_checker import _check_constraints
        warnings = _check_constraints("model.c1 = Constraint(expr=model.x <= 10)")
        assert len(warnings) == 0

    def test_no_constraints(self):
        from agent.tools.model_checker import _check_constraints
        warnings = _check_constraints("model = ConcreteModel()")
        assert any("constraint" in w.lower() for w in warnings)


class TestCheckSolverCompat:
    """Test solver compatibility checking."""

    def test_highs_no_issues(self):
        from agent.tools.model_checker import _check_solver_compat
        warnings = _check_solver_compat("model.obj = Objective(expr=model.x)", "highs")
        assert len(warnings) == 0

    def test_highs_with_nonlinear(self):
        from agent.tools.model_checker import _check_solver_compat
        warnings = _check_solver_compat("expr = sin(model.x)", "highs")
        assert any("nonlinear" in w.lower() for w in warnings)


class TestModelCheckerHandler:
    """Test the async handler."""

    @pytest.mark.asyncio
    async def test_missing_model_path(self):
        from agent.tools.model_checker import model_checker_handler
        output, is_error = await model_checker_handler({"model_path": ""})
        assert is_error

    @pytest.mark.asyncio
    async def test_nonexistent_file(self):
        from agent.tools.model_checker import model_checker_handler
        output, is_error = await model_checker_handler({
            "model_path": "/nonexistent/model.py"
        })
        assert is_error

    @pytest.mark.asyncio
    async def test_valid_model(self, temp_dir, sample_model_code):
        from agent.tools.model_checker import model_checker_handler
        model_path = temp_dir / "model.py"
        model_path.write_text(sample_model_code, encoding="utf-8")
        output, is_error = await model_checker_handler({
            "model_path": str(model_path),
            "run_import_test": False,
        })
        assert not is_error
        assert "Check" in output or "Model" in output

    @pytest.mark.asyncio
    async def test_model_with_warnings(self, temp_dir):
        from agent.tools.model_checker import model_checker_handler
        model_path = temp_dir / "model.py"
        model_path.write_text(
            "from pyomo.environ import *\nmodel = ConcreteModel()\nmodel.obj = Objective(expr=model.x, sense=maximize)",
            encoding="utf-8"
        )
        output, is_error = await model_checker_handler({
            "model_path": str(model_path),
            "run_import_test": False,
        })
        assert not is_error
        assert "Warning" in output or "Missing" in output or "variable" in output.lower()
