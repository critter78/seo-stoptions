"""DuckDuckGo web search tool (no API key needed)."""
from __future__ import annotations

from typing import List, Dict
from langchain_core.tools import tool

# `duckduckgo-search` was renamed to `ddgs`. Try the new name first, fall back.
try:  # pragma: no cover
    from ddgs import DDGS  # type: ignore
except ImportError:  # pragma: no cover
    from duckduckgo_search import DDGS  # type: ignore


@tool
def duckduckgo_search(query: str, max_results: int = 10) -> List[Dict[str, str]]:
    """Search the web with DuckDuckGo and return organic results.

    Returns a list of {title, href, body} dicts. Use this when you need to
    find SERPs for a keyword, look up competitors, find reference articles,
    or surface citation sources for E-E-A-T research.

    Args:
        query: The search query string.
        max_results: How many results to return (1-25). Default 10.
    """
    max_results = max(1, min(int(max_results or 10), 25))
    out: List[Dict[str, str]] = []
    try:
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results, safesearch="moderate"):
                out.append({
                    "title": r.get("title", ""),
                    "href": r.get("href", ""),
                    "body": r.get("body", ""),
                })
    except Exception as e:
        return [{"title": "ERROR", "href": "", "body": f"DuckDuckGo search failed: {e}"}]
    return out
