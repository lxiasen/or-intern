"""Unit tests for or_papers tool (multi-source search + citation analysis)."""

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

    def test_spec_has_operation(self):
        from agent.tools.or_papers import OR_PAPERS_TOOL_SPEC
        props = OR_PAPERS_TOOL_SPEC["parameters"]["properties"]
        assert "operation" in props
        assert set(props["operation"]["enum"]) == {"search", "detail", "cite"}

    def test_spec_has_paper_id(self):
        from agent.tools.or_papers import OR_PAPERS_TOOL_SPEC
        props = OR_PAPERS_TOOL_SPEC["parameters"]["properties"]
        assert "paper_id" in props

    def test_spec_has_source(self):
        from agent.tools.or_papers import OR_PAPERS_TOOL_SPEC
        props = OR_PAPERS_TOOL_SPEC["parameters"]["properties"]
        assert "source" in props
        assert "all" in props["source"]["enum"]
        assert "semantic_scholar" in props["source"]["enum"]
        assert "openalex" in props["source"]["enum"]


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

    @pytest.mark.asyncio
    async def test_search_arxiv_only(self):
        from agent.tools.or_papers import or_papers_handler
        output, is_error = await or_papers_handler({
            "query": "integer programming",
            "max_results": 2,
            "source": "arxiv",
        })
        assert not is_error

    @pytest.mark.asyncio
    async def test_search_semantic_scholar_only(self):
        from agent.tools.or_papers import or_papers_handler
        output, is_error = await or_papers_handler({
            "query": "vehicle routing problem",
            "max_results": 2,
            "source": "semantic_scholar",
        })
        assert not is_error

    @pytest.mark.asyncio
    async def test_search_openalex_only(self):
        from agent.tools.or_papers import or_papers_handler
        output, is_error = await or_papers_handler({
            "query": "supply chain optimization",
            "max_results": 2,
            "source": "openalex",
        })
        assert not is_error

    @pytest.mark.asyncio
    async def test_detail_requires_paper_id(self):
        from agent.tools.or_papers import or_papers_handler
        output, is_error = await or_papers_handler({
            "operation": "detail",
        })
        assert is_error

    @pytest.mark.asyncio
    async def test_cite_requires_paper_id(self):
        from agent.tools.or_papers import or_papers_handler
        output, is_error = await or_papers_handler({
            "operation": "cite",
        })
        assert is_error


class TestDeduplication:

    def test_normalize_title(self):
        from agent.tools.or_papers import _normalize_title
        assert _normalize_title("Hello, World!") == "helloworld"
        assert _normalize_title("A B C") == "abc"

    def test_deduplicate_merges(self):
        from agent.tools.or_papers import _deduplicate
        papers = [
            {"title": "Test Paper", "citation_count": 5, "source": "arxiv"},
            {"title": "Test Paper", "citation_count": None, "venue": "INFORMS", "source": "openalex"},
        ]
        result = _deduplicate(papers)
        assert len(result) == 1
        assert result[0]["citation_count"] == 5
        assert result[0]["venue"] == "INFORMS"

    def test_deduplicate_keeps_distinct(self):
        from agent.tools.or_papers import _deduplicate
        papers = [
            {"title": "Paper A", "source": "arxiv"},
            {"title": "Paper B", "source": "arxiv"},
        ]
        result = _deduplicate(papers)
        assert len(result) == 2


class TestFormatting:

    def test_format_search_empty(self):
        from agent.tools.or_papers import _format_search_results
        result = _format_search_results([], "test", "arxiv")
        assert "No results" in result

    def test_format_search_with_papers(self):
        from agent.tools.or_papers import _format_search_results
        papers = [{
            "title": "Test Paper",
            "authors_str": "Author A",
            "published": "2024-01-01",
            "citation_count": 10,
            "url": "https://example.com",
            "summary": "This is a test abstract.",
        }]
        result = _format_search_results(papers, "test", "arxiv")
        assert "Test Paper" in result
        assert "10" in result

    def test_format_detail(self):
        from agent.tools.or_papers import _format_detail
        paper = {
            "title": "Detail Paper",
            "authors_str": "Author B",
            "citation_count": 50,
            "reference_count": 30,
            "venue": "Operations Research",
            "summary": "Full abstract here.",
        }
        result = _format_detail(paper)
        assert "Detail Paper" in result
        assert "50" in result
        assert "Operations Research" in result

    def test_format_citation_list_empty(self):
        from agent.tools.or_papers import _format_citation_list
        result = _format_citation_list([], "Citing")
        assert "No Citing" in result

    def test_format_citation_list_with_items(self):
        from agent.tools.or_papers import _format_citation_list
        items = [
            {"title": "Citing Paper", "authors_str": "Author", "year": 2023, "citation_count": 5},
        ]
        result = _format_citation_list(items, "Citing")
        assert "Citing Paper" in result
        assert "2023" in result


class TestArxivHelpers:

    def test_arxiv_id_from_url(self):
        from agent.tools.or_papers import _arxiv_id_from_url
        assert _arxiv_id_from_url("https://arxiv.org/abs/2301.12345") == "2301.12345"
        assert _arxiv_id_from_url("2301.12345") == "2301.12345"
        assert _arxiv_id_from_url("no-match") == "no-match"


class TestOpenAlexHelpers:

    def test_reconstruct_abstract(self):
        from agent.tools.or_papers import _reconstruct_abstract
        inverted = {"Hello": [0], "world": [1]}
        result = _reconstruct_abstract(inverted)
        assert result == "Hello world"

    def test_reconstruct_abstract_ordering(self):
        from agent.tools.or_papers import _reconstruct_abstract
        inverted = {"second": [1], "first": [0], "third": [2]}
        result = _reconstruct_abstract(inverted)
        assert result == "first second third"
