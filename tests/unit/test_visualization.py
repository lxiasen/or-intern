"""Unit tests for visualization tool."""

import pytest
from pathlib import Path


class TestVisualizationSpec:
    """Test tool specification."""

    def test_spec_has_required_fields(self):
        from agent.tools.visualization import VISUALIZATION_TOOL_SPEC
        spec = VISUALIZATION_TOOL_SPEC
        assert spec["name"] == "visualization"
        assert "parameters" in spec

    def test_spec_chart_types(self):
        from agent.tools.visualization import VISUALIZATION_TOOL_SPEC
        chart_type = VISUALIZATION_TOOL_SPEC["parameters"]["properties"]["chart_type"]
        assert "variables" in chart_type["enum"]
        assert "sensitivity" in chart_type["enum"]
        assert "all" in chart_type["enum"]


class TestVariableChart:
    """Test variable value chart generation."""

    def test_generates_chart_file(self, temp_dir):
        import matplotlib
        matplotlib.use('Agg')
        from agent.tools.visualization import _generate_variable_chart
        chart_path = str(temp_dir / "test_var.png")
        _generate_variable_chart({"x": 10.0, "y": 5.0, "z": 0.0}, 30.0, chart_path)
        assert Path(chart_path).exists()
        assert Path(chart_path).stat().st_size > 0

    def test_single_variable(self, temp_dir):
        import matplotlib
        matplotlib.use('Agg')
        from agent.tools.visualization import _generate_variable_chart
        chart_path = str(temp_dir / "single.png")
        _generate_variable_chart({"x": 42.0}, 42.0, chart_path)
        assert Path(chart_path).exists()


class TestSensitivityChart:
    """Test sensitivity chart generation."""

    def test_generates_chart_file(self, temp_dir):
        import matplotlib
        matplotlib.use('Agg')
        from agent.tools.visualization import _generate_sensitivity_chart
        chart_path = str(temp_dir / "test_sens.png")
        param_data = [
            {"delta": -20, "objective": 10.0},
            {"delta": 0, "objective": 30.0},
            {"delta": 20, "objective": 50.0},
        ]
        _generate_sensitivity_chart(param_data, "x", chart_path)
        assert Path(chart_path).exists()

    def test_empty_data_returns_empty(self, temp_dir):
        from agent.tools.visualization import _generate_sensitivity_chart
        chart_path = str(temp_dir / "empty.png")
        result = _generate_sensitivity_chart([], "x", chart_path)
        assert result == ""


class TestGapChart:
    """Test gap convergence chart generation."""

    def test_generates_chart_file(self, temp_dir):
        import matplotlib
        matplotlib.use('Agg')
        from agent.tools.visualization import _generate_gap_chart
        chart_path = str(temp_dir / "test_gap.png")
        gap_data = [
            {"time": 0.1, "gap": 100.0, "bound": 0.0},
            {"time": 1.0, "gap": 10.0, "bound": 27.0},
            {"time": 5.0, "gap": 0.1, "bound": 29.9},
        ]
        _generate_gap_chart(gap_data, chart_path)
        assert Path(chart_path).exists()

    def test_empty_data_returns_empty(self, temp_dir):
        from agent.tools.visualization import _generate_gap_chart
        result = _generate_gap_chart([], str(temp_dir / "empty.png"))
        assert result == ""


class TestConstraintHeatmap:
    """Test constraint tightness heatmap generation."""

    def test_generates_heatmap_file(self, temp_dir):
        import matplotlib
        matplotlib.use('Agg')
        from agent.tools.visualization import _generate_constraint_heatmap
        chart_path = str(temp_dir / "test_heatmap.png")
        constraints = {"c1": 0.0, "c2": 5.0, "c3": 0.1}
        _generate_constraint_heatmap(constraints, chart_path)
        assert Path(chart_path).exists()
        assert Path(chart_path).stat().st_size > 0

    def test_empty_constraints_returns_empty(self, temp_dir):
        from agent.tools.visualization import _generate_constraint_heatmap
        chart_path = str(temp_dir / "empty.png")
        result = _generate_constraint_heatmap({}, chart_path)
        assert result == ""


class TestParetoFront:
    """Test Pareto front visualization."""

    def test_generates_pareto_file(self, temp_dir):
        import matplotlib
        matplotlib.use('Agg')
        from agent.tools.visualization import _generate_pareto_front
        chart_path = str(temp_dir / "test_pareto.png")
        objectives = [
            {"obj1": 10, "obj2": 20, "label": "S1"},
            {"obj1": 15, "obj2": 15, "label": "S2"},
            {"obj1": 20, "obj2": 10, "label": "S3"},
        ]
        _generate_pareto_front(objectives, chart_path)
        assert Path(chart_path).exists()
        assert Path(chart_path).stat().st_size > 0

    def test_insufficient_data_returns_empty(self, temp_dir):
        from agent.tools.visualization import _generate_pareto_front
        chart_path = str(temp_dir / "empty.png")
        result = _generate_pareto_front([{"obj1": 1, "obj2": 2}], chart_path)
        assert result == ""


class TestVisualizationHandler:
    """Test the async handler."""

    @pytest.mark.asyncio
    async def test_no_variables_provided(self):
        from agent.tools.visualization import visualization_handler
        output, is_error = await visualization_handler({
            "chart_type": "variables"
        })
        assert is_error
        assert "No variable data" in output

    @pytest.mark.asyncio
    async def test_non_numeric_variable_values(self):
        from agent.tools.visualization import visualization_handler
        output, is_error = await visualization_handler({
            "chart_type": "variables",
            "variables": {"x": "not_a_number"},
        })
        assert is_error
        assert "numeric" in output.lower()

    @pytest.mark.asyncio
    async def test_valid_variable_chart(self, temp_dir, monkeypatch):
        from agent.tools import visualization as _viz
        monkeypatch.setattr(_viz, "get_workspace_dir", lambda session=None: temp_dir)
        from agent.tools.visualization import visualization_handler
        output, is_error = await visualization_handler({
            "chart_type": "variables",
            "variables": {"x": 10.0, "y": 5.0},
            "objective": 30.0,
        })
        assert not is_error
        assert "Visualization Results" in output
        assert "variables" in output.lower()

    @pytest.mark.asyncio
    async def test_heatmap_chart(self, temp_dir, monkeypatch):
        from agent.tools import visualization as _viz
        monkeypatch.setattr(_viz, "get_workspace_dir", lambda session=None: temp_dir)
        from agent.tools.visualization import visualization_handler
        output, is_error = await visualization_handler({
            "chart_type": "heatmap",
            "constraints": {"c1": 0.0, "c2": 5.0},
        })
        assert not is_error
        assert "Heatmap" in output

    @pytest.mark.asyncio
    async def test_pareto_chart(self, temp_dir, monkeypatch):
        from agent.tools import visualization as _viz
        monkeypatch.setattr(_viz, "get_workspace_dir", lambda session=None: temp_dir)
        from agent.tools.visualization import visualization_handler
        output, is_error = await visualization_handler({
            "chart_type": "pareto",
            "pareto_data": [
                {"obj1": 10, "obj2": 20, "label": "S1"},
                {"obj1": 15, "obj2": 15, "label": "S2"},
                {"obj1": 20, "obj2": 10, "label": "S3"},
            ],
        })
        assert not is_error
        assert "Pareto" in output
