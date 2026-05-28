"""Unit tests for model_builder tool."""

import pytest
import re
from pathlib import Path
import tempfile


class TestParseSimpleLP:
    """Test natural language LP parsing."""

    def test_basic_maximize(self):
        from agent.tools.model_builder import _detect_direction, _extract_objective, _detect_var_types, _extract_constraints
        desc = "maximize 3x + 2y subject to x + y <= 10, x >= 0, y >= 0"
        direction = _detect_direction(desc)
        raw, coeffs = _extract_objective(desc)
        var_types = _detect_var_types(desc, list(coeffs.keys()))
        constraints = _extract_constraints(desc)

        assert direction == "maximize"
        assert var_types == {"x": "continuous", "y": "continuous"}
        assert coeffs == {"x": 3.0, "y": 2.0}
        assert len(constraints) >= 1

    def test_minimize(self):
        from agent.tools.model_builder import _detect_direction
        desc = "minimize x + 3y subject to 2x + y >= 5"
        assert _detect_direction(desc) == "minimize"

    def test_no_constraints(self):
        from agent.tools.model_builder import _extract_objective
        desc = "maximize 5x + 3y"
        _, coeffs = _extract_objective(desc)
        assert "x" in coeffs


class TestGeneratePyomoCode:
    """Test Pyomo code generation."""

    def test_output_is_valid_python(self):
        from agent.tools.model_builder import generate_pyomo_code
        code = generate_pyomo_code("maximize 3x + 2y subject to x + y <= 10")
        compile(code, "<test>", "exec")

    def test_contains_import(self):
        from agent.tools.model_builder import generate_pyomo_code
        code = generate_pyomo_code("maximize 3x + 2y subject to x + y <= 10")
        assert "from pyomo.environ import *" in code
        assert "ConcreteModel()" in code

    def test_variables_defined(self):
        from agent.tools.model_builder import generate_pyomo_code
        code = generate_pyomo_code("maximize 3x + 2y subject to x + y <= 10")
        assert "model.x" in code
        assert "model.y" in code


class TestModelBuilderHandler:
    """Test the async handler."""

    @pytest.mark.asyncio
    async def test_returns_analysis(self):
        from agent.tools.model_builder import model_builder_handler
        output, is_error = await model_builder_handler({
            "description": "maximize 3x + 2y subject to x + y <= 10"
        })
        assert not is_error
        assert "Model Generated" in output
        assert "maximize" in output.lower()

    @pytest.mark.asyncio
    async def test_empty_description(self):
        from agent.tools.model_builder import model_builder_handler
        output, is_error = await model_builder_handler({"description": ""})
        assert is_error

    @pytest.mark.asyncio
    async def test_model_file_created(self):
        from agent.tools.model_builder import model_builder_handler
        output, is_error = await model_builder_handler({
            "description": "maximize x + y subject to x <= 5, y <= 3"
        })
        assert not is_error
        m = re.search(r'Model file\*\*: (.+)', output)
        assert m is not None
        assert Path(m.group(1)).exists()
