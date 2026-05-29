"""Unit tests for report_generator tool."""

import pytest
from pathlib import Path
import unittest.mock as mock


class TestReportGeneratorSpec:
    """Test tool specification."""

    def test_spec_has_required_fields(self):
        from agent.tools.report_generator import REPORT_GENERATOR_TOOL_SPEC
        spec = REPORT_GENERATOR_TOOL_SPEC
        assert spec["name"] == "report_generator"
        assert "parameters" in spec

    def test_spec_has_problem_description(self):
        from agent.tools.report_generator import REPORT_GENERATOR_TOOL_SPEC
        props = REPORT_GENERATOR_TOOL_SPEC["parameters"]["properties"]
        assert "problem_description" in props
        assert "variables" in props
        assert "objective" in props


class TestFormatVarTable:
    """Test variable table formatting."""

    def test_basic_table(self):
        from agent.tools.report_generator import _format_var_table
        table = _format_var_table({"x": 10.0, "y": 5.0})
        assert "| x |" in table
        assert "| y |" in table
        assert "10.0000" in table

    def test_empty_variables(self):
        from agent.tools.report_generator import _format_var_table
        table = _format_var_table({})
        assert "| Variable |" in table

    def test_sorted_output(self):
        from agent.tools.report_generator import _format_var_table
        table = _format_var_table({"z": 1.0, "a": 2.0})
        lines = table.strip().split("\n")
        assert "a" in lines[2]
        assert "z" in lines[3]


class TestFormatConstraintTable:
    """Test constraint table formatting."""

    def test_with_constraints(self):
        from agent.tools.report_generator import _format_constraint_table
        table = _format_constraint_table({"c1": 0.5, "c2": -0.3})
        assert "c1" in table
        assert "c2" in table

    def test_empty_constraints(self):
        from agent.tools.report_generator import _format_constraint_table
        table = _format_constraint_table({})
        assert table == ""


class TestReportGeneratorHandler:
    """Test the async handler."""

    @pytest.mark.asyncio
    async def test_generates_report(self, temp_dir, monkeypatch):
        import agent.tools.report_generator as rg
        monkeypatch.setattr(rg, "get_run_dir", lambda: temp_dir)
        output, is_error = await rg.report_generator_handler({
            "problem_description": "Maximize 3x + 2y",
            "problem_type": "LP",
            "variables": {"x": 10.0, "y": 0.0},
            "objective": 30.0,
            "status": "OPTIMAL",
            "solver": "highs",
        })
        assert not is_error
        assert "report.md" in output

    @pytest.mark.asyncio
    async def test_report_file_created(self, temp_dir, monkeypatch):
        import agent.tools.report_generator as rg
        monkeypatch.setattr(rg, "get_run_dir", lambda: temp_dir)
        output, is_error = await rg.report_generator_handler({
            "problem_description": "Test problem",
            "variables": {"x": 1.0},
            "objective": 1.0,
        })
        assert not is_error
        report_path = temp_dir / "report.md"
        assert report_path.exists()
        content = report_path.read_text(encoding="utf-8")
        assert "OR-Intern" in content

    @pytest.mark.asyncio
    async def test_latex_report_generation(self, temp_dir, monkeypatch):
        import agent.tools.report_generator as rg
        monkeypatch.setattr(rg, "get_run_dir", lambda: temp_dir)
        output, is_error = await rg.report_generator_handler({
            "problem_description": "Maximize 3x + 2y",
            "problem_type": "LP",
            "variables": {"x": 10.0, "y": 0.0},
            "objective": 30.0,
            "status": "OPTIMAL",
            "solver": "highs",
            "format": "latex",
        })
        assert not is_error
        assert "LaTeX" in output
        report_path = temp_dir / "report.tex"
        assert report_path.exists()
        content = report_path.read_text(encoding="utf-8")
        assert "\\documentclass" in content
        assert "\\begin{document}" in content


class TestLatexFormatting:
    """Test LaTeX formatting functions."""

    def test_var_table_latex(self):
        from agent.tools.report_generator import _format_var_table_latex
        table = _format_var_table_latex({"x": 10.0, "y": 5.0})
        assert "\\begin{tabular}" in table
        assert "\\toprule" in table
        assert "x &" in table

    def test_constraint_table_latex(self):
        from agent.tools.report_generator import _format_constraint_table_latex
        table = _format_constraint_table_latex({"c1": 0.5, "c2": 0.0})
        assert "\\begin{tabular}" in table
        assert "c1 &" in table
