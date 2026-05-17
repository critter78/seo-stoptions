"""Google Search Console tools.

Supports two auth modes:
  1. **OAuth user credentials** — GSC_OAUTH_TOKEN_JSON (recommended)
  2. **Service account** — GSC_SERVICE_ACCOUNT_JSON

Tools exposed to the agents:
  - gsc_top_queries        — search analytics (queries/pages/countries/devices)
  - gsc_url_inspection     — index status + CWV + rich results for a single URL
  - gsc_sitemap_status     — submitted sitemaps + their indexing health
  - gsc_inspect_url_sample — bulk-inspect N URLs from a sitemap (coverage scan)
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Dict, List, Optional

from langchain_core.tools import tool

from app.config import (
    GSC_DEFAULT_SITE,
    GSC_OAUTH_TOKEN_JSON,
    GSC_SERVICE_ACCOUNT_JSON,
)
from app.db import log_gsc_snapshot

SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]


def _gsc_service():
    """Build a Search Console service object via OAuth or service account."""
    try:
        from googleapiclient.discovery import build  # type: ignore
    except ImportError as e:
        raise RuntimeError(
            "google-api-python-client / google-auth not installed. "
            "Add to requirements.txt and pip install."
        ) from e

    if GSC_OAUTH_TOKEN_JSON and Path(GSC_OAUTH_TOKEN_JSON).exists():
        from google.oauth2.credentials import Credentials  # type: ignore
        from google.auth.transport.requests import Request  # type: ignore
        creds = Credentials.from_authorized_user_file(GSC_OAUTH_TOKEN_JSON, SCOPES)
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            Path(GSC_OAUTH_TOKEN_JSON).write_text(creds.to_json())
        return build("searchconsole", "v1", credentials=creds, cache_discovery=False)

    if GSC_SERVICE_ACCOUNT_JSON and Path(GSC_SERVICE_ACCOUNT_JSON).exists():
        from google.oauth2 import service_account  # type: ignore
        creds = service_account.Credentials.from_service_account_file(
            GSC_SERVICE_ACCOUNT_JSON, scopes=SCOPES,
        )
        return build("searchconsole", "v1", credentials=creds, cache_discovery=False)

    raise RuntimeError(
        "Neither GSC_OAUTH_TOKEN_JSON nor GSC_SERVICE_ACCOUNT_JSON is configured."
    )


def _configured() -> bool:
    return bool(GSC_OAUTH_TOKEN_JSON or GSC_SERVICE_ACCOUNT_JSON)


# ============================================================================
@tool
def gsc_top_queries(
    site_url: str = "",
    days: int = 28,
    row_limit: int = 50,
    dimension: str = "query",
) -> Dict[str, object]:
    """Pull top search queries / pages / countries / devices from Search Console.

    Args:
        site_url: GSC property — defaults to GSC_DEFAULT_SITE (e.g. "sc-domain:stoptions.ai").
        days: lookback window in days (default 28).
        row_limit: max rows returned (default 50, max 25000).
        dimension: "query" | "page" | "country" | "device".

    Every call is **persisted to SQLite** so the Morning Briefing can compute
    week-over-week movers across snapshots.
    """
    site_url = site_url or GSC_DEFAULT_SITE
    if not _configured():
        return {"ok": False, "configured": False,
                "message": "GSC is not configured. Run setup_gsc.sh."}
    try:
        service = _gsc_service()
        end = dt.date.today()
        start = end - dt.timedelta(days=int(days))
        body = {
            "startDate": start.isoformat(),
            "endDate": end.isoformat(),
            "dimensions": [dimension],
            "rowLimit": int(row_limit),
        }
        resp = service.searchanalytics().query(siteUrl=site_url, body=body).execute()
        rows: List[Dict] = []
        snapshot_rows: List[Dict] = []
        for row in resp.get("rows", []):
            key = (row.get("keys") or [""])[0]
            entry = {
                dimension: key,
                "clicks": row.get("clicks"),
                "impressions": row.get("impressions"),
                "ctr": round(row.get("ctr", 0) * 100, 2),
                "position": round(row.get("position", 0), 2),
            }
            rows.append(entry)
            snapshot_rows.append({
                "key": key,
                "clicks": row.get("clicks"),
                "impressions": row.get("impressions"),
                "ctr": row.get("ctr"),
                "position": row.get("position"),
            })

        # Persist for week-over-week diffing
        try:
            log_gsc_snapshot(site_url, dimension, snapshot_rows, start.isoformat(), end.isoformat())
        except Exception:
            pass  # logging is best-effort

        return {
            "ok": True,
            "configured": True,
            "auth_mode": "oauth" if GSC_OAUTH_TOKEN_JSON else "service_account",
            "site_url": site_url,
            "range": f"{start} to {end}",
            "dimension": dimension,
            "rows": rows,
            "snapshot_persisted": True,
        }
    except Exception as e:
        return {"ok": False, "configured": True, "error": str(e)}


# ============================================================================
@tool
def gsc_url_inspection(
    page_url: str,
    site_url: str = "",
) -> Dict[str, object]:
    """Run Search Console URL Inspection on a single URL.

    Returns deep per-URL data:
      - **indexStatusResult**: coverageState, robotsTxtState, indexingState,
        crawledAs, lastCrawlTime, pageFetchState, googleCanonical, userCanonical,
        sitemap inclusion, referring URLs.
      - **mobileUsabilityResult**: mobile issues (touch-target, viewport, etc.).
      - **richResultsResult**: detected rich result types + verdict + items.
      - **ampResult** (if applicable).

    Args:
        page_url: full URL to inspect (must be under the property).
        site_url: GSC property — defaults to GSC_DEFAULT_SITE.

    This is the single most useful diagnostic — call it on any URL where you
    want to know "why isn't Google indexing this?" or "why isn't my schema
    showing as a rich result?".
    """
    site_url = site_url or GSC_DEFAULT_SITE
    if not _configured():
        return {"ok": False, "configured": False,
                "message": "GSC is not configured. Run setup_gsc.sh."}
    try:
        service = _gsc_service()
        body = {"inspectionUrl": page_url, "siteUrl": site_url}
        resp = service.urlInspection().index().inspect(body=body).execute()
        return {
            "ok": True,
            "url": page_url,
            "site_url": site_url,
            "inspectionResult": resp.get("inspectionResult", {}),
        }
    except Exception as e:
        return {"ok": False, "url": page_url, "error": str(e)}


# ============================================================================
@tool
def gsc_sitemap_status(site_url: str = "") -> Dict[str, object]:
    """List all sitemaps submitted to Search Console for the property,
    along with their submission status, error counts, and indexed URL counts.

    Returns: {sitemaps: [{path, lastSubmitted, lastDownloaded, errors,
        warnings, contents (per type: submitted/indexed)}, ...]}.

    Use this in audits to confirm:
      - the right sitemaps are submitted,
      - they're being fetched without errors,
      - the indexed-vs-submitted ratio is healthy.
    """
    site_url = site_url or GSC_DEFAULT_SITE
    if not _configured():
        return {"ok": False, "configured": False,
                "message": "GSC is not configured."}
    try:
        service = _gsc_service()
        resp = service.sitemaps().list(siteUrl=site_url).execute()
        sitemaps = []
        for sm in resp.get("sitemap", []):
            sitemaps.append({
                "path": sm.get("path"),
                "lastSubmitted": sm.get("lastSubmitted"),
                "lastDownloaded": sm.get("lastDownloaded"),
                "isPending": sm.get("isPending"),
                "isSitemapsIndex": sm.get("isSitemapsIndex"),
                "errors": sm.get("errors"),
                "warnings": sm.get("warnings"),
                "contents": sm.get("contents", []),
            })
        return {"ok": True, "site_url": site_url, "sitemaps": sitemaps,
                "count": len(sitemaps)}
    except Exception as e:
        return {"ok": False, "site_url": site_url, "error": str(e)}


# ============================================================================
@tool
def gsc_inspect_url_sample(
    sitemap_url: str,
    sample_size: int = 10,
    site_url: str = "",
) -> Dict[str, object]:
    """Coverage sampler — inspect N URLs from a sitemap to estimate site health.

    Pulls URLs from the sitemap, picks a sample, runs URL Inspection on each,
    aggregates coverage stats (indexed / not indexed / errors / excluded).

    Args:
        sitemap_url: full sitemap URL (e.g. https://stoptions.ai/sitemap.xml).
        sample_size: how many URLs to inspect (default 10, max 25 to respect quota).
        site_url: GSC property — defaults to GSC_DEFAULT_SITE.

    Quota note: each inspection is 1 API call against the daily quota (~2000/day).
    """
    site_url = site_url or GSC_DEFAULT_SITE
    sample_size = max(1, min(int(sample_size), 25))
    if not _configured():
        return {"ok": False, "configured": False,
                "message": "GSC is not configured."}
    # Pull candidate URLs from the sitemap
    try:
        from tools.sitemap_robots import fetch_sitemap_urls
        sm_resp = fetch_sitemap_urls.invoke({"sitemap_url": sitemap_url, "max_urls": 200})
        if not sm_resp.get("ok"):
            return {"ok": False, "error": f"Sitemap fetch failed: {sm_resp.get('error')}"}
        candidates = sm_resp.get("urls", [])
    except Exception as e:
        return {"ok": False, "error": f"Sitemap fetch error: {e}"}

    if not candidates:
        return {"ok": False, "error": "No URLs found in sitemap."}

    # Take a sample (evenly distributed, including first + last + middle)
    step = max(1, len(candidates) // sample_size)
    sample = candidates[::step][:sample_size]

    inspected = []
    summary = {"indexed": 0, "not_indexed": 0, "errors": 0,
               "excluded": 0, "mobile_issues": 0}

    for url in sample:
        try:
            r = gsc_url_inspection.invoke({"page_url": url, "site_url": site_url})
        except Exception as e:
            inspected.append({"url": url, "error": str(e)})
            summary["errors"] += 1
            continue
        if not r.get("ok"):
            inspected.append({"url": url, "error": r.get("error")})
            summary["errors"] += 1
            continue
        result = r.get("inspectionResult", {}) or {}
        idx = (result.get("indexStatusResult") or {})
        mobile = (result.get("mobileUsabilityResult") or {})
        coverage = idx.get("coverageState", "unknown")
        verdict = idx.get("verdict", "unknown")
        inspected.append({
            "url": url,
            "verdict": verdict,
            "coverageState": coverage,
            "indexingState": idx.get("indexingState"),
            "lastCrawlTime": idx.get("lastCrawlTime"),
            "googleCanonical": idx.get("googleCanonical"),
            "userCanonical": idx.get("userCanonical"),
            "mobileVerdict": mobile.get("verdict"),
        })
        v = (verdict or "").upper()
        if v == "PASS":
            summary["indexed"] += 1
        elif "EXCLUDED" in (coverage or "").upper():
            summary["excluded"] += 1
        else:
            summary["not_indexed"] += 1
        if (mobile.get("verdict") or "").upper() not in ("PASS", ""):
            summary["mobile_issues"] += 1

    return {
        "ok": True,
        "site_url": site_url,
        "sitemap_url": sitemap_url,
        "sample_size": len(sample),
        "total_sitemap_urls": len(candidates),
        "summary": summary,
        "inspected": inspected,
        "indexed_rate_pct": round(100 * summary["indexed"] / max(len(sample), 1), 1),
    }
