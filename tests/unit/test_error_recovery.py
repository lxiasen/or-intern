"""Unit tests for error_recovery utilities."""

import pytest


class TestDiagnoseSolveFailure:
    """Test solve failure diagnosis."""

    def test_infeasible_diagnosis(self):
        from agent.tools.error_recovery import diagnose_solve_failure
        result = diagnose_solve_failure("INFEASIBLE")
        assert result["cause"] == "No feasible solution exists"
        assert len(result["suggestions"]) > 0
        assert result["auto_fix"] == "relax_constraints"

    def test_unbounded_diagnosis(self):
        from agent.tools.error_recovery import diagnose_solve_failure
        result = diagnose_solve_failure("UNBOUNDED")
        assert "without limit" in result["cause"]

    def test_timeout_diagnosis(self):
        from agent.tools.error_recovery import diagnose_solve_failure
        result = diagnose_solve_failure("TIME_LIMIT")
        assert "time limit" in result["cause"].lower()
        assert result["auto_fix"] == "increase_timeout"

    def test_numeric_diagnosis(self):
        from agent.tools.error_recovery import diagnose_solve_failure
        result = diagnose_solve_failure("NUMERIC_ERROR")
        assert "Numerical" in result["cause"]

    def test_solver_not_found(self):
        from agent.tools.error_recovery import diagnose_solve_failure
        result = diagnose_solve_failure("SOLVER_NOT_FOUND")
        assert "Solver" in result["cause"]

    def test_unknown_status(self):
        from agent.tools.error_recovery import diagnose_solve_failure
        result = diagnose_solve_failure("UNKNOWN_STATUS")
        assert result["status"] == "UNKNOWN_STATUS"


class TestSuggestSolverSwitch:
    """Test solver switch suggestions."""

    def test_lp_alternatives(self):
        from agent.tools.error_recovery import suggest_solver_switch
        suggestion = suggest_solver_switch("highs", "LP", 0)
        assert suggestion != "highs"
        assert suggestion in ["glpk", "scip", "cplex", "gurobi"]

    def test_mip_alternatives(self):
        from agent.tools.error_recovery import suggest_solver_switch
        suggestion = suggest_solver_switch("glpk", "MIP", 0)
        assert suggestion != "glpk"

    def test_nlp_alternatives(self):
        from agent.tools.error_recovery import suggest_solver_switch
        suggestion = suggest_solver_switch("ipopt", "NLP", 0)
        assert suggestion != "ipopt"


class TestFormatRecoveryReport:
    """Test recovery report formatting."""

    def test_basic_report(self):
        from agent.tools.error_recovery import format_recovery_report
        report = format_recovery_report(
            original_error="Solve failed",
            diagnosis={
                "status": "INFEASIBLE",
                "cause": "No feasible solution",
                "suggestions": ["Check constraints"],
                "auto_fix": None,
            },
            recovery_attempts=[
                {"number": 1, "description": "Switch to SCIP", "success": False, "error": "Still infeasible"},
                {"number": 2, "description": "Relax constraints", "success": True},
            ],
            final_status="OPTIMAL",
        )
        assert "Error Recovery Report" in report
        assert "No feasible solution" in report
        assert "Attempt 1" in report
        assert "Attempt 2" in report
        assert "OPTIMAL" in report

    def test_report_with_no_attempts(self):
        from agent.tools.error_recovery import format_recovery_report
        report = format_recovery_report(
            original_error="Import error",
            diagnosis={
                "status": "IMPORT_ERROR",
                "cause": "Missing module",
                "suggestions": ["Install pyomo"],
                "auto_fix": None,
            },
            recovery_attempts=[],
            final_status="FAILED",
        )
        assert "Import error" in report
        assert "Missing module" in report


class TestRetryOnFailure:
    """Test retry logic."""

    @pytest.mark.asyncio
    async def test_success_on_first_try(self):
        from agent.tools.error_recovery import retry_on_failure

        async def success_func():
            return "success", False

        result, is_error = await retry_on_failure(success_func)
        assert not is_error
        assert result == "success"

    @pytest.mark.asyncio
    async def test_success_after_retry(self):
        from agent.tools.error_recovery import retry_on_failure
        call_count = 0

        async def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                return "error", True
            return "success", False

        result, is_error = await retry_on_failure(flaky_func, max_retries=3, retry_delay=0.01)
        assert not is_error
        assert result == "success"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_failure_after_max_retries(self):
        from agent.tools.error_recovery import retry_on_failure

        async def always_fail():
            return "persistent error", True

        result, is_error = await retry_on_failure(always_fail, max_retries=2, retry_delay=0.01)
        assert is_error
        assert "3 attempts" in result
