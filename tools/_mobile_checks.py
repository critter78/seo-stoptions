"""Mobile-friendliness signals you can derive from a static HTML payload.

Static HTML can't measure tap-target spacing in the rendered viewport, but it
*can* check the cheap-but-high-signal items: viewport meta, AMP/responsive
hints, font-size declarations in inline CSS, and the presence of a media-query
breakpoint somewhere in the HTML/inline-style payload.
"""
from __future__ import annotations

import re
from typing import Dict, List
from bs4 import BeautifulSoup


VIEWPORT_RECOMMENDED_WIDTH = "device-width"
VIEWPORT_RECOMMENDED_SCALE = "1"


def audit_mobile(soup: BeautifulSoup, raw_html: str) -> Dict:
    issues: List[str] = []

    vp_tag = soup.find("meta", attrs={"name": "viewport"})
    vp_content = (vp_tag.get("content") if vp_tag else "") or ""
    vp_lower = vp_content.lower()
    has_viewport = bool(vp_tag)
    width_ok = VIEWPORT_RECOMMENDED_WIDTH in vp_lower
    scale_ok = "initial-scale=1" in vp_lower or "initial-scale=1.0" in vp_lower
    user_scalable_blocked = "user-scalable=no" in vp_lower or "maximum-scale=1" in vp_lower

    if not has_viewport:
        issues.append("Missing <meta name=\"viewport\"> — page will render at desktop width on mobile")
    else:
        if not width_ok:
            issues.append("Viewport meta is missing width=device-width")
        if not scale_ok:
            issues.append("Viewport meta is missing initial-scale=1")
        if user_scalable_blocked:
            issues.append("Viewport blocks pinch-zoom (accessibility issue)")

    # Cheap signals from inline styles + style tags
    inline_styles = " ".join(s.get_text(" ", strip=True) for s in soup.find_all("style"))
    style_attrs = " ".join((t.get("style") or "") for t in soup.find_all(style=True))
    style_blob = (inline_styles + " " + style_attrs).lower()

    has_media_query = "@media" in style_blob or '@media' in raw_html.lower()
    if not has_media_query:
        issues.append("No @media queries found in inline CSS (page may not be responsive)")

    # Font-size: any obviously tiny declarations (<10px)
    tiny_fonts = re.findall(r"font-size\s*:\s*(\d+(?:\.\d+)?)\s*(px|pt)", style_blob)
    too_small = [f"{v}{u}" for v, u in tiny_fonts if (u == "px" and float(v) < 12) or (u == "pt" and float(v) < 9)]
    if too_small:
        issues.append(f"Inline CSS contains small font-sizes ({', '.join(sorted(set(too_small))[:5])}) — risk of unreadable text on mobile")

    # AMP / framework hints (informational)
    amp = soup.find("html", attrs={"amp": True}) or soup.find("html", attrs={"⚡": True})

    return {
        "has_viewport_meta": has_viewport,
        "viewport_content": vp_content,
        "viewport_width_ok": width_ok,
        "viewport_initial_scale_ok": scale_ok,
        "viewport_blocks_zoom": user_scalable_blocked,
        "has_media_queries_inline": has_media_query,
        "small_font_sizes_in_inline_css": too_small[:10],
        "is_amp": bool(amp),
        "issues": issues,
    }
