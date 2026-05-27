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
