"""Integration tests for OR-Intern tool chain."""

import pytest
import re


class TestModelBuildSolveValidate:
    """End-to-end: model_builder → solve_job → validate_solution."""

    @pytest.mark.asyncio
    async def test_full_lp_workflow(self, session):
        """Test complete LP workflow from description to validated solution."""
        from agent.tools.model_builder import model_builder_handler
        from agent.tools.solve_job import solve_job_handler
        from agent.tools.validate_solution import validate_solution_handler

        # 1. Build model
        out, err = await model_builder_handler({
            "description": "maximize 3x + 2y subject to x + y <= 10, x >= 0, y >= 0"
        }, session=session)
        assert not err, f"model_builder failed: {out}"
        m = re.search(r'Model file\*\*: (.+)', out)
        assert m, "No model file in output"
        model_path = m.group(1).strip()

        # 2. Solve
        sol, err = await solve_job_handler({
            "operation": "run", "model_path": model_path,
            "solver": "highs", "timeout": 30
        }, session=session)
        assert not err, f"solve failed: {sol}"
        assert "OPTIMAL" in sol
        assert "30.0" in sol

        # 3. Validate
        val, has_v = await validate_solution_handler({
            "model_path": model_path,
            "solution": {"x": 10.0, "y": 0.0},
        })
        assert not has_v, f"validation found violations: {val}"


class TestSolverSelectorIntegration:
    """Test solver_selector recommendations."""

    @pytest.mark.asyncio
    async def test_recommend_lp(self):
        from agent.tools.solver_selector import solver_selector_handler
        out, err = await solver_selector_handler({
            "operation": "recommend",
            "problem_type": "LP",
            "prefer_open_source": True,
        })
        assert not err
        assert "highs" in out.lower()

    @pytest.mark.asyncio
    async def test_list_solvers(self):
        from agent.tools.solver_selector import solver_selector_handler
        out, err = await solver_selector_handler({"operation": "list"})
        assert not err
        assert "highs" in out.lower()
        assert "gurobi" in out.lower()


class TestDataHandlerIntegration:
    """Test data_handler with real files."""

    @pytest.mark.asyncio
    async def test_csv_inspect(self, temp_dir):
        from agent.tools.data_handler import data_handler_handler
        csv_path = temp_dir / "test.csv"
        csv_path.write_text("city,x,y\nA,10,20\nB,30,40\n", encoding="utf-8")

        out, err = await data_handler_handler({
            "file_path": str(csv_path), "operation": "inspect"
        })
        assert not err
        assert "tabular" in out.lower()

    @pytest.mark.asyncio
    async def test_csv_convert(self, temp_dir):
        from agent.tools.data_handler import data_handler_handler
        csv_path = temp_dir / "test.csv"
        csv_path.write_text("city,x,y\nA,10,20\nB,30,40\n", encoding="utf-8")

        out, err = await data_handler_handler({
            "file_path": str(csv_path), "operation": "convert"
        })
        assert not err
        assert "Pyomo" in out


class TestReportGeneration:
    """Test report generator with solve results."""

    @pytest.mark.asyncio
    async def test_generate_report(self):
        from agent.tools.report_generator import report_generator_handler
        out, err = await report_generator_handler({
            "problem_description": "maximize 3x+2y s.t. x+y<=10",
            "objective": 30.0,
            "variables": {"x": 10.0, "y": 0.0},
            "solver": "HiGHS",
            "status": "OPTIMAL",
        })
        assert not err
        assert "30.0" in out or "Report" in out


class TestToolRegistration:
    """Verify all tools are registered."""

    def test_all_tools_registered(self):
        from agent.core.tools import create_builtin_tools
        tools = create_builtin_tools()
        names = {t.name for t in tools}
        assert len(tools) == 20
        for required in ["model_builder", "solve_job", "validate_solution",
                         "sensitivity_analysis", "visualization", "report_generator",
                         "compare_solvers", "or_papers", "data_handler",
                         "solver_selector", "research", "problem_templates",
                         "model_checker"]:
            assert required in names, f"Missing tool: {required}"
