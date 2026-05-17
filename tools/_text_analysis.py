"""Lightweight, dependency-free text analysis helpers used by onpage_audit.

We deliberately avoid NLTK / spaCy so the container stays small. The stopword
list is the standard English Snowball set plus a small SEO-noise list.
"""
from __future__ import annotations

import re
from collections import Counter
from typing import Dict, List, Tuple


STOPWORDS = set("""
a about above after again against all am an and any are as at be because been before being below
between both but by could did do does doing down during each few for from further had has have having
he her here hers herself him himself his how i if in into is it its itself just me more most my
myself no nor not now of off on once only or other our ours ourselves out over own same she should
so some such than that the their theirs them themselves then there these they this those through to
too under until up very was we were what when where which while who whom why will with would you
your yours yourself yourselves
""".split())

SEO_STOP_EXTRAS = {
    "click", "read", "more", "page", "site", "website", "home", "menu", "skip", "main",
    "navigation", "subscribe", "newsletter", "copyright", "rights", "reserved",
}
STOPWORDS |= SEO_STOP_EXTRAS

WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9'\-]+")


def tokenize(text: str) -> List[str]:
    return [w.lower() for w in WORD_RE.findall(text or "")]


def n_grams(tokens: List[str], n: int) -> List[str]:
    if n <= 0:
        return []
    out = []
    for i in range(len(tokens) - n + 1):
        chunk = tokens[i : i + n]
        if any(t in STOPWORDS for t in chunk):
            continue
        if all(len(t) > 1 for t in chunk):
            out.append(" ".join(chunk))
    return out


def keyword_density(text: str, target_keyword: str = "", top_k: int = 15) -> Dict:
    """Return density % of `target_keyword` plus the top unigram/bigram/trigram terms."""
    tokens = tokenize(text)
    total = len(tokens) or 1
    cleaned = [t for t in tokens if t not in STOPWORDS and len(t) > 2]

    target = (target_keyword or "").strip().lower()
    target_tokens = tokenize(target)
    target_count = 0
    if target_tokens:
        n = len(target_tokens)
        joined = " ".join(tokens)
        # naive but accurate count of multi-word target
        target_count = len(re.findall(r"\b" + re.escape(" ".join(target_tokens)) + r"\b", joined))

    target_density_pct = round((target_count * len(target_tokens) / total) * 100, 2) if target_tokens else 0.0

    return {
        "total_tokens": total,
        "target_keyword": target_keyword or None,
        "target_keyword_count": target_count if target_tokens else None,
        "target_keyword_density_pct": target_density_pct if target_tokens else None,
        "top_unigrams": Counter(cleaned).most_common(top_k),
        "top_bigrams": Counter(n_grams(tokens, 2)).most_common(top_k),
        "top_trigrams": Counter(n_grams(tokens, 3)).most_common(top_k),
    }
