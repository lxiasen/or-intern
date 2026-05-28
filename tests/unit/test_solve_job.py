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
        from agent.tools.solve_job import _parse_solution_from_output
        r = _parse_solution_from_output("STATUS: optimal\nOBJECTIVE: 30.0\n  x = 10.0\n  y = 0.0\n")
        assert r.status == "OPTIMAL"
        assert r.objective == 30.0
        assert r.variables["x"] == 10.0

    def test_parse_infeasible(self):
        from agent.tools.solve_job import _parse_solution_from_output
        r = _parse_solution_from_output("STATUS: infeasible\n")
        assert r.status == "INFEASIBLE"

    def test_parse_empty(self):
        from agent.tools.solve_job import _parse_solution_from_output
        r = _parse_solution_from_output("")
        assert r.status == "UNKNOWN"
        assert r.objective is None


class TestProgressParser:
    """Test HiGHS progress log parsing."""

    def test_parse_highs_mip_line(self):
        from agent.tools.solve_job import _parse_hipghs_progress
        import time
        t0 = time.monotonic()
        snap = _parse_hipghs_progress(
            "       1       0         1 100.00%   28              28               0.00%",
            t0,
        )
        assert snap is not None
        assert snap.nodes == 1
        assert snap.iterations == 0

    def test_parse_highs_lp_line(self):
        from agent.tools.solve_job import _parse_hipghs_progress
        import time
        t0 = time.monotonic()
        snap = _parse_hipghs_progress(
            "          2     3.2500000000e+01",
            t0,
        )
        assert snap is not None
        assert snap.iterations == 2
        assert abs(snap.best_bound - 32.5) < 0.01

    def test_parse_non_progress_line(self):
        from agent.tools.solve_job import _parse_hipghs_progress
        import time
        t0 = time.monotonic()
        snap = _parse_hipghs_progress("Running HiGHS 1.7.0", t0)
        assert snap is None
