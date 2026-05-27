"""Unit tests for solve_job tool."""

import pytest


class TestSolveJob:
    """Test solve_job handler with a real model file."""

    @pytest.mark.asyncio
    async def test_solve_simple_lp(self, model_file):
        from agent.tools.solve_job import solve_job_handler
        output, is_error = await solve_job_handler({
            "operation": "run",
            "model_path": model_file,
            "solver": "highs",
            "timeout": 30,
        })
        assert not is_error
        assert "OPTIMAL" in output
        assert "30.0" in output

    @pytest.mark.asyncio
    async def test_solve_missing_file(self):
        from agent.tools.solve_job import solve_job_handler
        output, is_error = await solve_job_handler({
            "operation": "run",
            "model_path": "/nonexistent/model.py",
        })
        assert is_error

    @pytest.mark.asyncio
    async def test_status_operation(self):
        from agent.tools.solve_job import solve_job_handler
        output, is_error = await solve_job_handler({"operation": "status"})
        assert not is_error
        assert "highs" in output.lower()


class TestParseSolution:
    """Test solution output parsing."""

    def test_parse_optimal(self):
        from agent.tools.solve_job import _parse_solution
        r = _parse_solution("STATUS: optimal\nOBJECTIVE: 30.0\n  x = 10.0\n  y = 0.0\n")
        assert r["status"] == "OPTIMAL"
        assert r["objective"] == 30.0
        assert r["variables"]["x"] == 10.0

    def test_parse_infeasible(self):
        from agent.tools.solve_job import _parse_solution
        r = _parse_solution("STATUS: infeasible\n")
        assert r["status"] == "INFEASIBLE"

    def test_parse_empty(self):
        from agent.tools.solve_job import _parse_solution
        r = _parse_solution("")
        assert r["status"] == "UNKNOWN"
        assert r["objective"] is None
