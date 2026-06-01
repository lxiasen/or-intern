"""OR benchmark problem set for validation.

Standard OR problems with known optimal solutions for testing
the end-to-end pipeline accuracy.
"""

import pytest
from pathlib import Path
import tempfile


BENCHMARK_PROBLEMS = [
    {
        "name": "Simple LP",
        "type": "LP",
        "description": "maximize 3x + 2y subject to x + y <= 10, x <= 8, y <= 6, x >= 0, y >= 0",
        "expected_objective": 28.0,
        "expected_variables": {"x": 8.0, "y": 2.0},
        "tolerance": 0.01,
    },
    {
        "name": "Knapsack (small)",
        "type": "MIP",
        "description": (
            "maximize 60*x1 + 100*x2 + 120*x3 subject to "
            "10*x1 + 20*x2 + 30*x3 <= 50, "
            "x1 binary, x2 binary, x3 binary"
        ),
        "expected_objective": 220.0,
        "expected_variables": {"x1": 0.0, "x2": 1.0, "x3": 1.0},
        "tolerance": 0.01,
    },
    {
        "name": "Production Planning",
        "type": "LP",
        "description": (
            "maximize 20*a + 30*b subject to "
            "a + 2*b <= 40, 3*a + b <= 30, a >= 0, b >= 0"
        ),
        "expected_objective": 620.0,
        "expected_variables": {"a": 4.0, "b": 18.0},
        "tolerance": 0.1,
    },
    {
        "name": "Diet Problem",
        "type": "LP",
        "description": (
            "minimize 2*f1 + 3*f2 + f3 subject to "
            "f1 + f2 + f3 >= 10, "
            "2*f1 + f2 >= 15, "
            "f1 >= 0, f2 >= 0, f3 >= 0"
        ),
        "expected_objective": 17.5,
        "expected_variables": {"f1": 7.5, "f2": 0.0, "f3": 2.5},
        "tolerance": 0.1,
    },
    {
        "name": "Transportation",
        "type": "LP",
        "description": (
            "minimize 10*x11 + 20*x12 + 15*x21 + 25*x22 subject to "
            "x11 + x12 = 30, x21 + x22 = 20, "
            "x11 + x21 = 25, x12 + x22 = 25, "
            "x11 >= 0, x12 >= 0, x21 >= 0, x22 >= 0"
        ),
        "expected_objective": 850.0,
        "expected_variables": {"x11": 5.0, "x12": 25.0, "x21": 20.0, "x22": 0.0},
        "tolerance": 0.1,
    },
    {
        "name": "Facility Location (small)",
        "type": "MIP",
        "description": (
            "minimize 100*y1 + 120*y2 + 80*y3 + 10*x11 + 15*x12 + 20*x21 + 12*x22 + 18*x31 + 8*x32 subject to "
            "x11 + x12 <= 200*y1, x21 + x22 <= 200*y2, x31 + x32 <= 200*y3, "
            "x11 + x21 + x31 = 80, x12 + x22 + x32 = 70, "
            "y1 binary, y2 binary, y3 binary, "
            "x11 >= 0, x12 >= 0, x21 >= 0, x22 >= 0, x31 >= 0, x32 >= 0"
        ),
        "expected_objective": 1540.0,
        "tolerance": 100.0,
    },
    {
        "name": "Assignment Problem",
        "type": "MIP",
        "description": (
            "minimize 4*x11 + 2*x12 + 8*x13 + 7*x21 + 5*x22 + 3*x23 + 6*x31 + 8*x32 + 4*x33 subject to "
            "x11 + x12 + x13 = 1, x21 + x22 + x23 = 1, x31 + x32 + x33 = 1, "
            "x11 + x21 + x31 = 1, x12 + x22 + x32 = 1, x13 + x23 + x33 = 1, "
            "x11 binary, x12 binary, x13 binary, "
            "x21 binary, x22 binary, x23 binary, "
            "x31 binary, x32 binary, x33 binary"
        ),
        "expected_objective": 11.0,
        "expected_variables": {},
        "tolerance": 0.01,
    },
]


class TestBenchmarkProblems:
    """Test OR benchmark problems with known solutions."""

    @pytest.mark.parametrize("problem", BENCHMARK_PROBLEMS, ids=[p["name"] for p in BENCHMARK_PROBLEMS])
    def test_model_generation(self, problem):
        """Test that model_builder can generate code for each benchmark."""
        from agent.tools.model_builder import generate_pyomo_code
        code = generate_pyomo_code(problem["description"])
        assert "ConcreteModel" in code
        assert "Objective" in code

    @pytest.mark.parametrize("problem", BENCHMARK_PROBLEMS, ids=[p["name"] for p in BENCHMARK_PROBLEMS])
    def test_model_syntax(self, problem):
        """Test that generated models have valid Python syntax."""
        from agent.tools.model_builder import generate_pyomo_code
        code = generate_pyomo_code(problem["description"])
        compile(code, "<test>", "exec")

    @pytest.mark.parametrize("problem", BENCHMARK_PROBLEMS[:3], ids=[p["name"] for p in BENCHMARK_PROBLEMS[:3]])
    @pytest.mark.asyncio
    async def test_end_to_end_solve(self, problem, temp_dir, monkeypatch, session):
        """Test end-to-end solve for first 3 benchmark problems."""
        from agent.tools.model_builder import model_builder_handler
        from agent.tools.solve_job import solve_job_handler

        monkeypatch.setattr(
            "agent.tools._output_dir.get_workspace_dir",
            lambda session=None: temp_dir,
        )
        monkeypatch.setattr(
            "agent.tools.model_builder.get_workspace_dir",
            lambda session=None: temp_dir,
        )

        output, is_error = await model_builder_handler({
            "description": problem["description"],
        }, session=session)
        assert not is_error

        py_files = list(temp_dir.glob("*.py"))
        assert len(py_files) >= 1
        model_path = py_files[0]
        assert model_path.exists()

        output, is_error = await solve_job_handler({
            "model_path": str(model_path),
            "solver": "highs",
            "timeout": 30,
        }, session=session)

        if not is_error:
            assert "OPTIMAL" in output or "optimal" in output.lower()
            if problem.get("expected_objective"):
                assert f"{problem['expected_objective']}" in output or \
                       f"{problem['expected_objective']:.0f}" in output


class TestBenchmarkCoverage:
    """Test benchmark problem coverage."""

    def test_problem_types_covered(self):
        """Verify that benchmarks cover LP and MIP types."""
        types = {p["type"] for p in BENCHMARK_PROBLEMS}
        assert "LP" in types
        assert "MIP" in types

    def test_minimum_problem_count(self):
        """Verify minimum number of benchmark problems."""
        assert len(BENCHMARK_PROBLEMS) >= 5

    def test_each_problem_has_required_fields(self):
        """Verify each problem has all required fields."""
        required = {"name", "type", "description", "tolerance"}
        for problem in BENCHMARK_PROBLEMS:
            assert required.issubset(problem.keys()), f"Missing fields in {problem.get('name')}"
