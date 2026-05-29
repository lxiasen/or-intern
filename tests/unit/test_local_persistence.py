"""Unit tests for local_persistence module."""

import pytest
import json
from pathlib import Path


class TestLocalSessionStore:
    """Test LocalSessionStore class."""

    def test_init_creates_directory(self, temp_dir):
        from agent.core.local_persistence import LocalSessionStore
        store_dir = temp_dir / "test_sessions"
        store = LocalSessionStore(store_dir)
        assert store_dir.exists()

    def test_save_and_load_trajectory(self, temp_dir):
        from agent.core.local_persistence import LocalSessionStore
        store = LocalSessionStore(temp_dir)
        trajectory = {
            "problem_description": "Maximize x + y",
            "solver": "highs",
            "status": "OPTIMAL",
            "objective": 30.0,
            "variables": {"x": 10.0, "y": 20.0},
        }
        store.save_trajectory("test_session_1", trajectory)
        loaded = store.load_trajectory("test_session_1")
        assert loaded is not None
        assert loaded["problem_description"] == "Maximize x + y"
        assert loaded["objective"] == 30.0

    def test_load_nonexistent_session(self, temp_dir):
        from agent.core.local_persistence import LocalSessionStore
        store = LocalSessionStore(temp_dir)
        result = store.load_trajectory("nonexistent")
        assert result is None

    def test_list_sessions(self, temp_dir):
        from agent.core.local_persistence import LocalSessionStore
        store = LocalSessionStore(temp_dir)
        store.save_trajectory("session_1", {"problem_description": "Problem 1", "status": "OPTIMAL"})
        store.save_trajectory("session_2", {"problem_description": "Problem 2", "status": "INFEASIBLE"})
        sessions = store.list_sessions()
        assert len(sessions) == 2

    def test_delete_session(self, temp_dir):
        from agent.core.local_persistence import LocalSessionStore
        store = LocalSessionStore(temp_dir)
        store.save_trajectory("to_delete", {"problem_description": "Delete me"})
        assert store.delete_session("to_delete") is True
        assert store.load_trajectory("to_delete") is None

    def test_save_model(self, temp_dir):
        from agent.core.local_persistence import LocalSessionStore
        store = LocalSessionStore(temp_dir)
        model_code = "from pyomo.environ import *\nmodel = ConcreteModel()"
        path = store.save_model("session_1", model_code)
        assert path.exists()
        assert path.read_text(encoding="utf-8") == model_code

    def test_save_report(self, temp_dir):
        from agent.core.local_persistence import LocalSessionStore
        store = LocalSessionStore(temp_dir)
        report = "# Report\n\nOptimization results..."
        path = store.save_report("session_1", report)
        assert path.exists()
        assert "Report" in path.read_text(encoding="utf-8")


class TestTrajectoryHelpers:
    """Test trajectory helper functions."""

    def test_create_trajectory(self):
        from agent.core.local_persistence import create_trajectory_from_session
        traj = create_trajectory_from_session(
            problem_description="Test problem",
            solver="highs",
            status="OPTIMAL",
            objective=42.0,
        )
        assert traj["problem_description"] == "Test problem"
        assert traj["solver"] == "highs"
        assert "timestamps" in traj

    def test_format_trajectory_summary(self):
        from agent.core.local_persistence import format_trajectory_summary
        traj = {
            "session_id": "test_123",
            "problem_description": "Maximize x + y",
            "status": "OPTIMAL",
            "objective": 30.0,
            "solver": "highs",
            "variables": {"x": 10.0, "y": 20.0},
            "saved_at": "2024-01-01T00:00:00",
        }
        summary = format_trajectory_summary(traj)
        assert "Optimization Trajectory" in summary
        assert "test_123" in summary
        assert "OPTIMAL" in summary