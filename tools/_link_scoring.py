"""Internal-link quality scoring.

Each internal link gets scored on three axes (each 0..1):
  - relevance     : Jaccard overlap of anchor text vs. (page title + H1)
  - position      : header=0.6, body=1.0, footer=0.3, aside=0.5, nav=0.7
  - anchor_quality: 1.0 for descriptive anchors, 0.4 for generic ones
                    ("click here", "read more", "learn more", bare URL, "here")
The composite score = mean of the three.
"""
from __future__ import annotations

import re
from typing import Dict, List, Set
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup


GENERIC_ANCHORS = {
    "click here", "click", "here", "read more", "read", "learn more", "more",
    "this", "this link", "link", "see more", "view more", "details",
}

POSITION_WEIGHTS = {
    "header": 0.6,
    "nav": 0.7,
    "main": 1.0,
    "article": 1.0,
    "section": 0.95,
    "aside": 0.5,
    "footer": 0.3,
    "body": 0.85,
}


def _tokens(s: str) -> Set[str]:
    return {w.lower() for w in re.findall(r"[A-Za-z]{3,}", s or "")}


def _position_for(tag) -> str:
    for parent in tag.parents:
        if not getattr(parent, "name", None):
            continue
        if parent.name in POSITION_WEIGHTS:
            return parent.name
    return "body"


def score_internal_links(soup: BeautifulSoup, base_url: str, page_title: str = "", h1_text: str = "") -> Dict:
    base_host = urlparse(base_url).netloc.lower().lstrip("www.")
    page_topic_tokens = _tokens(page_title) | _tokens(h1_text)

    rows: List[Dict] = []
    seen: Set[str] = set()

    for a in soup.find_all("a", href=True):
        href = urljoin(base_url, a["href"]).split("#")[0]
        if not href.startswith(("http://", "https://")):
            continue
        host = urlparse(href).netloc.lower().lstrip("www.")
        if not host.endswith(base_host):
            continue  # internal only

        anchor_raw = " ".join(a.get_text(strip=True).split())
        if not anchor_raw:
            continue

        key = (href, anchor_raw.lower())
        if key in seen:
            continue
        seen.add(key)

        anchor_tokens = _tokens(anchor_raw)
        if page_topic_tokens and anchor_tokens:
            inter = page_topic_tokens & anchor_tokens
            uni = page_topic_tokens | anchor_tokens
            relevance = round(len(inter) / max(len(uni), 1), 2)
        else:
            relevance = 0.0

        position_name = _position_for(a)
        position_score = POSITION_WEIGHTS.get(position_name, 0.85)

        is_generic = anchor_raw.lower().strip() in GENERIC_ANCHORS or anchor_raw.startswith("http")
        anchor_quality = 0.4 if is_generic else 1.0

        composite = round((relevance + position_score + anchor_quality) / 3, 2)

        rows.append({
            "href": href,
            "anchor": anchor_raw[:120],
            "position": position_name,
            "relevance": relevance,
            "position_score": position_score,
            "anchor_quality": anchor_quality,
            "score": composite,
            "generic_anchor": is_generic,
        })

    rows.sort(key=lambda r: r["score"])
    avg = round(sum(r["score"] for r in rows) / max(len(rows), 1), 2) if rows else 0.0
    weakest = rows[:5]

    return {
        "internal_link_count": len(rows),
        "avg_internal_link_score": avg,
        "weakest_internal_links": weakest,
        "links": rows[:50],
    }
