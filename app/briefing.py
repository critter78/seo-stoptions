"""Morning Briefing helpers — parse Daily Health Check reports + compute deltas."""
from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from app.db import history_for, list_keywords

REPORTS_DIR = Path(__file__).resolve().parent.parent / "reports"

HEALTH_SCORE_RE = re.compile(r"Health\s*Score[:\s]+(\d{1,3})\s*/\s*100", re.IGNORECASE)
TOP_ACTION_RE = re.compile(r"(?:one thing to do today|top action today|today.{0,8}fix)[:\s]+(.+?)(?:\n|$)", re.IGNORECASE)


_MIN_REPORT_BYTES = 500   # ignore stubs / blank placeholders


def _active_project_slug() -> Optional[str]:
    """Best-effort active-project slug. Returns None for legacy / no-DB callers."""
    try:
        from app.db import active_project
        proj = active_project()
        return (proj or {}).get("slug")
    except Exception:
        return None


def project_reports_dir(slug: Optional[str] = None) -> Path:
    """Per-project report directory. Falls back to the legacy flat dir."""
    s = slug or _active_project_slug()
    base = REPORTS_DIR / s if s else REPORTS_DIR
    base.mkdir(parents=True, exist_ok=True)
    return base


def reports_for(slug_substring: str) -> List[Path]:
    """All reports whose filename contains the given slug, newest first.

    Globs both the active-project subfolder AND the legacy flat /reports
    folder, so older single-project installs keep showing up after the
    Sprint 5 multi-project migration. Excludes empty / stub files
    (< 500 bytes) so test fixtures don't poison the Morning Briefing.
    """
    REPORTS_DIR.mkdir(exist_ok=True)
    project_dir = project_reports_dir()
    # Combine project-scoped and legacy flat reports
    candidates: List[Path] = []
    candidates.extend(project_dir.glob("*.md"))
    if project_dir != REPORTS_DIR:
        candidates.extend(REPORTS_DIR.glob("*.md"))
    return sorted(
        [
            p for p in candidates
            if slug_substring in p.name.lower()
            and p.stat().st_size >= _MIN_REPORT_BYTES
        ],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )


def latest_report_for(slug_substring: str) -> Optional[Path]:
    """Find the most recent report whose filename contains the given slug."""
    rs = reports_for(slug_substring)
    return rs[0] if rs else None


def previous_report_for(slug_substring: str) -> Optional[Path]:
    """Find the second-most-recent report (the one before the latest)."""
    rs = reports_for(slug_substring)
    return rs[1] if len(rs) >= 2 else None


def parse_health_score(report_path: Path) -> Optional[int]:
    try:
        text = report_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return None
    m = HEALTH_SCORE_RE.search(text)
    return int(m.group(1)) if m else None


def parse_top_action(report_path: Path) -> Optional[str]:
    try:
        text = report_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return None
    m = TOP_ACTION_RE.search(text)
    return m.group(1).strip().strip("*•-").strip() if m else None


# =============================================================================
# Sprint 4 — Report extractors for the executive-summary header card.
# =============================================================================

# A line counts as a "win" if it carries a success cue ("✅", "passing",
# "+ resolved", "good", "healthy") and as a "loss" if it carries a problem
# cue (critical, broken, missing, blocked, ★★★, "high impact", etc.). We pull
# the top N of each from the report body and feed report_header_card().

_WIN_CUES = ("✅", "✓ ", "passing", "healthy", "+ resolved", "improved",
             "in compliance", "compliant", "looks good", "no issues",
             "all clear", "shipped", "completed")
_LOSS_CUES = ("❌", "🔴", "critical", "blocker", "broken", "missing",
              "blocked", "★★★", "high impact", "high priority",
              "must fix", "p0", "p1", "regressed", "failed", "fatal",
              "stalled")
_STRIP_PREFIX = re.compile(r"^[\s\-\*\•\d\.\)\]]+")
_MD_MARKERS = re.compile(r"[`*_#>]+")


def _clean_line(line: str) -> str:
    """Strip Markdown bullets, numbering, leading symbols, and tidy whitespace."""
    s = _STRIP_PREFIX.sub("", line).strip()
    s = _MD_MARKERS.sub("", s).strip()
    return s


def _bucket_line(line: str) -> Optional[str]:
    low = line.lower()
    for cue in _WIN_CUES:
        if cue in low:
            return "win"
    for cue in _LOSS_CUES:
        if cue in low:
            return "loss"
    return None


def extract_wins_losses(report_text: str, max_each: int = 3) -> Dict[str, List[str]]:
    """Pull top wins + top losses from any agent report.

    Heuristic: scan every non-empty line, bucket by cue keywords, dedupe,
    keep the first N of each. Caller passes the result into report_header_card.
    """
    wins, losses = [], []
    seen_wins, seen_losses = set(), set()

    for raw in report_text.splitlines():
        cleaned = _clean_line(raw)
        if len(cleaned) < 12 or len(cleaned) > 200:
            continue
        bucket = _bucket_line(cleaned)
        if bucket == "win" and cleaned not in seen_wins and len(wins) < max_each:
            wins.append(cleaned)
            seen_wins.add(cleaned)
        elif bucket == "loss" and cleaned not in seen_losses and len(losses) < max_each:
            losses.append(cleaned)
            seen_losses.add(cleaned)
        if len(wins) >= max_each and len(losses) >= max_each:
            break

    return {"wins": wins, "losses": losses}


