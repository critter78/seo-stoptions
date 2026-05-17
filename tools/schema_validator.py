"""Schema.org structured-data validator.

Two tools live here:
  • `validate_schema_org`  — local validator. Fetches the page, extracts
    JSON-LD with extruct, and runs each block against hand-curated Schema.org
    type rules + Google rich-result requirements. Fast, no API, deterministic.
  • `validate_schema_remote` — hits the official Schema.org validator
    (validator.schema.org) for an authoritative second opinion. No API key.

Use both: local catches rich-result gating issues fast; remote gives the
canonical schema.org parse + any extra warnings their validator emits.
"""
from __future__ import annotations

import json
from typing import Dict, List, Optional

import requests
import extruct
from w3lib.html import get_base_url
from langchain_core.tools import tool

from app.config import USER_AGENT, REQUEST_TIMEOUT


# Required + recommended properties for common SEO-relevant Schema.org types.
# Required = Google rich-results requirements; recommended = best practice.
SCHEMA_RULES = {
    "Article": {
        "required": ["headline", "author"],
        "recommended": ["datePublished", "dateModified", "image", "publisher",
                        "mainEntityOfPage", "articleBody"],
    },
    "NewsArticle": {
        "required": ["headline", "author", "datePublished", "image"],
        "recommended": ["dateModified", "publisher"],
    },
    "BlogPosting": {
        "required": ["headline", "author"],
        "recommended": ["datePublished", "dateModified", "image", "publisher"],
    },
    "Product": {
        "required": ["name"],
        "recommended": ["image", "description", "brand", "offers", "aggregateRating", "review", "sku"],
    },
    "Organization": {
        "required": ["name"],
        "recommended": ["url", "logo", "sameAs", "contactPoint", "address"],
    },
    "LocalBusiness": {
        "required": ["name", "address"],
        "recommended": ["telephone", "openingHours", "geo", "priceRange",
                        "aggregateRating", "image"],
    },
    "Person": {
        "required": ["name"],
        "recommended": ["url", "image", "jobTitle", "worksFor", "sameAs"],
    },
    "FAQPage": {
        "required": ["mainEntity"],
        "recommended": [],
    },
    "Question": {
        "required": ["name", "acceptedAnswer"],
        "recommended": [],
    },
    "HowTo": {
        "required": ["name", "step"],
        "recommended": ["image", "totalTime", "estimatedCost", "supply", "tool"],
    },
    "BreadcrumbList": {
        "required": ["itemListElement"],
        "recommended": [],
    },
    "WebSite": {
        "required": ["name", "url"],
        "recommended": ["potentialAction"],  # SearchAction for sitelinks searchbox
    },
    "WebPage": {
        "required": [],
        "recommended": ["name", "url", "description", "primaryImageOfPage"],
    },
    "Recipe": {
        "required": ["name", "image", "recipeIngredient", "recipeInstructions"],
        "recommended": ["author", "datePublished", "description", "prepTime", "cookTime",
                        "totalTime", "nutrition", "recipeYield", "aggregateRating"],
    },
    "Event": {
        "required": ["name", "startDate", "location"],
        "recommended": ["endDate", "image", "description", "offers", "performer", "organizer"],
    },
    "VideoObject": {
        "required": ["name", "description", "thumbnailUrl", "uploadDate"],
        "recommended": ["duration", "contentUrl", "embedUrl", "publisher"],
    },
    "Review": {
        "required": ["itemReviewed", "reviewRating", "author"],
        "recommended": ["datePublished", "reviewBody"],
    },
    "AggregateRating": {
        "required": ["ratingValue", "reviewCount"],
        "recommended": ["bestRating", "worstRating"],
    },
    "Course": {
        "required": ["name", "description", "provider"],
        "recommended": ["url", "image"],
    },
    "JobPosting": {
        "required": ["title", "description", "datePosted", "hiringOrganization",
                     "jobLocation"],
        "recommended": ["validThrough", "employmentType", "baseSalary"],
    },
    "SoftwareApplication": {
        "required": ["name", "applicationCategory", "operatingSystem"],
        "recommended": ["aggregateRating", "offers", "screenshot"],
    },
    "Service": {
        "required": ["name"],
        "recommended": ["description", "provider", "areaServed", "serviceType"],
    },
}


def _types_of(block: dict) -> List[str]:
    t = block.get("@type")
    if isinstance(t, list):
        return [x for x in t if isinstance(x, str)]
    if isinstance(t, str):
        return [t]
    return []


