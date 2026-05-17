"""On-page SEO audit: title, meta, headings, OG/Twitter, canonical, hreflang,
images, keyword density + semantic terms, mobile-friendliness, internal-link
quality, and (optionally) Core Web Vitals via PageSpeed Insights.
"""
from __future__ import annotations

from typing import Dict, List, Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from langchain_core.tools import tool

from app.config import USER_AGENT, REQUEST_TIMEOUT
from ._text_analysis import keyword_density
from ._mobile_checks import audit_mobile
from ._link_scoring import score_internal_links


def _get_meta(soup: BeautifulSoup, name: str) -> str:
    tag = soup.find("meta", attrs={"name": name}) or soup.find("meta", attrs={"property": name})
    return (tag.get("content") if tag else "") or ""


@tool
def onpage_audit(
    url: str,
    target_keyword: str = "",
    include_pagespeed: bool = False,
    pagespeed_strategy: str = "mobile",
) -> Dict[str, object]:
    """Run a comprehensive on-page SEO audit on a URL.

    Pulls:
      - Core: title, meta description, robots, canonical, hreflang, OG/Twitter
      - Headings: H1-H6 with counts
      - Images: total + missing-alt list
      - Word count & text/HTML ratio
      - **Keyword density & semantic terms** (top unigrams/bigrams/trigrams,
        plus density % of `target_keyword` if supplied)
      - **Mobile-friendliness**: viewport meta, zoom-blocking, media-query
        presence, small-font detection, AMP signal
      - **Internal-link quality scoring**: each internal link scored on
        anchor relevance, position, and anchor quality (composite 0-1)
      - **Core Web Vitals (optional)**: set `include_pagespeed=True` to run
        PageSpeed Insights inline (uses GOOGLE_PAGESPEED_API_KEY if set)
      - Issues list summarising the biggest problems

    Args:
        url: page to audit.
        target_keyword: optional keyword to score density against.
        include_pagespeed: if True, also run a PageSpeed Insights call.
        pagespeed_strategy: "mobile" (default) or "desktop".
    """
    try:
        r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT)
        soup = BeautifulSoup(r.text, "lxml")
    except Exception as e:
        return {"ok": False, "url": url, "error": str(e)}

    title = (soup.title.string.strip() if soup.title and soup.title.string else "")
    description = _get_meta(soup, "description")
    robots = _get_meta(soup, "robots")
    canonical_tag = soup.find("link", rel="canonical")
    canonical = canonical_tag.get("href") if canonical_tag else ""
    hreflang = [
        {"hreflang": l.get("hreflang"), "href": l.get("href")}
        for l in soup.find_all("link", rel="alternate")
        if l.get("hreflang")
    ]

    og = {m.get("property"): m.get("content") for m in soup.find_all("meta") if m.get("property", "").startswith("og:")}
    tw = {m.get("name"): m.get("content") for m in soup.find_all("meta") if (m.get("name") or "").startswith("twitter:")}

    headings = {f"h{i}": [h.get_text(strip=True) for h in soup.find_all(f"h{i}")] for i in range(1, 7)}
    h1_text = headings["h1"][0] if headings["h1"] else ""

    imgs = soup.find_all("img")
    img_total = len(imgs)
    img_missing_alt = [urljoin(url, i.get("src", "")) for i in imgs if not (i.get("alt") or "").strip()]

    body_text = " ".join(soup.get_text(separator=" ", strip=True).split())
    word_count = len(body_text.split())
    text_html_ratio = round(len(body_text) / max(len(r.text), 1), 3)

    # ---- New: keyword density & semantic n-grams
    density = keyword_density(body_text, target_keyword=target_keyword, top_k=15)

    # ---- New: mobile audit
    mobile = audit_mobile(soup, r.text)

    # ---- New: internal-link scoring
    link_quality = score_internal_links(soup, base_url=r.url, page_title=title, h1_text=h1_text)

    # ---- Optional: inline PageSpeed Insights
    psi: Optional[Dict] = None
    if include_pagespeed:
        try:
            from .pagespeed import pagespeed_insights as _psi
            psi = _psi.invoke({"url": r.url, "strategy": pagespeed_strategy})
        except Exception as e:
            psi = {"ok": False, "error": str(e)}

    issues: List[str] = []
    if not title:
        issues.append("Missing <title>")
    elif len(title) > 65:
        issues.append(f"Title too long ({len(title)} chars; aim 50-60)")
    elif len(title) < 25:
        issues.append(f"Title too short ({len(title)} chars; aim 50-60)")
    if not description:
        issues.append("Missing meta description")
    elif len(description) > 165:
        issues.append(f"Meta description too long ({len(description)} chars; aim 140-160)")
    elif len(description) < 70:
        issues.append(f"Meta description too short ({len(description)} chars; aim 140-160)")
    if not canonical:
        issues.append("Missing canonical link")
    if len(headings["h1"]) == 0:
        issues.append("No H1 found")
    elif len(headings["h1"]) > 1:
        issues.append(f"Multiple H1s ({len(headings['h1'])})")
    if "noindex" in (robots or "").lower():
        issues.append("Page is set to NOINDEX")
    if img_total and len(img_missing_alt) / img_total > 0.2:
        issues.append(f"{len(img_missing_alt)}/{img_total} images missing alt text")
    if word_count < 300:
        issues.append(f"Thin content ({word_count} words; aim >600 for ranking pages)")

    # New: keyword issues
    if target_keyword:
        d = density.get("target_keyword_density_pct") or 0
        if d == 0:
            issues.append(f"Target keyword \"{target_keyword}\" not found in page text")
        elif d < 0.3:
            issues.append(f"Target keyword density only {d}% (aim 0.5-1.5%)")
        elif d > 3.0:
            issues.append(f"Possible keyword stuffing — {d}% density (aim 0.5-1.5%)")

    # Mobile issues bubbled up
    issues.extend(mobile.get("issues", []))

    # Link-quality summary issues
    if link_quality["internal_link_count"] == 0:
        issues.append("No internal links found")
    elif link_quality["avg_internal_link_score"] < 0.55:
        issues.append(
            f"Weak internal-link profile (avg score {link_quality['avg_internal_link_score']}) — "
            "rewrite generic anchors and move key links into body content"
        )

    # PSI issues
    if psi and psi.get("ok"):
        scores = psi.get("scores", {}) or {}
        if scores.get("performance") is not None and scores["performance"] < 70:
            issues.append(f"PageSpeed performance score is low ({scores['performance']}/100)")
        if scores.get("seo") is not None and scores["seo"] < 90:
            issues.append(f"PageSpeed SEO score is low ({scores['seo']}/100)")

    return {
        "ok": True,
        "url": r.url,
        "status_code": r.status_code,
        "title": title,
        "title_length": len(title),
        "meta_description": description,
        "meta_description_length": len(description),
        "meta_robots": robots,
        "canonical": canonical,
        "hreflang": hreflang,
        "open_graph": og,
        "twitter_card": tw,
        "headings": headings,
        "h1_count": len(headings["h1"]),
        "images_total": img_total,
        "images_missing_alt": img_missing_alt[:25],
        "word_count": word_count,
        "text_html_ratio": text_html_ratio,
        "keyword_analysis": density,
        "mobile_audit": mobile,
        "internal_link_quality": link_quality,
        "pagespeed": psi,
        "issues": issues,
    }
