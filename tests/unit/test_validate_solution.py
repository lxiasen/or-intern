"""Unit tests for validate_solution tool."""

import pytest


class TestValidateSolution:
    """Test solution validation."""

    @pytest.mark.asyncio
    async def test_feasible_solution(self, model_file):
        from agent.tools.validate_solution import validate_solution_handler
        output, has_violations = await validate_solution_handler({
            "model_path": model_file,
            "solution": {"x": 10.0, "y": 0.0},
        })
        assert not has_violations
        assert "FEASIBLE" in output

    @pytest.mark.asyncio
    async def test_infeasible_solution(self, model_file):
        from agent.tools.validate_solution import validate_solution_handler
        output, has_violations = await validate_solution_handler({
            "model_path": model_file,
            "solution": {"x": 20.0, "y": 5.0},
        })
        assert has_violations
        assert "VIOLATION" in output or "INFEASIBLE" in output

    @pytest.mark.asyncio
    async def test_missing_file(self):
        from agent.tools.validate_solution import validate_solution_handler
        output, _ = await validate_solution_handler({
            "model_path": "/nonexistent.py",
        })
        assert "Error" in output

    @pytest.mark.asyncio
    async def test_auto_solve_without_solution(self, model_file):
        """When no solution provided, should re-solve and check."""
        from agent.tools.validate_solution import validate_solution_handler
        output, has_violations = await validate_solution_handler({
            "model_path": model_file,
        })
        assert "FEASIBLE" in output or "violation" in output.lower()
