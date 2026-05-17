"""WebPageTest API wrapper.

WebPageTest gives deeper performance data than PageSpeed Insights:
  - filmstrip (visual progress over time)
  - per-request network waterfall
  - first/repeat-view comparison (caching benefit)
  - real-browser metrics from a chosen test location/connection

Requires a free API key from https://www.webpagetest.org/getkey.php
(set WEBPAGETEST_API_KEY in .env).

This tool submits a test, polls for completion, and returns the key metrics.
Average completion time: 30-90 seconds.
"""
from __future__ import annotations

import time
from typing import Dict, Optional

import requests
from langchain_core.tools import tool

from app.config import REQUEST_TIMEOUT, WEBPAGETEST_API_KEY

WPT_BASE = "https://www.webpagetest.org"


@tool
def webpagetest(
    url: str,
    location: str = "Dulles:Chrome",
    connection: str = "Cable",
    runs: int = 1,
    wait_seconds: int = 90,
) -> Dict[str, object]:
    """Run a WebPageTest performance test on a URL.

    Args:
        url: page to test.
        location: test location + browser, e.g. "Dulles:Chrome", "London_EC2:Chrome",
                  "Mumbai:Chrome", "Sydney:Chrome".
        connection: "Cable" (default), "FIOS", "DSL", "3GFast", "3G", "2G", "Native".
        runs: how many test iterations (default 1, max 3).
        wait_seconds: poll until result is ready, up to this many seconds (default 90).

    Returns the median test results including:
      - first-view + repeat-view timings
      - Speed Index, LCP, FCP, TTI, TTFB, fully-loaded time
      - bytes in, requests
      - filmstrip + waterfall URLs (for visual inspection)
    """
    if not WEBPAGETEST_API_KEY:
        return {
            "ok": False, "configured": False,
            "message": (
                "WEBPAGETEST_API_KEY is not set. Get a free key at "
                "https://www.webpagetest.org/getkey.php and add to .env."
            ),
        }

    runs = max(1, min(int(runs), 3))

    # 1) Submit the test (uses X-WPT-API-KEY header per Catchpoint docs)
    try:
        submit = requests.post(
            f"{WPT_BASE}/runtest.php",
            params={
                "url": url, "f": "json",
                "location": f"{location}.{connection}",
                "runs": runs, "fvonly": 0,
            },
            headers={"X-WPT-API-KEY": WEBPAGETEST_API_KEY},
            timeout=REQUEST_TIMEOUT,
        )
        submit_data = submit.json()
    except Exception as e:
        return {"ok": False, "error": f"Submit failed: {e}"}

    if submit_data.get("statusCode") != 200:
        return {
            "ok": False, "submit_response": submit_data,
            "error": submit_data.get("statusText", "Unknown submit error"),
        }

    data = submit_data.get("data", {})
    test_id = data.get("testId")
    json_url = data.get("jsonUrl")
    user_url = data.get("userUrl")
    if not test_id:
        return {"ok": False, "error": "No testId returned by WebPageTest."}

    # 2) Poll for completion
    deadline = time.time() + max(15, int(wait_seconds))
    last_status = None
    while time.time() < deadline:
        try:
            check = requests.get(
                f"{WPT_BASE}/testStatus.php",
                params={"f": "json", "test": test_id},
                timeout=REQUEST_TIMEOUT,
            )
            cd = check.json().get("data", {})
            last_status = cd.get("statusText")
            if cd.get("statusCode") == 200:
                break  # done
        except Exception:
            pass
        time.sleep(5)
    else:
        return {
            "ok": False, "test_id": test_id, "result_url": user_url,
            "error": f"Test did not complete within {wait_seconds}s "
                     f"(last status: {last_status}). Check {user_url} later.",
        }

    # 3) Fetch the results
    try:
        result = requests.get(json_url, timeout=REQUEST_TIMEOUT).json()
    except Exception as e:
        return {"ok": False, "error": f"Result fetch failed: {e}",
                "test_id": test_id, "result_url": user_url}

    rdata = result.get("data", {})
    runs_data = (rdata.get("runs") or {})
    median = (rdata.get("median") or {}).get("firstView") or {}
    repeat = (rdata.get("median") or {}).get("repeatView") or {}

    def _pick(d, keys):
        return {k: d.get(k) for k in keys if k in d}

    metric_keys = [
        "loadTime", "TTFB", "render", "SpeedIndex",
        "firstContentfulPaint", "largestContentfulPaint",
        "cumulativeLayoutShift", "TotalBlockingTime", "interactive",
        "fullyLoaded", "requestsFull", "bytesIn",
    ]

    return {
        "ok": True,
        "url": url,
        "test_id": test_id,
        "result_url": user_url,
        "location": location,
        "connection": connection,
        "runs": runs,
        "first_view": _pick(median, metric_keys),
        "repeat_view": _pick(repeat, metric_keys),
        "filmstrip_url": rdata.get("summary"),
        "waterfall_url": median.get("images", {}).get("waterfall") if isinstance(median.get("images"), dict) else None,
    }
