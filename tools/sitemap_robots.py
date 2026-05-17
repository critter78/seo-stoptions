"""robots.txt and sitemap.xml fetching/parsing."""
from __future__ import annotations

from typing import Dict, List
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from langchain_core.tools import tool

from app.config import USER_AGENT, REQUEST_TIMEOUT


def _origin(url: str) -> str:
    p = urlparse(url if "://" in url else f"https://{url}")
    return f"{p.scheme or 'https'}://{p.netloc or p.path}"


@tool
def fetch_robots_txt(domain_or_url: str) -> Dict[str, object]:
    """Fetch and parse robots.txt for a domain.

    Returns the raw text, sitemap URLs declared, disallowed paths,
    and crawl-delay (if present).
    """
    origin = _origin(domain_or_url)
    url = f"{origin.rstrip('/')}/robots.txt"
    try:
        r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT)
    except Exception as e:
        return {"ok": False, "url": url, "error": str(e)}
    text = r.text if r.ok else ""
    sitemaps, disallows, crawl_delay = [], [], None
    current_agents: List[str] = []
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if ":" not in s:
            continue
        key, _, val = s.partition(":")
        key, val = key.strip().lower(), val.strip()
        if key == "user-agent":
            current_agents = [val]
        elif key == "sitemap":
            sitemaps.append(val)
        elif key == "disallow" and ("*" in current_agents or any(a in ("*",) for a in current_agents)):
            if val:
                disallows.append(val)
        elif key == "crawl-delay":
            crawl_delay = val
    return {
        "ok": r.ok,
        "url": url,
        "status_code": r.status_code,
        "raw": text[:8000],
        "sitemaps": sitemaps,
        "disallow_for_star": disallows,
        "crawl_delay": crawl_delay,
    }


@tool
def fetch_sitemap_urls(sitemap_url: str, max_urls: int = 200) -> Dict[str, object]:
    """Fetch a sitemap.xml (or sitemap index) and return the URLs inside.

    Handles sitemap-index files by recursively pulling the first child sitemaps
    until max_urls URLs are collected.
    """
    collected: List[str] = []
    visited: List[str] = []

    def _pull(u: str):
        if len(collected) >= max_urls or u in visited:
            return
        visited.append(u)
        try:
            r = requests.get(u, headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT)
            soup = BeautifulSoup(r.text, "xml")
        except Exception:
            return
        # sitemap index?
        for sm in soup.find_all("sitemap"):
            loc = sm.find("loc")
            if loc and loc.text:
                _pull(loc.text.strip())
                if len(collected) >= max_urls:
                    return
        # url entries
        for u_node in soup.find_all("url"):
            loc = u_node.find("loc")
            if loc and loc.text:
                collected.append(loc.text.strip())
                if len(collected) >= max_urls:
                    return

    try:
        _pull(sitemap_url)
    except Exception as e:
        return {"ok": False, "url": sitemap_url, "error": str(e)}

    return {
        "ok": True,
        "sitemap_url": sitemap_url,
        "urls": collected,
        "count": len(collected),
        "sitemaps_visited": visited,
    }
