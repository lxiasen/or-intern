"""Unit tests for solver_selector tool."""

import pytest


class TestSolverSelectorSpec:
    """Test tool specification."""

    def test_spec_has_required_fields(self):
        from agent.tools.solver_selector import SOLVER_SELECTOR_TOOL_SPEC
        spec = SOLVER_SELECTOR_TOOL_SPEC
        assert spec["name"] == "solver_selector"
        assert "parameters" in spec

    def test_spec_operations(self):
        from agent.tools.solver_selector import SOLVER_SELECTOR_TOOL_SPEC
        ops = SOLVER_SELECTOR_TOOL_SPEC["parameters"]["properties"]["operation"]
        assert "recommend" in ops["enum"]
        assert "list" in ops["enum"]


class TestDetectProblemSize:
    """Test problem size detection."""

    def test_small_by_default(self):
        from agent.tools.solver_selector import _detect_problem_size
        assert _detect_problem_size("") == "small"

    def test_large_keywords(self):
        from agent.tools.solver_selector import _detect_problem_size
        assert _detect_problem_size("a large problem with thousands of variables") == "large"

    def test_medium_keywords(self):
        from agent.tools.solver_selector import _detect_problem_size
        assert _detect_problem_size("a medium size problem with hundreds of constraints") == "medium"


class TestRecommendSolver:
    """Test solver recommendation logic."""

    def test_lp_recommends_highs(self):
        from agent.tools.solver_selector import recommend_solver
        rec = recommend_solver("LP", "small", prefer_open_source=True)
        assert rec["solver"] == "highs"
        assert rec["type"] == "open_source"

    def test_mip_recommends_open_source(self):
        from agent.tools.solver_selector import recommend_solver
        rec = recommend_solver("MIP", "small", prefer_open_source=True)
        assert rec["type"] == "open_source"

    def test_nlp_fallback(self):
        from agent.tools.solver_selector import recommend_solver
        rec = recommend_solver("NLP", "small", prefer_open_source=True)
        assert rec["solver"] is not None

    def test_gurobi_with_prefer_commercial(self):
        from agent.tools.solver_selector import recommend_solver
        rec = recommend_solver("LP", "large", prefer_open_source=False)
        assert rec["solver"] is not None

    def test_returns_params(self):
        from agent.tools.solver_selector import recommend_solver
        rec = recommend_solver("MIP", "large", prefer_open_source=True)
        assert "params" in rec


class TestListAvailableSolvers:
    """Test solver listing."""

    def test_returns_list(self):
        from agent.tools.solver_selector import list_available_solvers
        solvers = list_available_solvers()
        assert isinstance(solvers, list)
        assert len(solvers) > 0

    def test_each_solver_has_required_fields(self):
        from agent.tools.solver_selector import list_available_solvers
        solvers = list_available_solvers()
        for s in solvers:
            assert "name" in s
            assert "key" in s
            assert "type" in s
            assert "supports" in s
            assert "available" in s


class TestSolverSelectorHandler:
    """Test the async handler."""

    @pytest.mark.asyncio
    async def test_list_operation(self):
        from agent.tools.solver_selector import solver_selector_handler
        output, is_error = await solver_selector_handler({
            "operation": "list"
        })
        assert not is_error
        assert "Solvers" in output

    @pytest.mark.asyncio
    async def test_recommend_lp(self):
        from agent.tools.solver_selector import solver_selector_handler
        output, is_error = await solver_selector_handler({
            "operation": "recommend",
            "problem_type": "LP",
        })
        assert not is_error
        assert "Solver Recommendation" in output

    @pytest.mark.asyncio
    async def test_recommend_mip(self):
        from agent.tools.solver_selector import solver_selector_handler
        output, is_error = await solver_selector_handler({
            "operation": "recommend",
            "problem_type": "MIP",
            "problem_description": "a large MIP problem",
        })
        assert not is_error
        assert "Solver Recommendation" in output