def build_header_subtitle(report_path: Path) -> str:
    """One-liner subtitle for the report header card."""
    try:
        when = dt.datetime.fromtimestamp(report_path.stat().st_mtime)
        return f"{report_path.name} · {time_ago(when)}"
    except Exception:
        return report_path.name


def rank_movers(top_n: int = 5) -> List[dict]:
    """Top rank changes since the previous check, sorted by absolute delta."""
    movers = []
    for kw in list_keywords():
        h = history_for(kw)
        if len(h) < 2:
            continue
        latest, prev = h[-1], h[-2]
        # Ignore when nothing has changed or data is missing
        if latest.get("position") is None and prev.get("position") is None:
            continue
        # Treat None as 'not in top N' (assign sentinel = 100 for delta purposes)
        a = prev["position"] if prev["position"] is not None else 100
        b = latest["position"] if latest["position"] is not None else 100
        delta = a - b  # positive = improvement (lower position = better)
        if delta == 0:
            continue
        movers.append({
            "keyword": kw,
            "domain": latest["domain"],
            "from": prev["position"],
            "to": latest["position"],
            "delta": delta,
        })
    movers.sort(key=lambda m: abs(m["delta"]), reverse=True)
    return movers[:top_n]


def parse_issue_sections(report_path: Path) -> Dict[str, List[str]]:
    """Parse markdown bullets under each `## ...` section header.

    Specifically captures the green/amber/red headers from the Daily Health Check
    output format. Returns {section_header: [issue_text, ...]}.
    """
    try:
        text = report_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return {}
    sections: Dict[str, List[str]] = {}
    current: Optional[str] = None
    for raw in text.splitlines():
        line = raw.rstrip()
        # Section header
        if line.startswith("## "):
            current = line[3:].strip()
            # only keep the most useful ones
            sections.setdefault(current, [])
        # Bullet under a section
        elif current and (line.lstrip().startswith("- ") or line.lstrip().startswith("* ")):
            content = line.lstrip()[2:].strip()
            # strip leading bold markers like "**X**"
            content = re.sub(r"^\*\*([^*]+)\*\*\s*[—:-]?\s*", r"\1: ", content)
            sections[current].append(content)
        # Empty line resets bullet capture? No, keep current section open.
    return sections


def _norm_issue(text: str) -> str:
    """Normalise an issue line for fuzzy comparison across reports."""
    t = text.lower()
    t = re.sub(r"\d+(\.\d+)?\s*(ms|s|kb|mb|%|chars|px|/100)?\b", "N", t)  # numeric → N
    t = re.sub(r"https?://\S+", "URL", t)
    t = re.sub(r"[^a-z0-9 ]+", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t[:80]


@dataclass
class HealthDiff:
    latest_score: Optional[int]
    previous_score: Optional[int]
    score_delta: Optional[int]
    new_issues: List[str]
    resolved_issues: List[str]
    latest_issue_count: int
    previous_issue_count: int


def compare_health_reports(latest: Path, previous: Optional[Path]) -> HealthDiff:
    """Diff two health-check reports."""
    latest_score = parse_health_score(latest)
    prev_score = parse_health_score(previous) if previous else None
    score_delta = (
        latest_score - prev_score
        if (latest_score is not None and prev_score is not None)
        else None
    )

    latest_sections = parse_issue_sections(latest)
    prev_sections = parse_issue_sections(previous) if previous else {}

    # Flatten across sections that look like "issues"
    def _collect(sections: Dict[str, List[str]]) -> List[str]:
        out = []
        for header, items in sections.items():
            h = header.lower()
            if any(tag in h for tag in ("attention", "critical", "🟡", "🔴", "issue", "fixes")):
                out.extend(items)
        return out

    # Skip placeholder bullets like "(none)", "—", "n/a"
    _SKIP = {"(none)", "none", "—", "-", "n/a", "na"}

    def _real(items: List[str]) -> List[str]:
        return [i for i in items if i and i.lower().strip().strip(".") not in _SKIP]

    latest_issues = _real(_collect(latest_sections))
    prev_issues = _real(_collect(prev_sections))

    latest_map = {_norm_issue(i): i for i in latest_issues}
    prev_map = {_norm_issue(i): i for i in prev_issues}

    new_keys = [k for k in latest_map if k not in prev_map]
    resolved_keys = [k for k in prev_map if k not in latest_map]

    return HealthDiff(
        latest_score=latest_score,
        previous_score=prev_score,
        score_delta=score_delta,
        new_issues=[latest_map[k] for k in new_keys][:8],
        resolved_issues=[prev_map[k] for k in resolved_keys][:8],
        latest_issue_count=len(latest_issues),
        previous_issue_count=len(prev_issues),
    )


def time_ago(ts: dt.datetime) -> str:
    delta = dt.datetime.now() - ts
    secs = delta.total_seconds()
    if secs < 60:
        return "just now"
    if secs < 3600:
        return f"{int(secs // 60)} min ago"
    if secs < 86400:
        return f"{int(secs // 3600)} hr ago"
    if secs < 86400 * 2:
        return "yesterday"
    return f"{int(secs // 86400)} days ago"
