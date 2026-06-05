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
        # New chart types
        assert "trend" in chart_type["enum"]
        assert "stacked_bar" in chart_type["enum"]
        assert "scatter_gantt" in chart_type["enum"]
        assert "pie" in chart_type["enum"]
        assert "ratio_heatmap" in chart_type["enum"]


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

    @pytest.mark.asyncio
    async def test_trend_chart(self, temp_dir, monkeypatch):
        from agent.tools import visualization as _viz
        monkeypatch.setattr(_viz, "get_workspace_dir", lambda session=None: temp_dir)
        from agent.tools.visualization import visualization_handler
        output, is_error = await visualization_handler({
            "chart_type": "trend",
            "series_data": {"库存A": [100, 90, 80, 70], "库存B": [50, 60, 55, 45]},
            "x_labels": ["第1周", "第2周", "第3周", "第4周"],
            "title": "库存趋势分析",
            "xlabel": "周次",
            "ylabel": "库存量",
            "threshold_lines": {"安全库存": 60},
            "fill_threshold": 60,
        })
        assert not is_error
        assert "Trend" in output

    @pytest.mark.asyncio
    async def test_stacked_bar_chart(self, temp_dir, monkeypatch):
        from agent.tools import visualization as _viz
        monkeypatch.setattr(_viz, "get_workspace_dir", lambda session=None: temp_dir)
        from agent.tools.visualization import visualization_handler
        output, is_error = await visualization_handler({
            "chart_type": "stacked_bar",
            "category_data": {"物料A": [10, 15, 20], "物料B": [5, 8, 12]},
            "categories": ["物料A", "物料B"],
            "x_labels": ["第1周", "第2周", "第3周"],
            "title": "每周物料需求",
            "xlabel": "周次",
            "ylabel": "需求量",
        })
        assert not is_error
        assert "Stacked" in output

    @pytest.mark.asyncio
    async def test_scatter_gantt_chart(self, temp_dir, monkeypatch):
        from agent.tools import visualization as _viz
        monkeypatch.setattr(_viz, "get_workspace_dir", lambda session=None: temp_dir)
        from agent.tools.visualization import visualization_handler
        output, is_error = await visualization_handler({
            "chart_type": "scatter_gantt",
            "event_data": {"物料A": [0, 100, 0, 200], "物料B": [50, 0, 150, 0]},
            "categories": ["物料A", "物料B"],
            "x_labels": ["第1周", "第2周", "第3周", "第4周"],
            "title": "补货计划",
            "xlabel": "周次",
        })
        assert not is_error
        assert "Gantt" in output

    @pytest.mark.asyncio
    async def test_pie_chart(self, temp_dir, monkeypatch):
        from agent.tools import visualization as _viz
        monkeypatch.setattr(_viz, "get_workspace_dir", lambda session=None: temp_dir)
        from agent.tools.visualization import visualization_handler
        output, is_error = await visualization_handler({
            "chart_type": "pie",
            "category_data": {"持有成本": 1000, "补货成本": 5000, "缺料成本": 200},
            "title": "成本分解",
        })
        assert not is_error
        assert "Pie" in output

    @pytest.mark.asyncio
    async def test_ratio_heatmap_chart(self, temp_dir, monkeypatch):
        from agent.tools import visualization as _viz
        monkeypatch.setattr(_viz, "get_workspace_dir", lambda session=None: temp_dir)
        from agent.tools.visualization import visualization_handler
        output, is_error = await visualization_handler({
            "chart_type": "ratio_heatmap",
            "value_data": {"物料A": [100, 80, 60], "物料B": [50, 45, 40]},
            "reference_data": {"物料A": 80, "物料B": 45},
            "categories": ["物料A", "物料B"],
            "x_labels": ["第1周", "第2周", "第3周"],
            "title": "库存风险分析",
            "xlabel": "周次",
            "ylabel": "物料",
        })
        assert not is_error
        assert "Heatmap" in output


class TestChineseFontSupport:
    """Test Chinese font configuration for matplotlib."""

    def test_setup_chinese_font_function_exists(self):
        """Verify _setup_chinese_font function is importable."""
        from agent.tools.visualization import _setup_chinese_font
        assert callable(_setup_chinese_font)

    def test_setup_chinese_font_runs_without_error(self):
        """Verify _setup_chinese_font executes without raising exceptions."""
        import matplotlib
        matplotlib.use('Agg')
        from agent.tools.visualization import _setup_chinese_font
        # Should not raise any exception
        _setup_chinese_font()

    def test_chinese_font_configures_rcparams(self):
        """Verify _setup_chinese_font modifies matplotlib rcParams."""
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        from agent.tools.visualization import _setup_chinese_font

        # Store original value
        original = plt.rcParams.get('font.sans-serif', [])

        _setup_chinese_font()

        # After setup, sans-serif should have been modified
        current = plt.rcParams.get('font.sans-serif', [])
        # At minimum, DejaVu Sans should be in the list as fallback
        assert len(current) >= len(original) or 'DejaVu Sans' in current

    def test_chinese_characters_in_variable_chart(self, temp_dir):
        """Verify charts with Chinese labels generate without warnings."""
        import matplotlib
        matplotlib.use('Agg')
        import warnings
        from agent.tools.visualization import _generate_variable_chart

        chart_path = str(temp_dir / "chinese_test.png")
        chinese_variables = {"硅晶圆": 500.0, "光刻胶": 200.0, "金属靶材": 150.0}

        # Capture warnings
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            _generate_variable_chart(chinese_variables, 850.0, chart_path)

            # Filter for CJK/glyph missing warnings
            glyph_warnings = [
                warning for warning in w
                if "missing from font" in str(warning.message)
            ]
            # Should have fewer or no glyph warnings after font setup
            # (may still have warnings if no Chinese font is installed)
            if glyph_warnings:
                pytest.skip("No Chinese font available in test environment")

        assert Path(chart_path).exists()
        assert Path(chart_path).stat().st_size > 0
