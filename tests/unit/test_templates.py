"""Unit tests for templates tool."""

import pytest


class TestTemplatesSpec:
    """Test tool specification."""

    def test_spec_has_required_fields(self):
        from agent.tools.templates import TEMPLATES_TOOL_SPEC
        spec = TEMPLATES_TOOL_SPEC
        assert spec["name"] == "problem_templates"
        assert "parameters" in spec

    def test_spec_operations(self):
        from agent.tools.templates import TEMPLATES_TOOL_SPEC
        ops = TEMPLATES_TOOL_SPEC["parameters"]["properties"]["operation"]
        assert "list" in ops["enum"]
        assert "match" in ops["enum"]
        assert "generate" in ops["enum"]


class TestMatchTemplate:
    """Test template matching."""

    def test_match_tsp(self):
        from agent.tools.templates import match_template
        result = match_template("solve a traveling salesman problem with 5 cities")
        assert result == "tsp"

    def test_match_knapsack(self):
        from agent.tools.templates import match_template
        result = match_template("maximize profit with knapsack capacity 50")
        assert result == "knapsack"

    def test_match_facility_location(self):
        from agent.tools.templates import match_template
        result = match_template("where should I build warehouses to minimize cost")
        assert result == "facility_location"

    def test_no_match(self):
        from agent.tools.templates import match_template
        result = match_template("quantum computing optimization")
        assert result is None


class TestListTemplates:
    """Test template listing."""

    def test_list_returns_string(self):
        from agent.tools.templates import list_templates
        result = list_templates()
        assert isinstance(result, str)
        assert "tsp" in result
        assert "knapsack" in result

    def test_list_contains_all_templates(self):
        from agent.tools.templates import list_templates, TEMPLATES
        result = list_templates()
        for name in TEMPLATES:
            assert name in result


class TestGenerateFromTemplate:
    """Test code generation from templates."""

    def test_generate_tsp(self):
        from agent.tools.templates import generate_from_template
        code = generate_from_template("tsp", {"n": 5})
        assert "pyomo" in code.lower() or "ConcreteModel" in code

    def test_generate_knapsack(self):
        from agent.tools.templates import generate_from_template
        code = generate_from_template("knapsack", {
            "capacity": 50,
            "items": [{"weight": 10, "value": 60}, {"weight": 20, "value": 100}],
        })
        assert "ConcreteModel" in code

    def test_unknown_template_raises(self):
        from agent.tools.templates import generate_from_template
        with pytest.raises(ValueError, match="Unknown template"):
            generate_from_template("nonexistent", {})


class TestTemplatesHandler:
    """Test the async handler."""

    @pytest.mark.asyncio
    async def test_list_operation(self):
        from agent.tools.templates import templates_handler
        output, is_error = await templates_handler({"operation": "list"})
        assert not is_error
        assert "Template" in output

    @pytest.mark.asyncio
    async def test_match_operation(self):
        from agent.tools.templates import templates_handler
        output, is_error = await templates_handler({
            "operation": "match",
            "description": "solve a TSP with 10 cities",
        })
        assert not is_error
        assert "tsp" in output

    @pytest.mark.asyncio
    async def test_generate_operation(self, temp_dir, monkeypatch):
        from agent.tools import _output_dir
        monkeypatch.setattr(_output_dir, "get_run_dir", lambda: temp_dir)
        from agent.tools.templates import templates_handler
        output, is_error = await templates_handler({
            "operation": "generate",
            "template_name": "knapsack",
            "parameters": {"capacity": 100, "items": [{"weight": 10, "value": 60}]},
        })
        assert not is_error
        assert "Generated" in output or "model" in output.lower()
