"""Unit tests for sensitivity_analysis tool."""

import pytest
import tempfile
from pathlib import Path


class TestSensitivityAnalysisSpec:
    """Test tool specification."""

    def test_spec_has_required_fields(self):
        from agent.tools.sensitivity_analysis import SENSITIVITY_ANALYSIS_TOOL_SPEC
        spec = SENSITIVITY_ANALYSIS_TOOL_SPEC
        assert spec["name"] == "sensitivity_analysis"
        assert "parameters" in spec
        assert "properties" in spec["parameters"]
        assert "model_path" in spec["parameters"]["properties"]

    def test_spec_operations(self):
        from agent.tools.sensitivity_analysis import SENSITIVITY_ANALYSIS_TOOL_SPEC
        ops = SENSITIVITY_ANALYSIS_TOOL_SPEC["parameters"]["properties"]["operation"]
        assert "dual" in ops["enum"]
        assert "parametric" in ops["enum"]
        assert "full" in ops["enum"]


class TestParametricCodeGeneration:
    """Test parametric analysis code generation."""

    def test_generates_code_for_single_variable(self):
        from agent.tools.sensitivity_analysis import _generate_parametric_code
        code = _generate_parametric_code(["x"], ["c1"])
        assert "model.x" in code
        assert "delta" in code

    def test_generates_code_for_multiple_variables(self):
        from agent.tools.sensitivity_analysis import _generate_parametric_code
        code = _generate_parametric_code(["x", "y", "z"], ["c1", "c2"])
        assert "model.x" in code
        assert "model.y" in code
        assert "model.z" in code

    def test_empty_variables(self):
        from agent.tools.sensitivity_analysis import _generate_parametric_code
        code = _generate_parametric_code([], [])
        assert "PARAMETRIC_OBJ" in code


class TestSensitivityAnalysisHandler:
    """Test the async handler."""

    @pytest.mark.asyncio
    async def test_missing_model_path(self):
        from agent.tools.sensitivity_analysis import sensitivity_analysis_handler
        output, is_error = await sensitivity_analysis_handler({"model_path": ""})
        assert is_error
        assert "No model path" in output

    @pytest.mark.asyncio
    async def test_nonexistent_model_file(self):
        from agent.tools.sensitivity_analysis import sensitivity_analysis_handler
        output, is_error = await sensitivity_analysis_handler({
            "model_path": "/nonexistent/model.py"
        })
        assert is_error
        assert "not found" in output.lower()

    @pytest.mark.asyncio
    async def test_valid_model_runs(self, temp_dir, sample_model_code):
        from agent.tools.sensitivity_analysis import sensitivity_analysis_handler
        model_path = temp_dir / "model.py"
        model_path.write_text(sample_model_code, encoding="utf-8")
        output, is_error = await sensitivity_analysis_handler({
            "model_path": str(model_path),
            "solver": "highs",
            "operation": "dual",
        })
        assert not is_error
        assert "Sensitivity Analysis" in output