def _has_property(block: dict, prop: str) -> bool:
    if prop not in block:
        return False
    v = block[prop]
    if v is None:
        return False
    if isinstance(v, (list, dict, str)):
        return bool(v)
    return True


def _validate_block(block: dict) -> dict:
    issues: List[str] = []
    warnings: List[str] = []
    types = _types_of(block)
    if not types:
        return {"types": [], "valid": False, "issues": ["No @type set"],
                "warnings": [], "checked": False}
    ctx = block.get("@context", "")
    if isinstance(ctx, list):
        ctx = " ".join(str(c) for c in ctx)
    if "schema.org" not in str(ctx).lower():
        warnings.append('@context should reference schema.org (e.g. "https://schema.org")')

    checked = False
    for t in types:
        rules = SCHEMA_RULES.get(t)
        if not rules:
            continue
        checked = True
        for req in rules["required"]:
            if not _has_property(block, req):
                issues.append(f"{t}: missing required property '{req}'")
        for rec in rules["recommended"]:
            if not _has_property(block, rec):
                warnings.append(f"{t}: missing recommended property '{rec}'")

    return {
        "types": types,
        "valid": len(issues) == 0,
        "issues": issues,
        "warnings": warnings,
        "checked": checked,
        "checked_against": [t for t in types if t in SCHEMA_RULES],
    }


@tool
def validate_schema_org(url: str) -> Dict[str, object]:
    """Validate Schema.org structured data (JSON-LD) on a URL.

    Fetches the page, extracts every JSON-LD block, and validates each one
    against Schema.org type definitions. For each @type detected, checks:
      - required properties (Google rich-result requirements)
      - recommended properties (improves eligibility for rich results)
      - @context references schema.org

    Returns a per-block report plus an overall pass/fail and a summary count.
    Use this whenever a page should be eligible for rich results
    (Article, Product, FAQ, HowTo, Breadcrumb, Event, Recipe, etc.).

    Note: This is a structural validator, not Google's official Rich Results
    Test. It will catch missing-required-property issues that block rich
    results, plus best-practice gaps.
    """
    try:
        r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT)
        base_url = get_base_url(r.text, r.url)
        data = extruct.extract(
            r.text, base_url=base_url,
            syntaxes=["json-ld", "microdata", "rdfa"],
            uniform=True,
        )
    except Exception as e:
        return {"ok": False, "url": url, "error": str(e)}

    json_ld = data.get("json-ld", []) or []
    microdata = data.get("microdata", []) or []
    rdfa = data.get("rdfa", []) or []

    # Flatten + validate JSON-LD (the format Google explicitly recommends)
    def _flatten(blocks):
        out = []
        for b in blocks:
            if isinstance(b, dict):
                out.append(b)
                graph = b.get("@graph")
                if isinstance(graph, list):
                    out.extend([g for g in graph if isinstance(g, dict)])
        return out

    flat_json_ld = _flatten(json_ld)

    per_block = []
    type_counts: dict = {}
    total_issues = 0
    total_warnings = 0
    for b in flat_json_ld:
        v = _validate_block(b)
        per_block.append(v)
        for t in v["types"]:
            type_counts[t] = type_counts.get(t, 0) + 1
        total_issues += len(v["issues"])
        total_warnings += len(v["warnings"])

    return {
        "ok": True,
        "url": r.url,
        "json_ld_blocks": len(flat_json_ld),
        "microdata_blocks": len(microdata),
        "rdfa_blocks": len(rdfa),
        "types_found": type_counts,
        "total_issues": total_issues,
        "total_warnings": total_warnings,
        "overall_valid": total_issues == 0,
        "per_block": per_block,
        "note": (
            "Local validator using Schema.org type rules + Google rich-result "
            "requirements. For the definitive check, also run "
            "https://search.google.com/test/rich-results"
        ),
    }


# =============================================================================
# Remote validator — calls the official Schema.org Validator
# =============================================================================
#
# Schema.org runs a free validator at https://validator.schema.org/ that the
# org co-maintains with Google. Their UI calls an internal `/validate` endpoint
# which accepts URL or pasted code and returns parsed nodes + errors as JSON
# (with the XSSI prefix `)]}'`). No API key, no rate-limit docs, but they
# expect non-abusive use — we set a UA and don't retry on failures.

_VALIDATOR_ENDPOINT = "https://validator.schema.org/validate"
_XSSI_PREFIX = ")]}'\n"


