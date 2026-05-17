"""Estimate where a domain ranks for a keyword (DuckDuckGo organic position)."""
from __future__ import annotations

from typing import Dict
from urllib.parse import urlparse
from langchain_core.tools import tool

from .web_search import duckduckgo_search
from app.db import log_rank


@tool
def estimate_keyword_rank(keyword: str, domain: str, depth: int = 30) -> Dict[str, object]:
    """Estimate the rank of `domain` for `keyword` on DuckDuckGo.

    Returns the position (1-based) and the matching URL if found within `depth`
    organic results. DuckDuckGo SERPs are not Google-identical, but this is a
    free directional signal that works well for tracking week-over-week changes.
    """
    domain = (domain or "").lower().lstrip("www.")
    results = duckduckgo_search.invoke({"query": keyword, "max_results": int(depth)})
    for i, r in enumerate(results, start=1):
        href = r.get("href") or ""
        if domain and domain in urlparse(href).netloc.lower():
            try:
                log_rank(keyword, domain, i, href, "duckduckgo")
            except Exception:
                pass
            return {
                "ok": True,
                "keyword": keyword,
                "domain": domain,
                "position": i,
                "matched_url": href,
                "title": r.get("title"),
                "engine": "duckduckgo",
                "depth_searched": depth,
            }
    try:
        log_rank(keyword, domain, None, "", "duckduckgo")
    except Exception:
        pass
    return {
        "ok": True,
        "keyword": keyword,
        "domain": domain,
        "position": None,
        "engine": "duckduckgo",
        "depth_searched": depth,
        "note": f"Not found in top {depth} DuckDuckGo results.",
    }
