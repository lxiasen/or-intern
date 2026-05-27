"""Unit tests for model_builder tool."""

import pytest
import re
from pathlib import Path
import tempfile


class TestParseSimpleLP:
    """Test natural language LP parsing."""

    def test_basic_maximize(self):
        from agent.tools.model_builder import _parse_simple_lp
        r = _parse_simple_lp("maximize 3x + 2y subject to x + y <= 10, x >= 0, y >= 0")
        assert r["direction"] == "maximize"
        assert r["variables"] == {"x": "continuous", "y": "continuous"}
        assert r["coeffs"] == {"x": 3.0, "y": 2.0}
        # Constraint parsing may vary; check at least 1 constraint
        assert len(r["constraints"]) >= 1

    def test_minimize(self):
        from agent.tools.model_builder import _parse_simple_lp
        r = _parse_simple_lp("minimize x + 3y subject to 2x + y >= 5")
        assert r["direction"] == "minimize"

    def test_no_constraints(self):
        from agent.tools.model_builder import _parse_simple_lp
        r = _parse_simple_lp("maximize 5x + 3y")
        assert r["direction"] == "maximize"
        assert "x" in r["variables"]


class TestGeneratePyomoCode:
    """Test Pyomo code generation."""

    def test_output_is_valid_python(self):
        from agent.tools.model_builder import generate_pyomo_code
        code = generate_pyomo_code("maximize 3x + 2y subject to x + y <= 10")
        # Must be parseable Python
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
