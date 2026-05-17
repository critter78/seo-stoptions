"""AEO Scoreboard — query AI engines for a topic + detect whether stoptions.ai
is cited as a source.

Supported engines (each optional, gracefully degrades):
  - **Claude** (Anthropic) — uses ANTHROPIC_API_KEY (already set)
  - **Perplexity** — uses PERPLEXITY_API_KEY; returns sources natively
  - **ChatGPT** — uses OPENAI_API_KEY
  - **Gemini** — uses GEMINI_API_KEY (Google AI Studio)
  - **Google AI Overviews** — uses SERPAPI_KEY (paid, real Google SERPs with AI box)

Every check is logged to SQLite (aeo_citations table) so we can chart citation
rate over time per engine + query.
"""
from __future__ import annotations

import json as _json
import re
from typing import Dict, List, Optional

import requests
from langchain_core.tools import tool

from app.config import (
    ANTHROPIC_API_KEY,
    ANTHROPIC_MODEL,
    GEMINI_API_KEY,
    OPENAI_API_KEY,
    PERPLEXITY_API_KEY,
    REQUEST_TIMEOUT,
    SERPAPI_KEY,
)
from app.db import log_aeo_citation


def _detect_citations(text: str, domains: List[str], urls: List[str] = None) -> dict:
    """Check if any of our domains appears in text/url list. Returns {cited, count}."""
    urls = urls or []
    found = 0
    matched = []
    haystack = " ".join([text or ""] + urls).lower()
    for d in domains:
        dl = d.lower().lstrip("www.")
        count = haystack.count(dl)
        if count > 0:
            found += count
            matched.append(d)
    return {"cited": found > 0, "count": found, "matched_domains": matched}


# ============================================================================
def _query_claude(prompt: str) -> dict:
    if not ANTHROPIC_API_KEY:
        return {"ok": False, "skipped": "ANTHROPIC_API_KEY missing"}
    try:
        from anthropic import Anthropic
        client = Anthropic(api_key=ANTHROPIC_API_KEY)
        msg = client.messages.create(
            model=ANTHROPIC_MODEL, max_tokens=1500,
            messages=[{"role": "user", "content": prompt}],
        )
        text = ""
        for block in msg.content:
            if hasattr(block, "text"):
                text += block.text
        return {"ok": True, "text": text, "citations": []}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _query_perplexity(prompt: str) -> dict:
    if not PERPLEXITY_API_KEY:
        return {"ok": False, "skipped": "PERPLEXITY_API_KEY missing"}
    try:
        r = requests.post(
            "https://api.perplexity.ai/chat/completions",
            headers={"Authorization": f"Bearer {PERPLEXITY_API_KEY}",
                     "Content-Type": "application/json"},
            json={
                "model": "sonar",
                "messages": [{"role": "user", "content": prompt}],
                "return_citations": True,
            },
            timeout=60,
        )
        data = r.json()
        text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        citations = data.get("citations", [])
        return {"ok": True, "text": text, "citations": citations}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _query_openai(prompt: str) -> dict:
    if not OPENAI_API_KEY:
        return {"ok": False, "skipped": "OPENAI_API_KEY missing"}
    try:
        r = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}",
                     "Content-Type": "application/json"},
            json={
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=60,
        )
        data = r.json()
        text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        return {"ok": True, "text": text, "citations": []}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _query_gemini(prompt: str) -> dict:
    if not GEMINI_API_KEY:
        return {"ok": False, "skipped": "GEMINI_API_KEY missing"}
    try:
        r = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}",
            json={"contents": [{"parts": [{"text": prompt}]}]},
            timeout=60,
        )
        data = r.json()
        text = ""
        for cand in data.get("candidates", []):
            for part in cand.get("content", {}).get("parts", []):
                text += part.get("text", "")
        return {"ok": True, "text": text, "citations": []}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _query_google_ai_overview(query: str) -> dict:
    """Use SerpApi to fetch a Google SERP including the AI Overview box."""
    if not SERPAPI_KEY:
        return {"ok": False, "skipped": "SERPAPI_KEY missing"}
    try:
        r = requests.get(
            "https://serpapi.com/search.json",
            params={"q": query, "engine": "google", "api_key": SERPAPI_KEY,
                    "hl": "en", "gl": "us"},
            timeout=REQUEST_TIMEOUT,
        )
        data = r.json()
        ai_overview = data.get("ai_overview", {})
        text = ai_overview.get("text_blocks_text", "") or _json.dumps(ai_overview)[:2000]
        citations = []
        for ref in ai_overview.get("references", []):
            if ref.get("link"):
                citations.append(ref["link"])
        return {"ok": True, "text": text, "citations": citations,
                "raw": {"has_ai_overview": bool(ai_overview)}}
    except Exception as e:
        return {"ok": False, "error": str(e)}


_ENGINE_FUNCS = {
    "claude": _query_claude,
    "perplexity": _query_perplexity,
    "chatgpt": _query_openai,
    "gemini": _query_gemini,
    "google_ai_overview": _query_google_ai_overview,
}


def _build_prompt_for_query(query: str) -> str:
    return (
        f"I'm researching {query} for retail option traders. Give me a thorough, "
        f"sourced answer with specific platforms, tools, and educational resources "
        f"that are widely respected in this space. Cite specific websites where appropriate."
    )


# ============================================================================
@tool
def check_ai_citations(
    query: str,
    our_domains: List[str] = ["stoptions.ai"],
    engines: List[str] = ["claude", "perplexity", "chatgpt", "gemini", "google_ai_overview"],
) -> Dict[str, object]:
    """Query AI engines for `query` and check whether our domain is cited.

    Args:
        query: the search-style question (e.g. "best AI options trading platforms").
        our_domains: list of domains to check for citation. Defaults to ["stoptions.ai"].
        engines: which engines to query. Available: claude, perplexity, chatgpt, gemini,
                 google_ai_overview. Each is skipped if its API key isn't set.

    Every result is logged to SQLite (aeo_citations table) so the AEO Scoreboard
    page can chart citation rate over time.

    For each engine: returns {ok, cited (bool), count (int), matched_domains, citations}.
    """
    prompt = _build_prompt_for_query(query)
    out = {"ok": True, "query": query, "our_domains": our_domains, "results": {}}

    for engine in engines:
        fn = _ENGINE_FUNCS.get(engine)
        if not fn:
            out["results"][engine] = {"ok": False, "error": f"Unknown engine: {engine}"}
            continue
        # Google AI Overview takes the raw query; others take the prompt
        resp = fn(query if engine == "google_ai_overview" else prompt)
        if not resp.get("ok"):
            out["results"][engine] = resp
            continue
        det = _detect_citations(resp.get("text", ""), our_domains, resp.get("citations", []))
        result = {
            "ok": True,
            "cited": det["cited"],
            "count": det["count"],
            "matched_domains": det["matched_domains"],
            "citations_returned": resp.get("citations", [])[:10],
            "response_preview": (resp.get("text", "") or "")[:400],
        }
        out["results"][engine] = result
        # Log to SQLite for charting
        try:
            log_aeo_citation(
                query=query, engine=engine,
                cited=det["cited"], citation_count=det["count"],
                response_text=resp.get("text", ""),
                citations=resp.get("citations", []),
            )
        except Exception:
            pass

    # Summary
    cited_engines = [e for e, r in out["results"].items() if r.get("cited")]
    out["summary"] = {
        "engines_tested": len(out["results"]),
        "engines_citing_us": len(cited_engines),
        "citation_rate_pct": round(100 * len(cited_engines) / max(len(out["results"]), 1), 1),
        "cited_in": cited_engines,
    }
    return out
