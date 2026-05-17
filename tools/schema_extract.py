"""Structured data extractor (JSON-LD / microdata / RDFa) using extruct."""
from __future__ import annotations

from typing import Dict
import requests
import extruct
from w3lib.html import get_base_url
from langchain_core.tools import tool

from app.config import USER_AGENT, REQUEST_TIMEOUT


@tool
def extract_structured_data(url: str) -> Dict[str, object]:
    """Extract Schema.org structured data (JSON-LD, microdata, RDFa, OpenGraph).

    Returns the parsed structured data and a quick coverage summary.
    Use this to confirm a page exposes the right Article/Product/Organization/
    BreadcrumbList/FAQPage schema, and to spot validation gaps.
    """
    try:
        r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT)
        base_url = get_base_url(r.text, r.url)
        data = extruct.extract(
            r.text,
            base_url=base_url,
            syntaxes=["json-ld", "microdata", "rdfa", "opengraph"],
            uniform=True,
        )
    except Exception as e:
        return {"ok": False, "url": url, "error": str(e)}

    types_found = []
    for entry in data.get("json-ld", []):
        t = entry.get("@type")
        if isinstance(t, list):
            types_found.extend(t)
        elif t:
            types_found.append(t)

    return {
        "ok": True,
        "url": r.url,
        "json_ld": data.get("json-ld", []),
        "microdata": data.get("microdata", []),
        "rdfa": data.get("rdfa", []),
        "opengraph": data.get("opengraph", []),
        "json_ld_types": list(dict.fromkeys(types_found)),
        "summary": {
            "json_ld_blocks": len(data.get("json-ld", [])),
            "microdata_blocks": len(data.get("microdata", [])),
            "rdfa_blocks": len(data.get("rdfa", [])),
            "opengraph_blocks": len(data.get("opengraph", [])),
        },
    }