def _strip_xssi(text: str) -> str:
    """Schema.org wraps JSON responses with `)]}'\\n` to prevent XSSI attacks.
    Strip it before json-decoding."""
    if text.startswith(_XSSI_PREFIX):
        return text[len(_XSSI_PREFIX):]
    # Some responses use just `)]}'` without newline
    if text.startswith(")]}'"):
        return text[4:].lstrip()
    return text


def _normalise_remote_response(raw: dict) -> dict:
    """Reshape validator.schema.org's response into something agent-friendly.

    Their response is roughly:
      {
        "tripleGroups": [ {"nodes": [...], "errors": [...]} ],
        "errors": [...],
        "totalNumNodes": N,
        ...
      }
    Each node has `type` + `properties: [{pred, value}, ...]`.
    """
    triple_groups = raw.get("tripleGroups") or []
    top_errors = raw.get("errors") or []

    nodes = []
    block_errors = []
    type_counts: Dict[str, int] = {}

    for group in triple_groups:
        for node in group.get("nodes", []) or []:
            node_type = node.get("type") or node.get("typeGroup") or "(unknown)"
            type_counts[node_type] = type_counts.get(node_type, 0) + 1
            props = []
            for prop in node.get("properties", []) or []:
                pred = prop.get("pred")
                val = prop.get("value")
                if isinstance(val, dict):
                    val = val.get("value") or val.get("name") or str(val)[:80]
                if isinstance(val, list):
                    val = ", ".join(str(x)[:60] for x in val[:5])
                props.append({"property": pred, "value": str(val)[:200]})
            nodes.append({"type": node_type, "properties": props})
        for err in group.get("errors", []) or []:
            block_errors.append(err if isinstance(err, str) else json.dumps(err))

    all_errors = [e if isinstance(e, str) else json.dumps(e) for e in top_errors]
    all_errors.extend(block_errors)

    return {
        "nodes": nodes,
        "types_found": type_counts,
        "errors": all_errors,
        "num_nodes": len(nodes),
        "num_errors": len(all_errors),
    }


@tool
def validate_schema_remote(
    url: Optional[str] = None,
    code: Optional[str] = None,
) -> Dict[str, object]:
    """Validate schema.org markup against the OFFICIAL validator at validator.schema.org.

    Provide one of:
      - url: a public page to fetch + validate (e.g. https://stoptions.ai/)
      - code: a pasted JSON-LD / microdata / RDFa snippet to validate directly

    No API key required. Returns parsed nodes + per-node properties + any
    schema.org-side errors or warnings. This is the authoritative check that
    complements `validate_schema_org` (the local rich-result rule check).

    Use this when you want a definitive answer on whether schema.org itself
    accepts the markup, regardless of Google's rich-result eligibility.
    """
    if not url and not code:
        return {"ok": False, "error": "Pass either `url` or `code`."}
    if url and code:
        return {"ok": False, "error": "Pass only one of `url` or `code`, not both."}

    payload = {"url": url} if url else {"code": code}
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json, text/plain, */*",
    }

    try:
        r = requests.post(
            _VALIDATOR_ENDPOINT,
            data=payload,
            headers=headers,
            timeout=REQUEST_TIMEOUT,
        )
    except requests.RequestException as e:
        return {"ok": False, "error": f"Network error contacting validator.schema.org: {e}"}

    if r.status_code != 200:
        return {
            "ok": False,
            "error": f"validator.schema.org returned HTTP {r.status_code}",
            "body_preview": r.text[:300],
        }

    try:
        body = _strip_xssi(r.text)
        raw = json.loads(body)
    except (ValueError, json.JSONDecodeError) as e:
        return {
            "ok": False,
            "error": f"Could not parse validator.schema.org response: {e}",
            "body_preview": r.text[:300],
        }

    parsed = _normalise_remote_response(raw)

    return {
        "ok": True,
        "validator": "validator.schema.org",
        "url": url,
        "input_mode": "url" if url else "code",
        "num_nodes": parsed["num_nodes"],
        "num_errors": parsed["num_errors"],
        "overall_valid": parsed["num_errors"] == 0,
        "types_found": parsed["types_found"],
        "nodes": parsed["nodes"],
        "errors": parsed["errors"],
        "deep_link": (
            f"https://validator.schema.org/#url={requests.utils.quote(url, safe='')}"
            if url else "https://validator.schema.org/"
        ),
        "note": (
            "Authoritative parse from validator.schema.org (no API key). "
            "Complement with `validate_schema_org` for Google rich-result "
            "gating + with https://search.google.com/test/rich-results for "
            "Google's own check."
        ),
    }
