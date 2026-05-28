"""or_papers tool for OR-Intern Phase 1 (completion).

Searches OR/optimization literature via arXiv API and web search.
Supports: arXiv search, keyword-based discovery, abstract reading.
"""

import logging
import re
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from typing import Any

logger = logging.getLogger(__name__)

# ── arXiv API ──

_ARXIV_API = "https://export.arxiv.org/api/query"

_OR_KEYWORDS = [
    "optimization", "operations research", "linear programming",
    "mixed integer programming", "stochastic optimization",
    "combinatorial optimization", "network flow", "scheduling",
    "vehicle routing", "supply chain optimization",
    "robust optimization", "nonlinear programming",
    "constraint programming", "dynamic programming",
]


def _build_arxiv_query(query: str, max_results: int = 10) -> str:
    """Build arXiv API query URL."""
    encoded = urllib.parse.quote(query)
    return (
        f"{_ARXIV_API}?search_query=all:{encoded}"
        f"&start=0&max_results={max_results}&sortBy=relevance"
    )


def _fetch_arxiv(query: str, max_results: int = 5) -> list[dict]:
    """Fetch papers from arXiv API."""
    try:
        url = _build_arxiv_query(query, max_results)
        req = urllib.request.Request(url, headers={"User-Agent": "OR-Intern/0.1"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = resp.read().decode("utf-8")

        ns = {
            "atom": "http://www.w3.org/2005/Atom",
            "arxiv": "http://arxiv.org/schemas/atom",
        }
        root = ET.fromstring(data)

        papers = []
        for entry in root.findall("atom:entry", ns):
            title = entry.find("atom:title", ns)
            summary = entry.find("atom:summary", ns)
            link = entry.find("atom:id", ns)
            published = entry.find("atom:published", ns)

            authors = []
            for author in entry.findall("atom:author", ns):
                name = author.find("atom:name", ns)
                if name is not None and name.text:
                    authors.append(name.text)

            papers.append({
                "title": title.text.strip() if title is not None else "Unknown",
                "authors": ", ".join(authors[:3]),
                "summary": (summary.text or "")[:500].strip() if summary is not None else "",
                "url": link.text.strip() if link is not None else "",
                "published": published.text[:10] if published is not None else "Unknown",
            })

        return papers

    except Exception as e:
        logger.warning(f"arXiv fetch failed: {e}")
        return []


def _format_papers(papers: list[dict], query: str) -> str:
    """Format papers into markdown output."""
    if not papers:
        return f"## arXiv Search: '{query}'\n\nNo results found or API unavailable."

    lines = [
        f"## arXiv Search: '{query}'\n",
        f"Found {len(papers)} papers:\n",
    ]
    for i, p in enumerate(papers, 1):
        lines.append(f"### {i}. {p['title']}")
        lines.append(f"- **Authors**: {p['authors']}")
        lines.append(f"- **Published**: {p['published']}")
        lines.append(f"- **URL**: [{p['url']}]({p['url']})")
        if p['summary']:
            lines.append(f"- **Abstract**: {p['summary'][:400]}...")
        lines.append("")
    return "\n".join(lines)


# ── Tool spec and handler ──

OR_PAPERS_TOOL_SPEC = {
    "name": "or_papers",
    "description": (
        "Search OR/optimization research papers via arXiv and web. "
        "Use for finding papers on algorithms, solvers, problem formulations. "
        "Input: search query or keywords. Output: paper titles, authors, abstracts, URLs."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query (e.g. 'vehicle routing problem with time windows')",
            },
            "max_results": {
                "type": "integer",
                "description": "Max papers to return (1-20, default: 5)",
                "default": 5,
            },
            "source": {
                "type": "string",
                "enum": ["arxiv", "web", "both"],
                "description": "Search source",
                "default": "both",
            },
        },
        "required": ["query"],
    },
}


async def or_papers_handler(args: dict[str, Any]) -> tuple[str, bool]:
    """Handler for or_papers tool."""
    query = args.get("query", "")
    max_results = min(args.get("max_results", 5), 20)
    source = args.get("source", "both")

    if not query:
        return "Error: No search query provided", True

    # Add OR keywords if query is short
    if len(query.split()) < 2:
        query += " optimization"

    results_parts = []

    if source in ("arxiv", "both"):
        papers = _fetch_arxiv(query, max_results)
        results_parts.append(_format_papers(papers, query))

    if source in ("web", "both") and (not results_parts or source == "web"):
        results_parts.append(
            f"## Web Search Tip\n\n"
            f"Use `web_search` tool with query: "
            f"'{query} operations research paper site:arxiv.org OR site:scholar.google.com'"
        )

    if not results_parts:
        return f"No results found for '{query}'", False

    return "\n\n".join(results_parts) + "\n\n*Tip: Use `web_search` for broader coverage.*", False
