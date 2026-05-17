"""Analyse the top organic results for a keyword and extract SEO signals."""
from __future__ import annotations

from typing import Dict, List
from urllib.parse import urlparse
from langchain_core.tools import tool

from .web_search import duckduckgo_search
from .onpage_audit import onpage_audit


@tool
def analyze_serp_for_keyword(keyword: str, top_n: int = 5) -> Dict[str, object]:
    """Search a keyword and run an on-page audit on the top N organic results.

    Returns per-result: title, URL, word count, H1, schema-friendly meta, and
    a quick set of differentiators. Use this when planning content briefs or
    competitive gap analysis.
    """
    results = duckduckgo_search.invoke({"query": keyword, "max_results": max(top_n, 5)})
    audited: List[Dict] = []
    domains = []
    for r in results[:top_n]:
        url = r.get("href")
        if not url:
            continue
        domains.append(urlparse(url).netloc)
        try:
            a = onpage_audit.invoke({"url": url})
        except Exception as e:
            a = {"ok": False, "url": url, "error": str(e)}
        audited.append({
            "rank": len(audited) + 1,
            "url": url,
            "snippet": r.get("body"),
            "title": a.get("title"),
            "title_length": a.get("title_length"),
            "meta_description_length": a.get("meta_description_length"),
            "h1": (a.get("headings") or {}).get("h1", [None])[:1],
            "h2_count": len((a.get("headings") or {}).get("h2", [])),
            "word_count": a.get("word_count"),
            "issues": a.get("issues", []),
        })

    avg_words = round(sum((x.get("word_count") or 0) for x in audited) / max(len(audited), 1))
    return {
        "ok": True,
        "keyword": keyword,
        "results": audited,
        "competitor_domains": sorted(set(domains)),
        "avg_word_count_top": avg_words,
        "recommendation": (
            f"Aim for at least {max(avg_words, 800)} words and address the H1/H2 themes "
            "that recur across the top results. Cover each competitor's H2s plus 1-2 differentiators."
        ),
    }
