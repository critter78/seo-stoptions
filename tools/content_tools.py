"""Content-focused SEO tools for Kira + Maya.

These complement the existing audit tools by giving the agents structured
ways to plan + compare + score content quality.
"""
from __future__ import annotations

import re
from collections import Counter
from typing import Dict, List
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from langchain_core.tools import tool

from app.config import REQUEST_TIMEOUT, USER_AGENT
from app.db import add_content_item, list_content
from tools._text_analysis import keyword_density, n_grams, tokenize


def _fetch(url: str):
    return requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT)


def _visible_text(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for t in soup(["script", "style", "noscript", "nav", "header", "footer", "aside"]):
        t.decompose()
    return " ".join(soup.get_text(separator=" ", strip=True).split())


# ============================================================================
@tool
def competitor_content_compare(
    our_url: str,
    competitor_url: str,
    target_keyword: str = "",
) -> Dict[str, object]:
    """Side-by-side content comparison between our page and a competitor's.

    Compares: word count, heading depth (H1/H2/H3 counts + actual H2s), keyword
    density on the target keyword, internal/external link counts, schema types,
    image counts. Returns a structured diff with concrete recommendations.

    Use this when planning to upgrade a page that's losing to a competitor for a
    specific keyword — Kira runs this, Cash decides what to change.
    """
    out = {"ok": True, "our_url": our_url, "competitor_url": competitor_url,
           "target_keyword": target_keyword, "comparison": {}, "recommendations": []}
    try:
        ours = _fetch(our_url)
        theirs = _fetch(competitor_url)
    except Exception as e:
        return {"ok": False, "error": str(e)}

    def _profile(html: str) -> dict:
        soup = BeautifulSoup(html, "lxml")
        title = (soup.title.string.strip() if soup.title and soup.title.string else "")
        h1 = [h.get_text(strip=True) for h in soup.find_all("h1")]
        h2 = [h.get_text(strip=True) for h in soup.find_all("h2")]
        h3 = [h.get_text(strip=True) for h in soup.find_all("h3")]
        text = _visible_text(html)
        wc = len(text.split())
        # Links
        links = soup.find_all("a", href=True)
        internal_count = sum(1 for a in links if a["href"].startswith(("/", "#")))
        external_count = sum(1 for a in links if a["href"].startswith(("http://", "https://")))
        # Images
        imgs = soup.find_all("img")
        # Schema
        ld_blocks = soup.find_all("script", type="application/ld+json")
        schema_types = []
        for s in ld_blocks:
            try:
                import json as _j
                data = _j.loads(s.string or "")
                if isinstance(data, dict):
                    t = data.get("@type")
                    if isinstance(t, list):
                        schema_types.extend(t)
                    elif t:
                        schema_types.append(t)
            except Exception:
                pass
        kw = keyword_density(text, target_keyword=target_keyword, top_k=10)
        return {
            "title": title, "word_count": wc,
            "h1_count": len(h1), "h2_count": len(h2), "h3_count": len(h3),
            "h2_topics": h2[:20],
            "internal_links": internal_count, "external_links": external_count,
            "image_count": len(imgs),
            "schema_types": list(dict.fromkeys(schema_types)),
            "target_kw_density_pct": kw.get("target_keyword_density_pct"),
            "top_bigrams": [b[0] for b in kw.get("top_bigrams", [])[:10]],
        }

    ours_p = _profile(ours.text)
    theirs_p = _profile(theirs.text)
    out["comparison"] = {"ours": ours_p, "theirs": theirs_p}

    recs = []
    if theirs_p["word_count"] > ours_p["word_count"] * 1.2:
        recs.append(
            f"Add depth — competitor is {theirs_p['word_count']} words vs ours "
            f"{ours_p['word_count']}. Aim for {theirs_p['word_count'] + 200}+."
        )
    missing_h2 = [t for t in theirs_p["h2_topics"] if t and t not in ours_p["h2_topics"]]
    if missing_h2:
        recs.append(
            f"Add H2 sections we're missing: {', '.join(missing_h2[:5])}"
            + (f" (+{len(missing_h2)-5} more)" if len(missing_h2) > 5 else "")
        )
    missing_schema = set(theirs_p["schema_types"]) - set(ours_p["schema_types"])
    if missing_schema:
        recs.append(f"Add schema types we don't have: {', '.join(missing_schema)}")
    if target_keyword:
        td, td2 = ours_p["target_kw_density_pct"], theirs_p["target_kw_density_pct"]
        if td2 and (td or 0) < td2 * 0.5:
            recs.append(f"Increase target keyword density (ours {td}% vs theirs {td2}%)")
    if theirs_p["image_count"] > ours_p["image_count"] + 3:
        recs.append(
            f"Add more imagery — they have {theirs_p['image_count']} images, "
            f"we have {ours_p['image_count']}."
        )

    out["recommendations"] = recs
    return out


# ============================================================================
@tool
def content_gap_analysis(
    keyword: str,
    our_domain: str = "stoptions.ai",
    top_n: int = 5,
) -> Dict[str, object]:
    """Identify content gaps by analysing the top organic results for a keyword.

    For the keyword: searches SERP, profiles top N competing pages, extracts the
    most-common H2 topics and bigrams. Returns a list of topics our domain probably
    needs to cover for ranking-relevance, plus competitor URLs for reference.

    Pair with competitor_content_compare for deep dives on specific URLs.
    """
    try:
        from .web_search import duckduckgo_search
    except ImportError:
        from tools.web_search import duckduckgo_search
    results = duckduckgo_search.invoke({"query": keyword, "max_results": max(top_n + 2, 8)})
    competitors = [
        r for r in results
        if r.get("href") and our_domain not in urlparse(r["href"]).netloc.lower()
    ][:top_n]

    common_h2: Counter = Counter()
    common_bigrams: Counter = Counter()
    profiles = []
    for r in competitors:
        try:
            resp = _fetch(r["href"])
            soup = BeautifulSoup(resp.text, "lxml")
            h2s = [h.get_text(strip=True) for h in soup.find_all("h2")]
            text = _visible_text(resp.text)
            tokens = tokenize(text)
            bigrams = n_grams(tokens, 2)
            common_h2.update(h2s)
            common_bigrams.update(bigrams)
            profiles.append({"url": r["href"], "h2_count": len(h2s),
                              "word_count": len(text.split())})
        except Exception as e:
            profiles.append({"url": r["href"], "error": str(e)})

    # Topics that appear in 2+ competitors are real signals
    must_cover = [t for t, c in common_h2.most_common(25) if c >= 2 and len(t) > 4]
    nice_to_have = [t for t, c in common_h2.most_common(50) if c == 1 and len(t) > 4][:15]
    semantic_terms = [b for b, _ in common_bigrams.most_common(20)]

    return {
        "ok": True,
        "keyword": keyword,
        "competitors_analysed": len(competitors),
        "must_cover_topics": must_cover[:15],
        "nice_to_have_topics": nice_to_have,
        "semantic_terms_to_include": semantic_terms,
        "competitor_profiles": profiles,
        "recommendation": (
            f"Cover the {len(must_cover[:15])} must-have topics (appear in 2+ "
            f"top-ranking pages) and weave in the semantic terms for relevance."
        ),
    }


# ============================================================================
@tool
def eeat_audit(url: str) -> Dict[str, object]:
    """E-E-A-T (Experience, Expertise, Authoritativeness, Trustworthiness) audit.

    Checks for the signals Google's quality raters look for:
      - Author byline + bio + credentials
      - Publication date + last updated
      - Author / Organization JSON-LD schema
      - Citations / external references
      - Contact / about / privacy pages on the site
      - HTTPS
      - Disclosure of conflicts (paid promotion, affiliations)

    Returns per-signal pass/fail + an overall score + actionable fixes.
    """
    try:
        r = _fetch(url)
        soup = BeautifulSoup(r.text, "lxml")
        host = urlparse(r.url).netloc
    except Exception as e:
        return {"ok": False, "url": url, "error": str(e)}

    signals = {}
    issues = []

    # HTTPS
    signals["https"] = r.url.startswith("https://")
    if not signals["https"]:
        issues.append("Page not served over HTTPS — basic trust signal missing")

    # Author byline
    author_meta = soup.find("meta", attrs={"name": "author"})
    author_rel = soup.find(attrs={"rel": "author"})
    author_class = soup.find(attrs={"class": re.compile(r"author|byline", re.I)})
    signals["author_byline"] = bool(author_meta or author_rel or author_class)
    if not signals["author_byline"]:
        issues.append("No visible author byline — add a named author with link to bio")

    # Dates
    has_published = bool(
        soup.find("meta", attrs={"property": "article:published_time"}) or
        soup.find("time", attrs={"datetime": True})
    )
    has_modified = bool(soup.find("meta", attrs={"property": "article:modified_time"}))
    signals["date_published"] = has_published
    signals["date_modified"] = has_modified
    if not has_published:
        issues.append("Missing article:published_time meta or <time> element")
    if not has_modified:
        issues.append("Missing article:modified_time — add to show freshness")

    # JSON-LD with Author + Organization
    has_person, has_org = False, False
    for s in soup.find_all("script", type="application/ld+json"):
        try:
            import json as _j
            data = _j.loads(s.string or "")
            for block in (data if isinstance(data, list) else [data]):
                if not isinstance(block, dict):
                    continue
                t = block.get("@type")
                ts = t if isinstance(t, list) else [t]
                if "Person" in ts:
                    has_person = True
                if "Organization" in ts:
                    has_org = True
                author = block.get("author")
                if isinstance(author, dict) and author.get("@type") == "Person":
                    has_person = True
                pub = block.get("publisher")
                if isinstance(pub, dict) and pub.get("@type") == "Organization":
                    has_org = True
        except Exception:
            pass
    signals["jsonld_person_schema"] = has_person
    signals["jsonld_organization_schema"] = has_org
    if not has_person:
        issues.append("Add Person/author JSON-LD schema (name, jobTitle, sameAs)")
    if not has_org:
        issues.append("Add Organization JSON-LD schema (name, logo, sameAs)")

    # External citations (links to authority domains)
    external_links = [
        a["href"] for a in soup.find_all("a", href=True)
        if a["href"].startswith(("http://", "https://"))
        and urlparse(a["href"]).netloc.lower().lstrip("www.") != host.lstrip("www.")
    ]
    signals["external_citations_count"] = len(external_links)
    if len(external_links) < 3:
        issues.append(
            f"Only {len(external_links)} external citations — add 3+ links to "
            "authoritative sources (.gov, .edu, recognised publications)"
        )

    # About / contact / privacy pages
    nav_links = [a.get("href", "").lower() for a in soup.find_all("a", href=True)]
    nav_text = " ".join(nav_links)
    signals["has_about_link"] = "about" in nav_text
    signals["has_contact_link"] = "contact" in nav_text
    signals["has_privacy_link"] = "privacy" in nav_text
    for label, key in [("About", "has_about_link"), ("Contact", "has_contact_link"),
                        ("Privacy policy", "has_privacy_link")]:
        if not signals[key]:
            issues.append(f"Missing site-wide {label} link — important trust signal")

    # Score: 1 point per passing signal, normalised to 100
    pass_signals = [k for k, v in signals.items() if isinstance(v, bool) and v]
    bool_signals = [k for k, v in signals.items() if isinstance(v, bool)]
    score = round(100 * len(pass_signals) / max(len(bool_signals), 1))
    # Bonus for citations
    if signals["external_citations_count"] >= 5:
        score = min(100, score + 5)

    return {
        "ok": True,
        "url": r.url,
        "eeat_score": score,
        "signals": signals,
        "issues": issues,
    }


# ============================================================================
@tool
def topic_cluster_planner(
    seed_keyword: str,
    pillar_url: str = "",
    cluster_size: int = 8,
) -> Dict[str, object]:
    """Generate a topic cluster (pillar + spoke pages) for a seed keyword.

    Returns the proposed cluster: 1 pillar topic + N spoke topics, each with
    suggested target keywords + content type + word-count target. Use to plan
    out a hub-and-spoke architecture instead of one-off blog posts.

    The 'real-world signal' comes from a SERP query for the seed keyword + 'guide'
    and 'how to' modifiers, plus an n-gram analysis of related top results.
    """
    try:
        from .web_search import duckduckgo_search
    except ImportError:
        from tools.web_search import duckduckgo_search

    cluster_size = max(3, min(int(cluster_size), 15))
    modifiers = ["how to", "what is", "best", "vs", "guide", "examples", "for beginners"]
    seeds = [seed_keyword] + [f"{seed_keyword} {m}" for m in modifiers]
    topic_signals = Counter()
    sample_urls: List[str] = []

    for q in seeds[:6]:  # cap searches
        try:
            for r in duckduckgo_search.invoke({"query": q, "max_results": 5}):
                title = (r.get("title") or "").lower()
                snippet = (r.get("body") or "").lower()
                # Pull bigrams + trigrams from titles + snippets
                tokens = tokenize(title + " " + snippet)
                topic_signals.update(n_grams(tokens, 2))
                topic_signals.update(n_grams(tokens, 3))
                if r.get("href") and len(sample_urls) < 10:
                    sample_urls.append(r["href"])
        except Exception:
            continue

    # Filter signals to those containing seed terms (or close)
    seed_tokens = set(tokenize(seed_keyword))
    relevant = [
        (term, count) for term, count in topic_signals.most_common(50)
        if any(t in term for t in seed_tokens) and count >= 2
    ]
    if len(relevant) < cluster_size:
        relevant = topic_signals.most_common(cluster_size * 2)

    spokes = []
    seen = set()
    for term, _ in relevant:
        if term in seen or term == seed_keyword.lower():
            continue
        seen.add(term)
        spokes.append({
            "topic": term,
            "target_keyword": term,
            "content_type": "blog" if any(m in term for m in ["how", "guide", "what"]) else "comparison",
            "word_count_target": 1500 if "guide" in term else 1000,
        })
        if len(spokes) >= cluster_size:
            break

    return {
        "ok": True,
        "seed_keyword": seed_keyword,
        "pillar": {
            "topic": seed_keyword,
            "content_type": "pillar",
            "word_count_target": 3500,
            "target_url": pillar_url or f"https://stoptions.ai/guides/{seed_keyword.replace(' ', '-')}",
        },
        "spokes": spokes,
        "reference_serps": sample_urls[:10],
        "next_step": (
            "Pillar covers the seed keyword broadly; each spoke targets a long-tail "
            "modifier. Each spoke links UP to pillar; pillar links DOWN to all spokes. "
            "Save the chosen pillar + spokes to the Content Calendar to track delivery."
        ),
    }


# ============================================================================
@tool
def internal_link_suggestions(target_url: str, sitemap_url: str = "") -> Dict[str, object]:
    """Find pages on the site that should link to target_url but don't yet.

    Walks the sitemap, fetches each page, checks if it mentions any of target_url's
    target keywords (extracted from the target page's title + H1 + H2s) AND doesn't
    already link to target_url. Returns prioritised list of source pages to add
    internal links from.

    Limited to ~50 sitemap URLs to keep it fast.
    """
    try:
        target_resp = _fetch(target_url)
        target_soup = BeautifulSoup(target_resp.text, "lxml")
        target_title = (target_soup.title.string.strip()
                        if target_soup.title and target_soup.title.string else "")
        target_h1 = " ".join(h.get_text(strip=True) for h in target_soup.find_all("h1"))
        target_h2s = " ".join(h.get_text(strip=True) for h in target_soup.find_all("h2"))
        anchor_terms = set(tokenize(target_title + " " + target_h1 + " " + target_h2s))
        # Filter stopwordsy single tokens by keeping only multi-char meaningful ones
        anchor_terms = {t for t in anchor_terms if len(t) > 4}
    except Exception as e:
        return {"ok": False, "error": f"Could not fetch target page: {e}"}

    # Get sitemap URLs
    if not sitemap_url:
        parsed = urlparse(target_url)
        sitemap_url = f"{parsed.scheme}://{parsed.netloc}/sitemap.xml"
    try:
        from .sitemap_robots import fetch_sitemap_urls
    except ImportError:
        from tools.sitemap_robots import fetch_sitemap_urls
    sm_resp = fetch_sitemap_urls.invoke({"sitemap_url": sitemap_url, "max_urls": 50})
    if not sm_resp.get("ok"):
        return {"ok": False, "error": f"Sitemap fetch failed: {sm_resp.get('error')}"}
    candidates = [u for u in sm_resp["urls"] if u != target_url]

    target_path = urlparse(target_url).path
    suggestions = []
    for url in candidates[:50]:
        try:
            resp = _fetch(url)
            html = resp.text
            soup = BeautifulSoup(html, "lxml")
            # Already linking?
            already = any(target_url in (a.get("href") or "") or target_path in (a.get("href") or "")
                          for a in soup.find_all("a", href=True))
            if already:
                continue
            text = _visible_text(html).lower()
            tokens = set(tokenize(text))
            overlap = anchor_terms & tokens
            if len(overlap) >= 3:  # at least 3 anchor terms appear
                suggestions.append({
                    "source_url": url,
                    "overlap_terms": sorted(overlap)[:10],
                    "overlap_score": len(overlap),
                    "suggested_anchor": target_title[:60],
                })
        except Exception:
            continue

    suggestions.sort(key=lambda s: s["overlap_score"], reverse=True)
    return {
        "ok": True,
        "target_url": target_url,
        "target_title": target_title,
        "anchor_terms_used": sorted(anchor_terms)[:15],
        "candidates_scanned": min(len(candidates), 50),
        "suggestions": suggestions[:20],
    }


# ============================================================================
@tool
def content_calendar_add(
    title: str,
    target_keyword: str = "",
    intent: str = "informational",
    content_type: str = "blog",
    owner: str = "",
    due_date: str = "",
    target_url: str = "",
    word_count: int = 0,
    outline: str = "",
) -> Dict[str, object]:
    """Add a new content piece to the editorial calendar (SQLite-backed).

    intent: informational | commercial | navigational | transactional
    content_type: blog | landing | guide | tool | comparison | listicle
    status starts at 'idea'. Use the 📝 Content page to move through the workflow.
    """
    cid = add_content_item(
        title=title, target_keyword=target_keyword, intent=intent,
        content_type=content_type, owner=owner, due_date=due_date,
        target_url=target_url, word_count=word_count, outline=outline,
    )
    return {"ok": True, "id": cid, "title": title, "status": "idea"}


@tool
def content_calendar_list(status: str = "") -> Dict[str, object]:
    """List content items in the editorial calendar.

    status: idea | brief | drafting | review | scheduled | published | archived
    Leave blank to list everything.
    """
    items = list_content(status=status)
    return {"ok": True, "count": len(items), "items": items}
