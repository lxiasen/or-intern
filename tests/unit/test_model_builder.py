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


class TestAdvancedMIPFeatures:
    """Test advanced MIP features: binary, integer, SOS, indicator, piecewise."""

    def test_binary_variables(self):
        from agent.tools.model_builder import _detect_var_types
        desc = "maximize x + y where x is binary, y is binary"
        var_types = _detect_var_types(desc, ["x", "y"])
        assert var_types["x"] == "binary"
        assert var_types["y"] == "binary"

    def test_integer_variables(self):
        from agent.tools.model_builder import _detect_var_types
        desc = "maximize x + y where x is integer, y is integer"
        var_types = _detect_var_types(desc, ["x", "y"])
        assert var_types["x"] == "integer"
        assert var_types["y"] == "integer"

    def test_semi_continuous_variables(self):
        from agent.tools.model_builder import _detect_var_types
        desc = "maximize x + y where x is semi-continuous"
        var_types = _detect_var_types(desc, ["x", "y"])
        assert var_types["x"] == "semi_continuous"

    def test_sos1_extraction(self):
        from agent.tools.model_builder import _extract_sos
        desc = "SOS1([x, y, z])"
        sos_list = _extract_sos(desc)
        assert len(sos_list) == 1
        assert sos_list[0]["type"] == "SOS1"
        assert "x" in sos_list[0]["vars"]

    def test_sos2_extraction(self):
        from agent.tools.model_builder import _extract_sos
        desc = "SOS2([a, b, c], weights=[1, 2, 3])"
        sos_list = _extract_sos(desc)
        assert len(sos_list) == 1
        assert sos_list[0]["type"] == "SOS2"
        assert sos_list[0]["weights"] == [1.0, 2.0, 3.0]

    def test_indicator_extraction(self):
        from agent.tools.model_builder import _extract_indicators
        desc = "if x == 1 then y >= 5"
        indicators = _extract_indicators(desc)
        assert len(indicators) == 1
        assert indicators[0]["var"] == "x"
        assert indicators[0]["val"] == 1

    def test_piecewise_extraction(self):
        from agent.tools.model_builder import _extract_piecewise
        desc = "piecewise([0, 10, 20], [0, 5, 15], x)"
        pieces = _extract_piecewise(desc)
        assert len(pieces) == 1
        assert pieces[0]["breakpoints"] == [0.0, 10.0, 20.0]
        assert pieces[0]["values"] == [0.0, 5.0, 15.0]

    def test_mip_model_generation(self):
        from agent.tools.model_builder import generate_pyomo_code
        code = generate_pyomo_code("maximize x + y subject to x + y <= 10, x binary, y binary")
        assert "Binary" in code or "binary" in code
        compile(code, "<test>", "exec")


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

    @pytest.mark.asyncio
    async def test_mip_model_with_binary(self):
        from agent.tools.model_builder import model_builder_handler
        output, is_error = await model_builder_handler({
            "description": "maximize x + y subject to x + y <= 10, x binary, y binary"
        })
        assert not is_error
        assert "MIP" in output
