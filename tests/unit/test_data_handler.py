"""Unit tests for data_handler tool."""

import pytest
import json
from pathlib import Path


class TestDataHandlerSpec:
    """Test tool specification."""

    def test_spec_has_required_fields(self):
        from agent.tools.data_handler import DATA_HANDLER_TOOL_SPEC
        spec = DATA_HANDLER_TOOL_SPEC
        assert spec["name"] == "data_handler"
        assert "parameters" in spec

    def test_spec_has_file_path(self):
        from agent.tools.data_handler import DATA_HANDLER_TOOL_SPEC
        props = DATA_HANDLER_TOOL_SPEC["parameters"]["properties"]
        assert "file_path" in props

    def test_spec_operations(self):
        from agent.tools.data_handler import DATA_HANDLER_TOOL_SPEC
        ops = DATA_HANDLER_TOOL_SPEC["parameters"]["properties"]["operation"]
        assert "inspect" in ops["enum"]
        assert "convert" in ops["enum"]


class TestLoadCSV:
    """Test CSV loading."""

    def test_load_tabular_csv(self, temp_dir):
        csv_path = temp_dir / "test.csv"
        csv_path.write_text("name,cost\nA,10\nB,20\nC,30\n", encoding="utf-8")
        from agent.tools.data_handler import _load_csv
        result = _load_csv(str(csv_path))
        assert result["type"] == "tabular"
        assert result["rows"] == 3
        assert "name" in result["columns"]
        assert "cost" in result["columns"]

    def test_load_matrix_csv(self, temp_dir):
        csv_path = temp_dir / "matrix.csv"
        csv_path.write_text(",0,1,2\n0,0,10,20\n1,10,0,15\n2,20,15,0\n", encoding="utf-8")
        from agent.tools.data_handler import _load_csv
        result = _load_csv(str(csv_path))
        assert result["type"] == "matrix"
        assert result["shape"] == [3, 3]

    def test_empty_csv(self, temp_dir):
        csv_path = temp_dir / "empty.csv"
        csv_path.write_text("", encoding="utf-8")
        from agent.tools.data_handler import _load_csv
        result = _load_csv(str(csv_path))
        assert result["type"] == "empty"


class TestLoadJSON:
    """Test JSON loading."""

    def test_load_json_object(self, temp_dir):
        json_path = temp_dir / "data.json"
        data = {"costs": [10, 20, 30], "names": ["A", "B", "C"]}
        json_path.write_text(json.dumps(data), encoding="utf-8")
        from agent.tools.data_handler import _load_json
        result = _load_json(str(json_path))
        assert result["type"] == "object"
        assert "costs" in result["keys"]

    def test_load_json_list(self, temp_dir):
        json_path = temp_dir / "list.json"
        data = [{"id": 1, "cost": 10}, {"id": 2, "cost": 20}]
        json_path.write_text(json.dumps(data), encoding="utf-8")
        from agent.tools.data_handler import _load_json
        result = _load_json(str(json_path))
        assert result["type"] == "list"
        assert result["length"] == 2


class TestToPyomoData:
    """Test Pyomo code generation."""

    def test_matrix_to_pyomo(self):
        from agent.tools.data_handler import _to_pyomo_data
        parsed = {
            "type": "matrix",
            "labels": ["A", "B", "C"],
            "data": [[0, 10, 20], [10, 0, 15], [20, 15, 0]],
            "shape": [3, 3],
        }
        code = _to_pyomo_data(parsed)
        assert "Set" in code
        assert "Param" in code
        assert "A" in code

    def test_tabular_to_pyomo(self):
        from agent.tools.data_handler import _to_pyomo_data
        parsed = {
            "type": "tabular",
            "columns": ["name", "cost"],
            "data": [{"name": "A", "cost": 10.0}],
            "rows": 1,
        }
        code = _to_pyomo_data(parsed)
        assert "tabular" in code.lower()


class TestDataHandlerHandler:
    """Test the async handler."""

    @pytest.mark.asyncio
    async def test_missing_file_path(self):
        from agent.tools.data_handler import data_handler_handler
        output, is_error = await data_handler_handler({"file_path": ""})
        assert is_error

    @pytest.mark.asyncio
    async def test_nonexistent_file(self):
        from agent.tools.data_handler import data_handler_handler
        output, is_error = await data_handler_handler({
            "file_path": "/nonexistent/data.csv"
        })
        assert is_error

    @pytest.mark.asyncio
    async def test_unsupported_format(self, temp_dir):
        txt_path = temp_dir / "data.txt"
        txt_path.write_text("hello", encoding="utf-8")
        from agent.tools.data_handler import data_handler_handler
        output, is_error = await data_handler_handler({
            "file_path": str(txt_path)
        })
        assert is_error

    @pytest.mark.asyncio
    async def test_csv_inspect(self, temp_dir):
        csv_path = temp_dir / "test.csv"
        csv_path.write_text("name,cost\nA,10\nB,20\n", encoding="utf-8")
        from agent.tools.data_handler import data_handler_handler
        output, is_error = await data_handler_handler({
            "file_path": str(csv_path),
            "operation": "inspect",
        })
        assert not is_error
        assert "Data Inspection" in output

    @pytest.mark.asyncio
    async def test_csv_convert(self, temp_dir):
        csv_path = temp_dir / "test.csv"
        csv_path.write_text(",0,1\n0,0,10\n1,10,0\n", encoding="utf-8")
        from agent.tools.data_handler import data_handler_handler
        output, is_error = await data_handler_handler({
            "file_path": str(csv_path),
            "operation": "convert",
        })
        assert not is_error
        assert "Pyomo" in output
