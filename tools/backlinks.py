"""Free-tier inbound-link signal discovery.

No paid API access, so we approximate by:
  1. DuckDuckGo "link:" / unique-quote queries to surface pages mentioning the URL.
  2. Common Crawl Index API (CCI) host lookups for known pages.
  3. Wayback Machine CDX API for historical references.

These are signals, not a full Ahrefs replacement — but they're useful for the
Jr Marketer to plan outreach and for the analyst to spot mention opportunities.
"""
from __future__ import annotations

import datetime as dt
from typing import Dict, List
from urllib.parse import quote_plus, urlparse

import requests
from langchain_core.tools import tool

from app.config import USER_AGENT, REQUEST_TIMEOUT


@tool
def find_backlink_signals(url_or_domain: str, max_per_source: int = 15) -> Dict[str, object]:
    """Discover free-tier inbound-link signals for a URL or domain.

    Combines DuckDuckGo SERP mentions, Common Crawl host index, and the
    Wayback Machine CDX API. Returns a deduped list of referring URLs and
    raw evidence per source.
    """
    domain = urlparse(url_or_domain if "://" in url_or_domain else f"https://{url_or_domain}").netloc
    domain = domain.lstrip("www.")
    target = url_or_domain if "://" in url_or_domain else f"https://{domain}"

    referring: Dict[str, str] = {}  # url -> source

    # 1) DuckDuckGo mentions (exclude same domain)
    try:
        try:
            from ddgs import DDGS  # type: ignore
        except ImportError:
            from duckduckgo_search import DDGS  # type: ignore
        q = f'"{domain}" -site:{domain}'
        with DDGS() as ddgs:
            for r in ddgs.text(q, max_results=max_per_source):
                u = r.get("href")
                if u and domain not in urlparse(u).netloc:
                    referring.setdefault(u, "duckduckgo")
    except Exception:
        pass

    # 2) Wayback CDX – pages that link to this URL would be hard to query;
    # but CDX captures of THIS url give us crawl history (useful as authority signal).
    wayback_captures = []
    try:
        cdx = (
            "https://web.archive.org/cdx/search/cdx"
            f"?url={quote_plus(target)}&output=json&limit=20&fl=timestamp,original,statuscode"
        )
        r = requests.get(cdx, headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT)
        if r.ok and r.text.strip():
            rows = r.json()
            for row in rows[1:]:  # skip header
                wayback_captures.append({"timestamp": row[0], "original": row[1], "status": row[2]})
    except Exception:
        pass

    # 3) Common Crawl host index – look up pages on this host across recent crawls.
    cc_pages = []
    try:
        idx = "https://index.commoncrawl.org/collinfo.json"
        r = requests.get(idx, headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT)
        if r.ok:
            collections = r.json()[:1]  # most recent only to stay fast
            for c in collections:
                api = c.get("cdx-api")
                if not api:
                    continue
                rr = requests.get(
                    api,
                    params={"url": f"{domain}/*", "output": "json", "limit": max_per_source},
                    headers={"User-Agent": USER_AGENT},
                    timeout=REQUEST_TIMEOUT,
                )
                if rr.ok and rr.text.strip():
                    for line in rr.text.strip().splitlines():
                        try:
                            import json
                            obj = json.loads(line)
                            cc_pages.append({"url": obj.get("url"), "status": obj.get("status"),
                                             "timestamp": obj.get("timestamp")})
                        except Exception:
                            continue
    except Exception:
        pass

    return {
        "ok": True,
        "queried_domain": domain,
        "target": target,
        "queried_at": dt.datetime.utcnow().isoformat() + "Z",
        "referring_urls": sorted(referring.keys()),
        "referring_count": len(referring),
        "wayback_captures": wayback_captures,
        "common_crawl_pages": cc_pages[:max_per_source],
        "notes": "These are free-tier signals — for production-grade backlink intelligence add an Ahrefs/SEMrush key.",
    }
