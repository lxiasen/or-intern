"""Unit tests for or_papers tool."""

import pytest


class TestOrPapersSpec:
    """Test tool specification."""

    def test_spec_has_required_fields(self):
        from agent.tools.or_papers import OR_PAPERS_TOOL_SPEC
        spec = OR_PAPERS_TOOL_SPEC
        assert spec["name"] == "or_papers"
        assert "parameters" in spec

    def test_spec_has_query(self):
        from agent.tools.or_papers import OR_PAPERS_TOOL_SPEC
        props = OR_PAPERS_TOOL_SPEC["parameters"]["properties"]
        assert "query" in props


class TestOrPapersHandler:
    """Test the async handler."""

    @pytest.mark.asyncio
    async def test_empty_query(self):
        from agent.tools.or_papers import or_papers_handler
        output, is_error = await or_papers_handler({"query": ""})
        assert is_error

    @pytest.mark.asyncio
    async def test_search_returns_results(self):
        from agent.tools.or_papers import or_papers_handler
        output, is_error = await or_papers_handler({
            "query": "traveling salesman problem",
            "max_results": 3,
        })
        assert not is_error
        assert len(output) > 0

    @pytest.mark.asyncio
    async def test_search_with_max_results(self):
        from agent.tools.or_papers import or_papers_handler
        output, is_error = await or_papers_handler({
            "query": "linear programming",
            "max_results": 2,
        })
        assert not is_error
