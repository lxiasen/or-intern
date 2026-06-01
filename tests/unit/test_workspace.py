"""Unit tests for workspace directory management."""

import json
import pytest
from pathlib import Path


class TestGetWorkspaceDir:

    def test_returns_default_when_no_session(self):
        from agent.tools._output_dir import get_workspace_dir
        result = get_workspace_dir(None)
        assert result.exists()
        assert result.name == "default"

    def test_returns_session_prefix_dir(self, tmp_path, monkeypatch):
        from agent.tools._output_dir import get_workspace_dir
        from agent.tools import _output_dir
        monkeypatch.setattr(_output_dir, "_OUTPUTS_ROOT", tmp_path)

        class FakeSession:
            session_id = "abcdef12-3456-7890"

        result = get_workspace_dir(FakeSession())
        assert result.exists()
        assert result.name == "abcdef12"
        assert result.parent == tmp_path

    def test_fallback_when_no_session_id(self, tmp_path, monkeypatch):
        from agent.tools._output_dir import get_workspace_dir
        from agent.tools import _output_dir
        monkeypatch.setattr(_output_dir, "_OUTPUTS_ROOT", tmp_path)

        class FakeSession:
            pass

        result = get_workspace_dir(FakeSession())
        assert result.name == "default"


class TestSuggestFilename:

    def test_first_file_no_suffix(self, tmp_path):
        from agent.tools._output_dir import suggest_filename
        result = suggest_filename(tmp_path, "model", ".py")
        assert result == "model.py"

    def test_second_file_gets_v2(self, tmp_path):
        from agent.tools._output_dir import suggest_filename
        (tmp_path / "model.py").write_text("x = 1")
        result = suggest_filename(tmp_path, "model", ".py")
        assert result == "model_v2.py"

    def test_third_file_gets_v3(self, tmp_path):
        from agent.tools._output_dir import suggest_filename
        (tmp_path / "model.py").write_text("x = 1")
        (tmp_path / "model_v2.py").write_text("x = 2")
        result = suggest_filename(tmp_path, "model", ".py")
        assert result == "model_v3.py"

    def test_custom_base_name(self, tmp_path):
        from agent.tools._output_dir import suggest_filename
        result = suggest_filename(tmp_path, "model_relaxed", ".py")
        assert result == "model_relaxed.py"


class TestRecordFile:

    def test_creates_state_file(self, tmp_path):
        from agent.tools._output_dir import record_file
        record_file(tmp_path, "test.py", file_type="pyomo_model", tool="model_builder")
        state_path = tmp_path / ".workspace_state.json"
        assert state_path.exists()

    def test_records_file_metadata(self, tmp_path):
        from agent.tools._output_dir import record_file
        record_file(tmp_path, "model_v1.py", file_type="pyomo_model",
                     tool="model_builder", note="LP model")
        state_path = tmp_path / ".workspace_state.json"
        state = json.loads(state_path.read_text())
        assert len(state["files"]) == 1
        assert state["files"][0]["name"] == "model_v1.py"
        assert state["files"][0]["type"] == "pyomo_model"
        assert state["files"][0]["tool"] == "model_builder"
        assert state["files"][0]["note"] == "LP model"

    def test_updates_existing_file(self, tmp_path):
        from agent.tools._output_dir import record_file
        record_file(tmp_path, "model.py", file_type="pyomo_model", note="v1")
        record_file(tmp_path, "model.py", file_type="pyomo_model", note="v2 updated")
        state_path = tmp_path / ".workspace_state.json"
        state = json.loads(state_path.read_text())
        assert len(state["files"]) == 1
        assert state["files"][0]["note"] == "v2 updated"

    def test_multiple_files(self, tmp_path):
        from agent.tools._output_dir import record_file
        record_file(tmp_path, "model.py", file_type="pyomo_model")
        record_file(tmp_path, "report.md", file_type="report")
        record_file(tmp_path, "variables.png", file_type="chart")
        state_path = tmp_path / ".workspace_state.json"
        state = json.loads(state_path.read_text())
        assert len(state["files"]) == 3


class TestLoadWorkspaceState:

    def test_empty_state_when_no_file(self, tmp_path):
        from agent.tools._output_dir import load_workspace_state
        state = load_workspace_state(tmp_path)
        assert state["files"] == []

    def test_loads_existing_state(self, tmp_path):
        from agent.tools._output_dir import save_workspace_state, load_workspace_state
        save_workspace_state(tmp_path, {"files": [{"name": "test.py"}], "created": "2026-01-01"})
        state = load_workspace_state(tmp_path)
        assert len(state["files"]) == 1
        assert state["files"][0]["name"] == "test.py"

    def test_handles_corrupted_json(self, tmp_path):
        from agent.tools._output_dir import load_workspace_state
        (tmp_path / ".workspace_state.json").write_text("{invalid json")
        state = load_workspace_state(tmp_path)
        assert state["files"] == []


