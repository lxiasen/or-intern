"""Unit tests for approval_policy."""

import pytest
from agent.config import Config


class TestSolverApproval:
    """Test solver approval rules."""

    @pytest.fixture
    def config(self):
        c = Config()
        c.approval.yolo_mode = False
        return c

    def test_higs_auto_approved(self, config):
        from agent.core.approval_policy import needs_solver_approval
        ok, reason = needs_solver_approval("highs", 60, config=config)
        assert not ok

    def test_gurobi_requires_approval(self, config):
        from agent.core.approval_policy import needs_solver_approval
        ok, reason = needs_solver_approval("gurobi", 60, config=config)
        assert ok
        assert "license" in reason.lower()

    def test_cplex_requires_approval(self, config):
        from agent.core.approval_policy import needs_solver_approval
        ok, reason = needs_solver_approval("cplex", 60, config=config)
        assert ok

    def test_large_timeout(self, config):
        from agent.core.approval_policy import needs_solver_approval
        ok, reason = needs_solver_approval("highs", 10000, config=config)
        assert ok
        assert "time" in reason.lower()

    def test_unknown_solver(self, config):
        from agent.core.approval_policy import needs_solver_approval
        ok, reason = needs_solver_approval("fantasy_solver_v2", 60, config=config)
        assert ok


class TestCostEstimation:
    """Test cost estimation."""

    def test_open_source_is_free(self):
        from agent.core.approval_policy import estimate_solve_cost
        cost = estimate_solve_cost("highs", 3600, 1000, 1000)
        assert cost == 0.0

    def test_commercial_has_cost(self):
        from agent.core.approval_policy import estimate_solve_cost
        cost = estimate_solve_cost("gurobi", 3600, 1000, 1000)
        assert cost > 0.0


class TestSolverClassification:
    """Test solver type classification."""

    def test_commercial_check(self):
        from agent.core.approval_policy import is_commercial_solver, is_open_source_solver
        assert is_commercial_solver("gurobi")
        assert is_commercial_solver("cplex")
        assert not is_commercial_solver("highs")

    def test_open_source_check(self):
        from agent.core.approval_policy import is_open_source_solver
        assert is_open_source_solver("highs")
        assert is_open_source_solver("scip")
        assert is_open_source_solver("glpk")
