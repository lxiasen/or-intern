"""OR-Intern Benchmark Suite.

Two tiers:
- Tier 1: Direct tool chain (model_builder → solve_job → validate)
  Simple structured LP problems that model_builder can parse directly.
- Tier 2: Agent-driven (full LLM agent pipeline)
  Complex narrative problems requiring the agent to reason and convert.

Run: uv run pytest tests/benchmarks/test_benchmarks.py -v
"""

import asyncio
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


# ── Tier 1: Direct tool chain benchmarks ──

TIER1_BENCHMARKS = [
    {
        "name": "01_simple_lp",
        "description": "maximize 3x + 2y subject to x + y <= 10, x >= 0, y >= 0",
        "expected_obj": 30.0,
        "expected_vars": {"x": 10.0, "y": 0.0},
    },
    {
        "name": "02_two_constraint_lp",
        "description": "maximize 2x + 5y subject to 3x + 4y <= 24, x <= 5, y <= 4, x >= 0, y >= 0",
        "expected_obj": 25.333,
    },
    {
        "name": "03_minimization",
        "description": "minimize 4x + 3y subject to 2x + y >= 10, x + 2y >= 8, x >= 0, y >= 0",
        "expected_obj": None,  # Verify solve succeeds
    },
    {
        "name": "04_three_variable",
        "description": "maximize 5x + 4y + 3z subject to 2x + 3y + z <= 30, x + 2y + 3z <= 25, x >= 0, y >= 0, z >= 0",
        "expected_obj": None,
    },
    {
        "name": "05_resource_allocation",
        "description": "maximize 10x + 15y subject to 2x + 3y <= 100, 4x + 2y <= 120, x <= 30, y <= 25, x >= 0, y >= 0",
        "expected_obj": None,
    },
    {
        "name": "06_production_planning",
        "description": "maximize 40x + 30y subject to 2x + 4y <= 100, 3x + y <= 90, x >= 0, y >= 0",
        "expected_obj": 1400.0,
        "expected_vars": {"x": 26.0, "y": 12.0},
    },
]

# Tier 2 problems require the full LLM agent (not tested here — see integration tests)
TIER2_BENCHMARKS = [
    "Transportation: 3 warehouses, 4 stores with capacities/demands/costs",
    "Blending: 3 ingredients, nutrition constraints",
    "Portfolio: 4 assets, risk/return/diversification",
    "Workforce scheduling: 7-day, 5-consecutive-day shifts",
]


