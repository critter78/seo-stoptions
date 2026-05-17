"""Google Analytics 4 tools — traffic, sources, conversions, landing-page joins.

Uses the GA4 Data API via `google-analytics-data`. Requires:
  - GA4_OAUTH_TOKEN_JSON pointing at a refresh-token file (run tools/ga4_oauth_setup.py)
  - GA4_PROPERTY_ID set to your 9-digit GA4 property ID
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Dict, List, Optional

from langchain_core.tools import tool

from app.config import GA4_OAUTH_TOKEN_JSON, GA4_PROPERTY_ID

SCOPES = ["https://www.googleapis.com/auth/analytics.readonly"]


def _ga4_client():
    """Build a BetaAnalyticsDataClient using the OAuth refresh token."""
    try:
        from google.analytics.data_v1beta import BetaAnalyticsDataClient  # type: ignore
        from google.oauth2.credentials import Credentials  # type: ignore
        from google.auth.transport.requests import Request  # type: ignore
    except ImportError as e:
        raise RuntimeError(
            "google-analytics-data not installed. Run pip install -r requirements.txt"
        ) from e

    if not (GA4_OAUTH_TOKEN_JSON and Path(GA4_OAUTH_TOKEN_JSON).exists()):
        raise RuntimeError(
            "GA4_OAUTH_TOKEN_JSON not configured. "
            "Run `python -m tools.ga4_oauth_setup`."
        )
    if not GA4_PROPERTY_ID:
        raise RuntimeError(
            "GA4_PROPERTY_ID not set. Find it in GA4 → Admin → Property Settings "
            "(9-digit number). Add to .env."
        )

    creds = Credentials.from_authorized_user_file(GA4_OAUTH_TOKEN_JSON, SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        Path(GA4_OAUTH_TOKEN_JSON).write_text(creds.to_json())
    return BetaAnalyticsDataClient(credentials=creds)


def _configured() -> bool:
    return bool(GA4_OAUTH_TOKEN_JSON and GA4_PROPERTY_ID)


def _run_report(
    dimensions: List[str], metrics: List[str], days: int = 28,
    row_limit: int = 50, order_by_metric: Optional[str] = None,
    filter_expr=None,
) -> Dict:
    from google.analytics.data_v1beta.types import (  # type: ignore
        DateRange, Dimension, Metric, OrderBy, RunReportRequest,
    )
    client = _ga4_client()
    end = dt.date.today()
    start = end - dt.timedelta(days=int(days))
    req = RunReportRequest(
        property=f"properties/{GA4_PROPERTY_ID}",
        dimensions=[Dimension(name=d) for d in dimensions],
        metrics=[Metric(name=m) for m in metrics],
        date_ranges=[DateRange(start_date=start.isoformat(), end_date=end.isoformat())],
        limit=row_limit,
        order_bys=(
            [OrderBy(metric=OrderBy.MetricOrderBy(metric_name=order_by_metric), desc=True)]
            if order_by_metric else None
        ),
        dimension_filter=filter_expr,
    )
    resp = client.run_report(req)
    rows = []
    for row in resp.rows:
        entry = {}
        for i, d in enumerate(dimensions):
            entry[d] = row.dimension_values[i].value
        for i, m in enumerate(metrics):
            v = row.metric_values[i].value
            try:
                entry[m] = float(v) if "." in v else int(v)
            except Exception:
                entry[m] = v
        rows.append(entry)
    return {"range": f"{start} to {end}", "row_count": len(rows), "rows": rows}


# ============================================================================
@tool
def ga4_top_pages(days: int = 28, row_limit: int = 50) -> Dict[str, object]:
    """Top pages by users + sessions + conversions over the last N days.

    Returns rows of {pagePath, pageTitle, sessions, totalUsers, screenPageViews,
    averageSessionDuration, engagementRate, conversions}.
    """
    if not _configured():
        return {"ok": False, "configured": False,
                "message": "GA4 not configured. Run tools/ga4_oauth_setup.py and "
                           "set GA4_PROPERTY_ID."}
    try:
        out = _run_report(
            dimensions=["pagePath", "pageTitle"],
            metrics=["sessions", "totalUsers", "screenPageViews",
                     "averageSessionDuration", "engagementRate", "conversions"],
            days=days, row_limit=row_limit, order_by_metric="totalUsers",
        )
        return {"ok": True, "configured": True, **out}
    except Exception as e:
        return {"ok": False, "configured": True, "error": str(e)}


@tool
def ga4_traffic_sources(days: int = 28, row_limit: int = 50) -> Dict[str, object]:
    """Traffic source / medium breakdown over the last N days.

    Returns rows of {sessionDefaultChannelGroup, sessionSource, sessionMedium,
    sessions, totalUsers, conversions, engagementRate}.

    Useful for: confirming organic-search growth vs paid/direct, finding referrers,
    spotting which channels actually convert.
    """
    if not _configured():
        return {"ok": False, "configured": False, "message": "GA4 not configured."}
    try:
        out = _run_report(
            dimensions=["sessionDefaultChannelGroup", "sessionSource", "sessionMedium"],
            metrics=["sessions", "totalUsers", "conversions", "engagementRate"],
            days=days, row_limit=row_limit, order_by_metric="sessions",
        )
        return {"ok": True, "configured": True, **out}
    except Exception as e:
        return {"ok": False, "configured": True, "error": str(e)}


@tool
def ga4_conversions(days: int = 28, row_limit: int = 50) -> Dict[str, object]:
    """Conversion events over the last N days.

    Returns rows of {eventName, eventCount, totalUsers, conversions}.

    Use this to see which events are firing (trial_signup, plan_subscribe,
    newsletter_subscribe, etc.) and how they trend. Configure events as
    conversions in GA4 admin → Events → mark as conversion.
    """
    if not _configured():
        return {"ok": False, "configured": False, "message": "GA4 not configured."}
    try:
        out = _run_report(
            dimensions=["eventName"],
            metrics=["eventCount", "totalUsers", "conversions"],
            days=days, row_limit=row_limit, order_by_metric="eventCount",
        )
        return {"ok": True, "configured": True, **out}
    except Exception as e:
        return {"ok": False, "configured": True, "error": str(e)}


@tool
def ga4_landing_pages(days: int = 28, row_limit: int = 50) -> Dict[str, object]:
    """Top landing pages for organic search over the last N days.

    Filters to organic search sessions only. Returns rows of {landingPagePlusQueryString,
    sessions, totalUsers, conversions, engagementRate}. Use this to see which pages
    actually pull people in from organic search and which ones convert.
    """
    if not _configured():
        return {"ok": False, "configured": False, "message": "GA4 not configured."}
    try:
        from google.analytics.data_v1beta.types import (  # type: ignore
            Filter, FilterExpression,
        )
        # Filter to organic search
        organic_filter = FilterExpression(
            filter=Filter(
                field_name="sessionDefaultChannelGroup",
                string_filter=Filter.StringFilter(value="Organic Search"),
            )
        )
        out = _run_report(
            dimensions=["landingPagePlusQueryString"],
            metrics=["sessions", "totalUsers", "conversions", "engagementRate"],
            days=days, row_limit=row_limit, order_by_metric="sessions",
            filter_expr=organic_filter,
        )
        return {"ok": True, "configured": True, **out}
    except Exception as e:
        return {"ok": False, "configured": True, "error": str(e)}


@tool
def ga4_realtime_active_users() -> Dict[str, object]:
    """Real-time active users on the site right now.

    Returns {active_users, by_country, by_page}. Useful for confirming the site is
    actually getting traffic before running heavier diagnostics.
    """
    if not _configured():
        return {"ok": False, "configured": False, "message": "GA4 not configured."}
    try:
        from google.analytics.data_v1beta.types import (  # type: ignore
            Dimension, Metric, RunRealtimeReportRequest,
        )
        client = _ga4_client()
        req = RunRealtimeReportRequest(
            property=f"properties/{GA4_PROPERTY_ID}",
            dimensions=[Dimension(name="country"), Dimension(name="unifiedScreenName")],
            metrics=[Metric(name="activeUsers")],
            limit=25,
        )
        resp = client.run_realtime_report(req)
        rows = []
        total = 0
        for r in resp.rows:
            v = int(r.metric_values[0].value or 0)
            total += v
            rows.append({
                "country": r.dimension_values[0].value,
                "page": r.dimension_values[1].value,
                "active_users": v,
            })
        return {"ok": True, "configured": True, "total_active_users": total, "rows": rows}
    except Exception as e:
        return {"ok": False, "configured": True, "error": str(e)}
