"""Web fetching + BeautifulSoup parsing tools."""
from __future__ import annotations

from typing import Dict, List
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from langchain_core.tools import tool
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import USER_AGENT, REQUEST_TIMEOUT


@retry(stop=stop_after_attempt(2), wait=wait_exponential(min=1, max=4))
def _http_get(url: str) -> requests.Response:
    return requests.get(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"},
        timeout=REQUEST_TIMEOUT,
        allow_redirects=True,
    )


@tool
def fetch_url(url: str) -> Dict[str, object]:
    """Fetch a URL and return status, final URL, headers and raw HTML (truncated to 200k chars).

    Use this whenever you need the raw HTML of a page so you can analyse it
    further with the on-page or schema tools.
    """
    try:
        r = _http_get(url)
    except Exception as e:
        return {"ok": False, "error": str(e), "url": url}
    return {
        "ok": r.ok,
        "status_code": r.status_code,
        "final_url": r.url,
        "content_type": r.headers.get("Content-Type", ""),
        "server": r.headers.get("Server", ""),
        "html": r.text[:200_000],
        "html_truncated": len(r.text) > 200_000,
        "length": len(r.text),
    }


@tool
def extract_visible_text(url: str, max_chars: int = 12000) -> Dict[str, object]:
    """Fetch a URL and return the visible body text (scripts/styles/nav stripped).

    Useful for content audits, EEAT analysis, semantic relevance scoring,
    and feeding the LLM the article body without HTML noise.
    """
    try:
        r = _http_get(url)
        soup = BeautifulSoup(r.text, "lxml")
        for tag in soup(["script", "style", "noscript", "header", "footer", "nav", "aside"]):
            tag.decompose()
        text = " ".join(soup.get_text(separator=" ", strip=True).split())
        return {
            "ok": True,
            "url": r.url,
            "word_count": len(text.split()),
            "text": text[: int(max_chars)],
            "truncated": len(text) > int(max_chars),
        }
    except Exception as e:
        return {"ok": False, "url": url, "error": str(e)}


@tool
def extract_all_links(url: str) -> Dict[str, object]:
    """Fetch a URL and return all internal and external links (deduped).

    Returns: {internal: [...], external: [...], counts: {...}, anchor_texts: {...}}.
    Useful for internal-linking audits and discovering inbound/outbound link
    profiles on a single page.
    """
    try:
        r = _http_get(url)
        soup = BeautifulSoup(r.text, "lxml")
        base = r.url
        host = urlparse(base).netloc.lower().lstrip("www.")
        internal, external, anchors = {}, {}, {}
        for a in soup.find_all("a", href=True):
            href = urljoin(base, a["href"]).split("#")[0]
            if not href.startswith(("http://", "https://")):
                continue
            text = " ".join(a.get_text(strip=True).split())[:120]
            netloc = urlparse(href).netloc.lower().lstrip("www.")
            target = internal if netloc.endswith(host) else external
            target[href] = target.get(href, 0) + 1
            anchors.setdefault(href, set()).add(text)
        return {
            "ok": True,
            "url": base,
            "internal": sorted(internal.keys()),
            "external": sorted(external.keys()),
            "counts": {"internal": len(internal), "external": len(external)},
            "anchor_texts": {k: sorted(v) for k, v in anchors.items()},
        }
    except Exception as e:
        return {"ok": False, "url": url, "error": str(e)}
