"""Google PageSpeed Insights v5 wrapper (free, optional API key)."""
from __future__ import annotations

from typing import Dict
import requests
from langchain_core.tools import tool

from app.config import GOOGLE_PAGESPEED_API_KEY, REQUEST_TIMEOUT


PSI_ENDPOINT = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"


@tool
def pagespeed_insights(url: str, strategy: str = "mobile") -> Dict[str, object]:
    """Run Google PageSpeed Insights against a URL.

    strategy: "mobile" (default) or "desktop".
    Returns Lighthouse scores (performance, accessibility, best-practices, SEO),
    Core Web Vitals (LCP, CLS, INP, TTFB, FCP) and the top opportunities.

    Works without an API key but quota is much higher with one set in
    GOOGLE_PAGESPEED_API_KEY.
    """
    params = {
        "url": url,
        "strategy": strategy if strategy in ("mobile", "desktop") else "mobile",
        "category": ["performance", "accessibility", "best-practices", "seo"],
    }
    if GOOGLE_PAGESPEED_API_KEY:
        params["key"] = GOOGLE_PAGESPEED_API_KEY
    try:
        r = requests.get(PSI_ENDPOINT, params=params, timeout=60)
        if not r.ok:
            return {"ok": False, "status_code": r.status_code, "error": r.text[:500]}
        data = r.json()
    except Exception as e:
        return {"ok": False, "error": str(e)}

    lhr = data.get("lighthouseResult", {}) or {}
    cats = lhr.get("categories", {}) or {}
    scores = {k: round((v.get("score") or 0) * 100) for k, v in cats.items()}

    audits = lhr.get("audits", {}) or {}
    cwv_keys = ["largest-contentful-paint", "cumulative-layout-shift",
                "interaction-to-next-paint", "server-response-time", "first-contentful-paint",
                "total-blocking-time", "speed-index"]
    cwv = {k: audits.get(k, {}).get("displayValue") for k in cwv_keys}

    opps = []
    for k, a in audits.items():
        if a.get("details", {}).get("type") == "opportunity" and (a.get("score") or 1) < 0.9:
            opps.append({
                "id": k,
                "title": a.get("title"),
                "description": a.get("description"),
                "savings_ms": a.get("details", {}).get("overallSavingsMs"),
            })
    opps.sort(key=lambda x: -(x.get("savings_ms") or 0))

    return {
        "ok": True,
        "url": url,
        "strategy": params["strategy"],
        "scores": scores,
        "core_web_vitals": cwv,
        "top_opportunities": opps[:10],
    }
