"""Unit tests for compare_solvers tool."""

import pytest
from pathlib import Path


class TestCompareSolversSpec:
    """Test tool specification."""

    def test_spec_has_required_fields(self):
        from agent.tools.compare_solvers import COMPARE_SOLVERS_TOOL_SPEC
        spec = COMPARE_SOLVERS_TOOL_SPEC
        assert spec["name"] == "compare_solvers"
        assert "parameters" in spec
        assert "model_path" in spec["parameters"]["properties"]

    def test_spec_solvers_default(self):
        from agent.tools.compare_solvers import COMPARE_SOLVERS_TOOL_SPEC
        solvers = COMPARE_SOLVERS_TOOL_SPEC["parameters"]["properties"]["solvers"]
        assert "default" in solvers


class TestBuildSolveScript:
    """Test solve script generation."""

    def test_script_contains_model_code(self):
        from agent.tools.compare_solvers import _build_solve_script
        script = _build_solve_script("model = ConcreteModel()", "highs", "/tmp")
        assert "model = ConcreteModel()" in script
        assert "highs" in script

    def test_script_contains_import(self):
        from agent.tools.compare_solvers import _build_solve_script
        script = _build_solve_script("from pyomo.environ import *", "scip", "/tmp")
        assert "from pyomo.environ import *" in script


class TestCompareSolversHandler:
    """Test the async handler."""

    @pytest.mark.asyncio
    async def test_missing_model_path(self):
        from agent.tools.compare_solvers import compare_solvers_handler
        output, is_error = await compare_solvers_handler({"model_path": ""})
        assert is_error

    @pytest.mark.asyncio
    async def test_nonexistent_model_file(self):
        from agent.tools.compare_solvers import compare_solvers_handler
        output, is_error = await compare_solvers_handler({
            "model_path": "/nonexistent/model.py"
        })
        assert is_error

    @pytest.mark.asyncio
    async def test_valid_model_comparison(self, temp_dir, sample_model_code):
        from agent.tools.compare_solvers import compare_solvers_handler
        model_path = temp_dir / "model.py"
        model_path.write_text(sample_model_code, encoding="utf-8")
        output, is_error = await compare_solvers_handler({
            "model_path": str(model_path),
            "solvers": ["highs"],
        })
        assert not is_error
        assert "Solver Comparison" in output