class TestTier1Benchmarks:
    """Direct tool chain: model_builder → solve_job → validate."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("bm", TIER1_BENCHMARKS, ids=[b["name"] for b in TIER1_BENCHMARKS])
    async def test_solve_and_validate(self, bm):
        from agent.tools.model_builder import model_builder_handler
        from agent.tools.solve_job import solve_job_handler
        from agent.tools.validate_solution import validate_solution_handler

        # 1. Build
        out, err = await model_builder_handler({"description": bm["description"]})
        assert not err, f"model_builder: {out[:200]}"
        m = re.search(r'(?:Model file\*\*|model_path):\s*(.+)', out)
        assert m, f"No model path: {out[:200]}"
        model_path = m.group(1).strip().strip("'")

        # 2. Solve
        sol, err = await solve_job_handler({
            "operation": "run", "model_path": model_path,
            "solver": "highs", "timeout": 60,
        })
        assert not err, f"solve: {sol[:200]}"
        assert "OPTIMAL" in sol, f"Not optimal: {sol[:200]}"

        # 3. Check objective
        if bm["expected_obj"] is not None:
            obj_m = re.search(r'(?:Objective value|OBJECTIVE|objective)[\*\s:]+([\d.]+)', sol, re.IGNORECASE)
            assert obj_m, f"No objective in output: {sol[:200]}"
            actual = float(obj_m.group(1))
            assert abs(actual - bm["expected_obj"]) < 0.2, (
                f"Obj mismatch: expected {bm['expected_obj']}, got {actual}"
            )

        # 4. Validate
        if bm.get("expected_vars"):
            val, has_v = await validate_solution_handler({
                "model_path": model_path, "solution": bm["expected_vars"],
            })
            assert not has_v, f"Validation: {val[:200]}"


class TestSolveSuccessRate:
    """Verify >= 80% Tier 1 success rate."""

    @pytest.mark.asyncio
    async def test_tier1_success_rate(self):
        from agent.tools.model_builder import model_builder_handler
        from agent.tools.solve_job import solve_job_handler

        passed = 0
        for bm in TIER1_BENCHMARKS:
            try:
                out, err = await model_builder_handler({"description": bm["description"]})
                if err: continue
                m = re.search(r'(?:Model file\*\*|model_path):\s*(.+)', out)
                if not m: continue
                sol, err = await solve_job_handler({
                    "operation": "run", "model_path": m.group(1).strip().strip("'"),
                    "solver": "highs", "timeout": 60,
                })
                if "OPTIMAL" in sol:
                    passed += 1
            except Exception:
                pass

        rate = passed / len(TIER1_BENCHMARKS) * 100
        assert rate >= 80, f"Tier 1 rate: {passed}/{len(TIER1_BENCHMARKS)} = {rate:.0f}%"


class TestFullPipeline:
    """End-to-end: model_builder → solver_selector → solve_job → validate → sensitivity → visualization → report."""

    @pytest.mark.asyncio
    async def test_full_pipeline_simple_lp(self):
        """Test the complete 6-phase pipeline on a simple LP."""
        from agent.tools.model_builder import model_builder_handler
        from agent.tools.solver_selector import solver_selector_handler
        from agent.tools.solve_job import solve_job_handler
        from agent.tools.validate_solution import validate_solution_handler
        from agent.tools.sensitivity_analysis import sensitivity_analysis_handler
        from agent.tools.visualization import visualization_handler
        from agent.tools.report_generator import report_generator_handler

        desc = "maximize 5x + 3y subject to 2x + y <= 20, x + 3y <= 30, x >= 0, y >= 0"

        # Phase 1: Model
        model_out, err = await model_builder_handler({"description": desc})
        assert not err, f"Phase 1: {model_out[:200]}"
        m = re.search(r'(?:Model file\*\*|model_path):\s*(.+)', model_out)
        assert m, f"No model path: {model_out[:200]}"
        model_path = m.group(1).strip().strip("'")

        # Phase 2: Solve
        sol_out, err = await solver_selector_handler({"description": desc})
        assert not err, f"solver_selector: {sol_out[:200]}"

        sol_out, err = await solve_job_handler({"model_path": model_path, "solver": "highs"})
        assert not err, f"Phase 2: {sol_out[:200]}"
        assert "OPTIMAL" in sol_out

        # Phase 3: Validate
        val_out, err = await validate_solution_handler({"model_path": model_path})
        assert not err, f"Phase 3: {val_out[:200]}"
        assert "FEASIBLE" in val_out

        # Phase 4: Sensitivity
        sens_out, err = await sensitivity_analysis_handler({"model_path": model_path, "operation": "dual"})
        assert not err, f"Phase 4: {sens_out[:200]}"

        # Phase 5: Visualize
        viz_out, err = await visualization_handler({"variables": {"x": 13.0, "y": 0.0}, "objective": 65.0})
        # viz may fail if matplotlib not installed, skip gracefully
        if err and "matplotlib" in str(viz_out):
            pytest.skip("matplotlib not installed")

        # Phase 6: Report
        rep_out, err = await report_generator_handler({
            "problem_description": desc, "objective": 65.0,
            "variables": {"x": 13.0, "y": 0.0}, "constraints": {"c1": 0.0},
            "status": "OPTIMAL",
        })
        assert not err, f"Phase 6: {rep_out[:200]}"
        assert "Report Generated" in rep_out

    @pytest.mark.asyncio
    async def test_full_pipeline_minimization(self):
        """Test pipeline on a minimization problem."""
        from agent.tools.model_builder import model_builder_handler
        from agent.tools.solve_job import solve_job_handler
        from agent.tools.validate_solution import validate_solution_handler
        from agent.tools.sensitivity_analysis import sensitivity_analysis_handler

        desc = "minimize 4x + 6y subject to x + 2y >= 8, 3x + 2y >= 12, x >= 0, y >= 0"

        out, err = await model_builder_handler({"description": desc})
        assert not err
        m = re.search(r'(?:Model file\*\*|model_path):\s*(.+)', out)
        model_path = m.group(1).strip().strip("'")

        sol, err = await solve_job_handler({"model_path": model_path, "solver": "highs"})
        assert not err
        assert "OPTIMAL" in sol

        val, err = await validate_solution_handler({"model_path": model_path})
        assert not err

        sens, err = await sensitivity_analysis_handler({"model_path": model_path, "operation": "dual"})
        assert not err

    @pytest.mark.asyncio
    async def test_full_pipeline_infeasible(self):
        """Infeasible problem should diagnose, not crash."""
        from agent.tools.model_builder import model_builder_handler
        from agent.tools.solve_job import solve_job_handler
        from agent.tools.validate_solution import validate_solution_handler
        from agent.tools.sensitivity_analysis import sensitivity_analysis_handler

        desc = "maximize x + y subject to x + y >= 100, x <= 10, y <= 10, x >= 0, y >= 0"

        out, err = await model_builder_handler({"description": desc})
        assert not err
        m = re.search(r'(?:Model file\*\*|model_path):\s*(.+)', out)
        model_path = m.group(1).strip().strip("'")

        sol, err = await solve_job_handler({"model_path": model_path, "solver": "highs"})
        # Should either fail (err=True) or report infeasible status
        if not err:
            assert "INFEASIBLE" in sol or "infeasible" in sol.lower()
        # validate and sensitivity should not crash on infeasible models
        await validate_solution_handler({"model_path": model_path})
        await sensitivity_analysis_handler({"model_path": model_path})