class TestListWorkspaceFiles:

    def test_empty_workspace(self, tmp_path):
        from agent.tools._output_dir import list_workspace_files
        result = list_workspace_files(tmp_path)
        assert result == ""

    def test_nonexistent_workspace(self, tmp_path):
        from agent.tools._output_dir import list_workspace_files
        result = list_workspace_files(tmp_path / "nonexistent")
        assert result == ""

    def test_lists_recorded_files(self, tmp_path):
        from agent.tools._output_dir import record_file, list_workspace_files
        (tmp_path / "model.py").write_text("x = 1")
        record_file(tmp_path, "model.py", file_type="pyomo_model")
        result = list_workspace_files(tmp_path)
        assert "model.py" in result
        assert "pyomo_model" in result

    def test_lists_unrecorded_files(self, tmp_path):
        from agent.tools._output_dir import list_workspace_files
        (tmp_path / "extra.py").write_text("x = 1")
        result = list_workspace_files(tmp_path)
        assert "extra.py" in result

    def test_excludes_state_file(self, tmp_path):
        from agent.tools._output_dir import list_workspace_files
        (tmp_path / ".workspace_state.json").write_text('{"files": []}')
        result = list_workspace_files(tmp_path)
        assert ".workspace_state.json" not in result


class TestClearRunMarker:

    def test_is_noop(self):
        from agent.tools._output_dir import clear_run_marker
        clear_run_marker()


class TestGetRunDirBackwardCompat:

    def test_returns_default_workspace(self):
        from agent.tools._output_dir import get_run_dir
        result = get_run_dir()
        assert result.exists()
        assert result.name == "default"


class TestWorkspaceIntegration:
    """Integration tests for workspace + tool handler interaction."""

    @pytest.mark.asyncio
    async def test_model_builder_writes_to_workspace(self, tmp_path, monkeypatch, session):
        from agent.tools import model_builder as mb
        monkeypatch.setattr(mb, "get_workspace_dir", lambda session=None: tmp_path)
        output, is_error = await mb.model_builder_handler({
            "description": "maximize x + y subject to x + y <= 10, x >= 0, y >= 0",
        }, session=session)
        assert not is_error
        py_files = list(tmp_path.glob("*.py"))
        assert len(py_files) >= 1

    @pytest.mark.asyncio
    async def test_model_builder_custom_filename(self, tmp_path, monkeypatch, session):
        from agent.tools import model_builder as mb
        monkeypatch.setattr(mb, "get_workspace_dir", lambda session=None: tmp_path)
        output, is_error = await mb.model_builder_handler({
            "description": "maximize x + y subject to x + y <= 10, x >= 0, y >= 0",
            "filename": "my_custom_model.py",
        }, session=session)
        assert not is_error
        assert (tmp_path / "my_custom_model.py").exists()

    @pytest.mark.asyncio
    async def test_model_builder_auto_version(self, tmp_path, monkeypatch, session):
        from agent.tools import model_builder as mb
        monkeypatch.setattr(mb, "get_workspace_dir", lambda session=None: tmp_path)

        await mb.model_builder_handler({
            "description": "maximize x + y subject to x + y <= 10, x >= 0, y >= 0",
        }, session=session)
        await mb.model_builder_handler({
            "description": "maximize 2x + 3y subject to x + y <= 20, x >= 0, y >= 0",
        }, session=session)
        py_files = sorted(tmp_path.glob("*.py"))
        assert len(py_files) == 2
        names = {f.name for f in py_files}
        assert "model.py" in names
        assert "model_v2.py" in names

    @pytest.mark.asyncio
    async def test_report_generator_custom_filename(self, tmp_path, monkeypatch, session):
        from agent.tools import report_generator as rg
        monkeypatch.setattr(rg, "get_workspace_dir", lambda session=None: tmp_path)
        output, is_error = await rg.report_generator_handler({
            "problem_description": "Test",
            "variables": {"x": 1.0},
            "objective": 1.0,
            "filename": "final_report.md",
        }, session=session)
        assert not is_error
        assert (tmp_path / "final_report.md").exists()
