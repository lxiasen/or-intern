"""or_papers tool for OR-Intern v0.5.

Multi-source OR/optimization literature search and analysis:

- arXiv API: preprint search with abstract, categories, PDF links
- Semantic Scholar API: citation counts, references, citations (free, no key)
- OpenAlex API: comprehensive metadata, citation analysis (free)

Operations:
  search   — multi-source paper search
  detail   — full paper metadata, abstract, citation count, related papers
  cite     — citation analysis for a specific paper
"""

import json
import logging
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from typing import Any

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════
# arXiv API
# ══════════════════════════════════════════════════════════════════════

_ARXIV_API = "https://export.arxiv.org/api/query"

_OR_KEYWORDS = [
    "optimization", "operations research", "linear programming",
    "mixed integer programming", "stochastic optimization",
    "combinatorial optimization", "network flow", "scheduling",
    "vehicle routing", "supply chain optimization",
    "robust optimization", "nonlinear programming",
    "constraint programming", "dynamic programming",
    "integer programming", "convex optimization", "portfolio optimization",
]


def _arxiv_id_from_url(url: str) -> str:
    """Extract the bare arXiv ID from a URL or ID string."""
    m = re.search(r"(\d{4}\.\d{4,5})", url)
    return m.group(1) if m else url


def _fetch_arxiv(query: str, max_results: int = 5) -> list[dict]:
    """Fetch papers from arXiv API with full metadata."""
    try:
        encoded = urllib.parse.quote(query)
        url = (
            f"{_ARXIV_API}?search_query=all:{encoded}"
            f"&start=0&max_results={max_results}&sortBy=relevance"
        )
        req = urllib.request.Request(url, headers={"User-Agent": "OR-Intern/0.5"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = resp.read().decode("utf-8")

        ns = {
            "atom": "http://www.w3.org/2005/Atom",
            "arxiv": "http://arxiv.org/schemas/atom",
        }
        root = ET.fromstring(data)

        papers = []
        for entry in root.findall("atom:entry", ns):
            title_el = entry.find("atom:title", ns)
            summary_el = entry.find("atom:summary", ns)
            link_el = entry.find("atom:id", ns)
            published_el = entry.find("atom:published", ns)
            updated_el = entry.find("atom:updated", ns)

            authors = []
            for author in entry.findall("atom:author", ns):
                name = author.find("atom:name", ns)
                if name is not None and name.text:
                    authors.append(name.text.strip())

            categories = []
            for cat in entry.findall("atom:category", ns):
                term = cat.get("term")
                if term:
                    categories.append(term)

            doi_el = entry.find("arxiv:doi", ns)
            comment_el = entry.find("arxiv:comment", ns)
            journal_el = entry.find("arxiv:journal_ref", ns)

            arxiv_id = _arxiv_id_from_url(
                link_el.text.strip() if link_el is not None else ""
            )

            pdf_link = f"https://arxiv.org/pdf/{arxiv_id}"

            papers.append({
                "title": (title_el.text or "Unknown").strip().replace("\n", " ")
                         if title_el is not None else "Unknown",
                "authors": authors,
                "authors_str": ", ".join(authors[:5])
                               + ("..." if len(authors) > 5 else ""),
                "summary": (summary_el.text or "").strip().replace("\n", " ")
                           if summary_el is not None else "",
                "url": f"https://arxiv.org/abs/{arxiv_id}",
                "pdf_url": pdf_link,
                "arxiv_id": arxiv_id,
                "published": (published_el.text or "")[:10]
                             if published_el is not None else "",
                "updated": (updated_el.text or "")[:10]
                           if updated_el is not None else "",
                "categories": categories,
                "doi": (doi_el.text or "").strip() if doi_el is not None else "",
                "comment": (comment_el.text or "").strip().replace("\n", " ")
                           if comment_el is not None else "",
                "journal_ref": (journal_el.text or "").strip()
                               if journal_el is not None else "",
                "source": "arxiv",
            })

        return papers

    except Exception as e:
        logger.warning("arXiv fetch failed: %s", e)
        return []


# ══════════════════════════════════════════════════════════════════════
# Semantic Scholar API (free, no key)
# ══════════════════════════════════════════════════════════════════════

_S2_SEARCH = "https://api.semanticscholar.org/graph/v1/paper/search"
_S2_PAPER = "https://api.semanticscholar.org/graph/v1/paper"
_S2_FIELDS = "title,authors,year,abstract,citationCount,referenceCount,url,externalIds,venue,publicationDate,fieldsOfStudy"


def _fetch_semantic_scholar(query: str, max_results: int = 5) -> list[dict]:
    """Search Semantic Scholar for papers."""
    try:
        params = urllib.parse.urlencode({
            "query": query,
            "limit": min(max_results, 10),
            "fields": _S2_FIELDS,
        })
        url = f"{_S2_SEARCH}?{params}"
        req = urllib.request.Request(
            url, headers={
                "User-Agent": "OR-Intern/0.5",
                "Accept": "application/json",
            }
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        papers = []
        for item in data.get("data", [])[:max_results]:
            ext_ids = item.get("externalIds") or {}
            arxiv_id = ext_ids.get("ArXiv", "")
            doi = ext_ids.get("DOI", "")

            authors = [
                a.get("name", "") for a in (item.get("authors") or [])
            ]

            papers.append({
                "title": item.get("title", "Unknown"),
                "authors": authors,
                "authors_str": ", ".join(authors[:5])
                               + ("..." if len(authors) > 5 else ""),
                "summary": (item.get("abstract") or "")[:600],
                "url": item.get("url", ""),
                "arxiv_id": arxiv_id,
                "pdf_url": f"https://arxiv.org/pdf/{arxiv_id}" if arxiv_id else "",
                "doi": doi,
                "published": item.get("publicationDate", "") or "",
                "year": item.get("year"),
                "citation_count": item.get("citationCount", 0),
                "reference_count": item.get("referenceCount", 0),
                "venue": item.get("venue", ""),
                "fields_of_study": item.get("fieldsOfStudy") or [],
                "s2_paper_id": item.get("paperId", ""),
                "source": "semantic_scholar",
            })

        return papers

    except Exception as e:
        logger.warning("Semantic Scholar fetch failed: %s", e)
        return []


def _fetch_s2_citations(paper_id: str, max_results: int = 10) -> list[dict]:
    """Fetch papers that cite a given Semantic Scholar paper ID."""
    try:
        url = (
            f"{_S2_PAPER}/{paper_id}/citations"
            f"?fields=title,authors,year,citationCount&limit={min(max_results, 20)}"
        )
        req = urllib.request.Request(
            url, headers={"User-Agent": "OR-Intern/0.5", "Accept": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        results = []
        for item in data.get("data", [])[:max_results]:
            citing = item.get("citingPaper", {})
            if not citing:
                continue
            authors = [a.get("name", "") for a in (citing.get("authors") or [])]
            results.append({
                "title": citing.get("title", "Unknown"),
                "authors_str": ", ".join(authors[:3]),
                "year": citing.get("year"),
                "citation_count": citing.get("citationCount", 0),
            })

        return results

    except Exception as e:
        logger.warning("S2 citations fetch failed: %s", e)
        return []


def _fetch_s2_references(paper_id: str, max_results: int = 10) -> list[dict]:
    """Fetch papers referenced by a given Semantic Scholar paper ID."""
    try:
        url = (
            f"{_S2_PAPER}/{paper_id}/references"
            f"?fields=title,authors,year,citationCount&limit={min(max_results, 20)}"
        )
        req = urllib.request.Request(
            url, headers={"User-Agent": "OR-Intern/0.5", "Accept": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        results = []
        for item in data.get("data", [])[:max_results]:
            cited = item.get("citedPaper", {})
            if not cited:
                continue
            authors = [a.get("name", "") for a in (cited.get("authors") or [])]
            results.append({
                "title": cited.get("title", "Unknown"),
                "authors_str": ", ".join(authors[:3]),
                "year": cited.get("year"),
                "citation_count": cited.get("citationCount", 0),
            })

        return results

    except Exception as e:
        logger.warning("S2 references fetch failed: %s", e)
        return []


# ══════════════════════════════════════════════════════════════════════
# OpenAlex API (free, comprehensive)
# ══════════════════════════════════════════════════════════════════════

_OPENALEX_SEARCH = "https://api.openalex.org/works"


def _fetch_openalex(query: str, max_results: int = 5) -> list[dict]:
    """Search OpenAlex for papers with citation and venue data."""
    try:
        params = urllib.parse.urlencode({
            "search": query,
            "per_page": min(max_results, 10),
            "mailto": "or-intern@example.org",
        })
        url = f"{_OPENALEX_SEARCH}?{params}"
        req = urllib.request.Request(
            url, headers={"User-Agent": "OR-Intern/0.5", "Accept": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        papers = []
        for item in data.get("results", [])[:max_results]:
            authors = [
                a.get("author", {}).get("display_name", "")
                for a in (item.get("authorships") or [])
            ]

            doi = item.get("doi", "")
            oa_url = item.get("primary_location", {}) or {}
            landing = oa_url.get("landing_page_url", "")

            oa_entry = {
                "title": item.get("title", "Unknown"),
                "authors": authors,
                "authors_str": ", ".join(authors[:5])
                               + ("..." if len(authors) > 5 else ""),
                "summary": "",
                "url": landing or doi or "",
                "doi": doi.replace("https://doi.org/", "") if doi else "",
                "published": item.get("publication_date", ""),
                "year": item.get("publication_year"),
                "citation_count": item.get("cited_by_count", 0),
                "venue": (item.get("primary_location") or {}).get("source", {})
                         .get("display_name", "") if item.get("primary_location") else "",
                "type": item.get("type", ""),
                "is_oa": item.get("open_access", {}).get("is_oa", False),
                "oa_url": item.get("open_access", {}).get("oa_url", ""),
                "source": "openalex",
            }

            abstract_inv = item.get("abstract_inverted_index")
            if abstract_inv:
                oa_entry["summary"] = _reconstruct_abstract(abstract_inv)

            papers.append(oa_entry)

        return papers

    except Exception as e:
        logger.warning("OpenAlex fetch failed: %s", e)
        return []


def _reconstruct_abstract(inverted_index: dict) -> str:
    """Reconstruct abstract text from OpenAlex inverted index format."""
    word_positions: list[tuple[int, str]] = []
    for word, positions in inverted_index.items():
        for pos in positions:
            word_positions.append((pos, word))
    word_positions.sort()
    return " ".join(w for _, w in word_positions)[:600]


# ══════════════════════════════════════════════════════════════════════
# Deduplication
# ══════════════════════════════════════════════════════════════════════

def _normalize_title(title: str) -> str:
    """Normalize a paper title for deduplication."""
    return re.sub(r"[^a-z0-9]", "", title.lower())


def _deduplicate(papers: list[dict]) -> list[dict]:
    """Remove duplicate papers across sources, preferring richer metadata."""
    seen: dict[str, dict] = {}
    for p in papers:
        key = _normalize_title(p.get("title", ""))
        if not key:
            continue
        existing = seen.get(key)
        if existing is None:
            seen[key] = p
        else:
            if p.get("citation_count") and not existing.get("citation_count"):
                existing["citation_count"] = p["citation_count"]
            if p.get("venue") and not existing.get("venue"):
                existing["venue"] = p["venue"]
            if p.get("doi") and not existing.get("doi"):
                existing["doi"] = p["doi"]
            if p.get("summary") and len(p["summary"]) > len(existing.get("summary", "")):
                existing["summary"] = p["summary"]
    return list(seen.values())


# ══════════════════════════════════════════════════════════════════════
# Formatting
# ══════════════════════════════════════════════════════════════════════

def _format_search_results(papers: list[dict], query: str, source: str) -> str:
    """Format search results as markdown."""
    if not papers:
        return f"## Paper Search: '{query}'\n\nNo results found from {source}."

    lines = [
        f"## Paper Search: '{query}' ({source})\n",
        f"Found {len(papers)} papers:\n",
    ]
    for i, p in enumerate(papers, 1):
        lines.append(f"### {i}. {p['title']}")
        lines.append(f"- **Authors**: {p.get('authors_str', 'Unknown')}")
        if p.get("published"):
            lines.append(f"- **Published**: {p['published'][:10]}")
        if p.get("year"):
            lines.append(f"- **Year**: {p['year']}")
        if p.get("citation_count") is not None:
            lines.append(f"- **Citations**: {p['citation_count']}")
        if p.get("venue"):
            lines.append(f"- **Venue**: {p['venue']}")
        if p.get("url"):
            lines.append(f"- **URL**: [{p['url']}]({p['url']})")
        if p.get("pdf_url"):
            lines.append(f"- **PDF**: [{p['pdf_url']}]({p['pdf_url']})")
        if p.get("doi"):
            lines.append(f"- **DOI**: {p['doi']}")
        if p.get("categories"):
            lines.append(f"- **Categories**: {', '.join(p['categories'][:5])}")
        if p.get("summary"):
            abstract = p["summary"][:400]
            lines.append(f"- **Abstract**: {abstract}...")
        lines.append("")
    return "\n".join(lines)


def _format_detail(paper: dict) -> str:
    """Format detailed paper metadata."""
    lines = [
        f"## {paper.get('title', 'Unknown')}\n",
        f"**Authors**: {paper.get('authors_str', 'Unknown')}",
    ]
    if paper.get("published"):
        lines.append(f"**Published**: {paper['published'][:10]}")
    if paper.get("year"):
        lines.append(f"**Year**: {paper['year']}")
    if paper.get("citation_count") is not None:
        lines.append(f"**Citations**: {paper['citation_count']}")
    if paper.get("reference_count") is not None:
        lines.append(f"**References**: {paper['reference_count']}")
    if paper.get("venue"):
        lines.append(f"**Venue**: {paper['venue']}")
    if paper.get("type"):
        lines.append(f"**Type**: {paper['type']}")
    if paper.get("doi"):
        lines.append(f"**DOI**: {paper['doi']}")
    if paper.get("url"):
        lines.append(f"**URL**: [{paper['url']}]({paper['url']})")
    if paper.get("pdf_url"):
        lines.append(f"**PDF**: [{paper['pdf_url']}]({paper['pdf_url']})")
    if paper.get("categories"):
        lines.append(f"**Categories**: {', '.join(paper['categories'][:8])}")
    if paper.get("journal_ref"):
        lines.append(f"**Journal**: {paper['journal_ref']}")
    if paper.get("comment"):
        lines.append(f"**Comment**: {paper['comment']}")
    if paper.get("fields_of_study"):
        lines.append(f"**Fields**: {', '.join(paper['fields_of_study'][:5])}")
    if paper.get("summary"):
        lines.append(f"\n### Abstract\n\n{paper['summary']}")
    return "\n".join(lines)


def _format_citation_list(items: list[dict], label: str) -> str:
    """Format a list of citing or referenced papers."""
    if not items:
        return f"No {label} found."
    lines = [f"### {label} ({len(items)} papers)\n"]
    for i, p in enumerate(items, 1):
        cite_info = f" [cited {p['citation_count']}x]" if p.get("citation_count") else ""
        year_info = f" ({p['year']})" if p.get("year") else ""
        lines.append(f"{i}. **{p['title']}**{year_info}{cite_info}")
        lines.append(f"   - {p.get('authors_str', 'Unknown')}")
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════
# Tool Spec
# ══════════════════════════════════════════════════════════════════════

OR_PAPERS_TOOL_SPEC = {
    "name": "or_papers",
    "description": (
        "Search OR/optimization research papers via arXiv, Semantic Scholar, "
        "and OpenAlex. Supports multi-source search, detailed paper metadata, "
        "citation analysis, and cross-source deduplication.\n"
        "Operations:\n"
        "  search — find papers (default)\n"
        "  detail — full metadata for a paper (by arXiv ID, DOI, or S2 ID)\n"
        "  cite   — citation analysis (papers citing / referenced by a paper)"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query (e.g. 'vehicle routing problem with time windows')",
            },
            "operation": {
                "type": "string",
                "enum": ["search", "detail", "cite"],
                "description": "search: find papers; detail: full metadata; cite: citation analysis",
                "default": "search",
            },
            "paper_id": {
                "type": "string",
                "description": "Paper ID for detail/cite (arXiv ID like '2301.12345', DOI, or S2 paper ID)",
            },
            "max_results": {
                "type": "integer",
                "description": "Max papers to return for search (1-20, default: 5)",
                "default": 5,
            },
            "source": {
                "type": "string",
                "enum": ["arxiv", "semantic_scholar", "openalex", "all"],
                "description": "Search source (default: all)",
                "default": "all",
            },
        },
    },
}


# ══════════════════════════════════════════════════════════════════════
# Handler
# ══════════════════════════════════════════════════════════════════════

async def or_papers_handler(args: dict[str, Any]) -> tuple[str, bool]:
    """Handler for or_papers tool with multi-source search and analysis."""
    operation = args.get("operation", "search")

    if operation == "detail":
        return await _handle_detail(args)
    elif operation == "cite":
        return await _handle_cite(args)
    else:
        return await _handle_search(args)


async def _handle_search(args: dict[str, Any]) -> tuple[str, bool]:
    """Multi-source paper search."""
    query = args.get("query", "")
    max_results = min(args.get("max_results", 5), 20)
    source = args.get("source", "all")

    if not query:
        return "Error: No search query provided", True

    if len(query.split()) < 2:
        query += " optimization"

    all_papers: list[dict] = []

    if source in ("arxiv", "all"):
        all_papers.extend(_fetch_arxiv(query, max_results))

    if source in ("semantic_scholar", "all"):
        all_papers.extend(_fetch_semantic_scholar(query, max_results))

    if source in ("openalex", "all"):
        all_papers.extend(_fetch_openalex(query, max_results))

    if source == "all":
        papers = _deduplicate(all_papers)[:max_results]
        papers.sort(
            key=lambda p: p.get("citation_count") or 0,
            reverse=True,
        )
    else:
        papers = all_papers[:max_results]

    if not papers:
        return (
            f"No results found for '{query}' across requested sources.\n\n"
            f"*Tip: Try broader terms or check spelling.*"
        ), False

    source_label = source if source != "all" else "arXiv + Semantic Scholar + OpenAlex"
    return _format_search_results(papers, query, source_label), False


async def _handle_detail(args: dict[str, Any]) -> tuple[str, bool]:
    """Fetch detailed metadata for a specific paper."""
    paper_id = args.get("paper_id", "")

    if not paper_id:
        return "Error: paper_id is required for 'detail' operation", True

    paper = None

    if re.match(r"\d{4}\.\d{4,5}", paper_id):
        papers = _fetch_arxiv(paper_id, 1)
        if papers:
            paper = papers[0]
            s2_papers = _fetch_semantic_scholar(paper["title"], 1)
            if s2_papers:
                s2 = s2_papers[0]
                paper["citation_count"] = s2.get("citation_count")
                paper["reference_count"] = s2.get("reference_count")
                paper["venue"] = s2.get("venue", "")
                paper["s2_paper_id"] = s2.get("s2_paper_id", "")
                if s2.get("summary") and len(s2["summary"]) > len(paper.get("summary", "")):
                    paper["summary"] = s2["summary"]

    elif paper_id.startswith("10."):
        try:
            url = f"{_S2_PAPER}/DOI:{paper_id}?fields={_S2_FIELDS}"
            req = urllib.request.Request(
                url, headers={"User-Agent": "OR-Intern/0.5", "Accept": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            authors = [a.get("name", "") for a in (data.get("authors") or [])]
            ext_ids = data.get("externalIds") or {}
            arxiv_id = ext_ids.get("ArXiv", "")

            paper = {
                "title": data.get("title", "Unknown"),
                "authors": authors,
                "authors_str": ", ".join(authors[:5])
                               + ("..." if len(authors) > 5 else ""),
                "summary": (data.get("abstract") or "")[:600],
                "url": data.get("url", ""),
                "doi": paper_id,
                "arxiv_id": arxiv_id,
                "pdf_url": f"https://arxiv.org/pdf/{arxiv_id}" if arxiv_id else "",
                "published": data.get("publicationDate", ""),
                "year": data.get("year"),
                "citation_count": data.get("citationCount", 0),
                "reference_count": data.get("referenceCount", 0),
                "venue": data.get("venue", ""),
                "fields_of_study": data.get("fieldsOfStudy") or [],
                "s2_paper_id": data.get("paperId", ""),
                "source": "semantic_scholar",
            }
        except Exception as e:
            logger.warning("DOI lookup failed: %s", e)

    else:
        try:
            url = f"{_S2_PAPER}/{paper_id}?fields={_S2_FIELDS}"
            req = urllib.request.Request(
                url, headers={"User-Agent": "OR-Intern/0.5", "Accept": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            authors = [a.get("name", "") for a in (data.get("authors") or [])]
            ext_ids = data.get("externalIds") or {}
            arxiv_id = ext_ids.get("ArXiv", "")
            doi = ext_ids.get("DOI", "")

            paper = {
                "title": data.get("title", "Unknown"),
                "authors": authors,
                "authors_str": ", ".join(authors[:5])
                               + ("..." if len(authors) > 5 else ""),
                "summary": (data.get("abstract") or "")[:600],
                "url": data.get("url", ""),
                "doi": doi,
                "arxiv_id": arxiv_id,
                "pdf_url": f"https://arxiv.org/pdf/{arxiv_id}" if arxiv_id else "",
                "published": data.get("publicationDate", ""),
                "year": data.get("year"),
                "citation_count": data.get("citationCount", 0),
                "reference_count": data.get("referenceCount", 0),
                "venue": data.get("venue", ""),
                "fields_of_study": data.get("fieldsOfStudy") or [],
                "s2_paper_id": data.get("paperId", ""),
                "source": "semantic_scholar",
            }
        except Exception as e:
            logger.warning("S2 paper ID lookup failed: %s", e)

    if not paper:
        return f"Paper not found for ID: {paper_id}", True

    return _format_detail(paper), False


async def _handle_cite(args: dict[str, Any]) -> tuple[str, bool]:
    """Citation analysis: who cites this paper and what it references."""
    paper_id = args.get("paper_id", "")

    if not paper_id:
        return "Error: paper_id is required for 'cite' operation", True

    s2_id = paper_id

    if re.match(r"\d{4}\.\d{4,5}", paper_id):
        try:
            url = f"{_S2_PAPER}/ArXiv:{paper_id}?fields=paperId,citationCount,referenceCount,title"
            req = urllib.request.Request(
                url, headers={"User-Agent": "OR-Intern/0.5", "Accept": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            s2_id = data.get("paperId", paper_id)
            title = data.get("title", paper_id)
            citation_count = data.get("citationCount", 0)
            reference_count = data.get("referenceCount", 0)
        except Exception:
            title = paper_id
            citation_count = 0
            reference_count = 0

    elif paper_id.startswith("10."):
        try:
            url = f"{_S2_PAPER}/DOI:{paper_id}?fields=paperId,citationCount,referenceCount,title"
            req = urllib.request.Request(
                url, headers={"User-Agent": "OR-Intern/0.5", "Accept": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            s2_id = data.get("paperId", paper_id)
            title = data.get("title", paper_id)
            citation_count = data.get("citationCount", 0)
            reference_count = data.get("referenceCount", 0)
        except Exception:
            title = paper_id
            citation_count = 0
            reference_count = 0

    else:
        title = paper_id
        citation_count = 0
        reference_count = 0

    citing = _fetch_s2_citations(s2_id, max_results=15)
    references = _fetch_s2_references(s2_id, max_results=15)

    lines = [
        f"## Citation Analysis: {title}\n",
        f"**Total citations**: {citation_count}",
        f"**Total references**: {reference_count}\n",
    ]

    if citing:
        lines.append(_format_citation_list(
            sorted(citing, key=lambda p: p.get("citation_count", 0), reverse=True),
            "Most-Cited Citing Papers",
        ))
    else:
        lines.append("### Citing Papers\n\nNo citing papers found.")

    lines.append("")

    if references:
        lines.append(_format_citation_list(
            sorted(references, key=lambda p: p.get("citation_count", 0), reverse=True),
            "Key References",
        ))
    else:
        lines.append("### References\n\nNo references found.")

    return "\n".join(lines), False
