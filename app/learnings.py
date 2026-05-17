"""Sprint 6 — Smarter-over-time wiring.

Single source of truth for the "learning layer" auto-injected into every
agent's system prompt. Combines:

  • The agent's free-form learnings notebook (you edit it on the Notebooks page)
  • Recent rejections of this agent's output, with reasons
  • Starred reports for this agent (few-shot reference vault, with your note)
  • A digest of the last N saved reports for this project (RAG)

All four pieces are project-scoped via the active_project_id helpers in db.py.
Block is silently empty when there's no signal to inject.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import List

from app.db import (
    get_agent_notes,
    list_favorites_with_notes,
    recent_rejections,
)


# Mirror briefing._MIN_REPORT_BYTES so the digest skips stubs
_MIN_REPORT_BYTES = 500


def _project_reports_dir() -> Path:
    """Resolve to the active project's report subfolder."""
    try:
        from app.briefing import project_reports_dir  # local import — avoid cycle
        return project_reports_dir()
    except Exception:
        # Fallback to flat /reports
        return Path(__file__).resolve().parent.parent / "reports"


def _extract_agent_section(report_text: str, agent_full_name: str) -> str:
    """Pull just the {agent}'s section out of a saved combined report.

    Reports are saved with headers like '## 🔎 Kira Nakamura — research findings'
    — split on '##' and keep the chunk that mentions the agent's name.
    """
    if not report_text:
        return ""
    chunks = re.split(r"\n(?=##\s)", report_text)
    for chunk in chunks:
        if agent_full_name.split()[0].lower() in chunk[:200].lower():
            # Trim to a sensible size so we don't blow the context window
            return chunk.strip()[:1800]
    # Fallback: first 1800 chars
    return report_text.strip()[:1800]


def _past_reports_digest(agent_full_name: str, last_n: int = 3) -> str:
    """Return a short digest of the last N saved reports for this project,
    extracting just the relevant agent's section from each.
    """
    rdir = _project_reports_dir()
    if not rdir.exists():
        return ""
    reports = sorted(
        [p for p in rdir.glob("*.md")
         if p.is_file() and p.stat().st_size >= _MIN_REPORT_BYTES],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )[:last_n]
    if not reports:
        return ""

    out: List[str] = []
    for p in reports:
        try:
            body = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        section = _extract_agent_section(body, agent_full_name)
        if section:
            out.append(f"### From `{p.name}`\n{section}")
    if not out:
        return ""
    return (
        "## Your recent work on this project (last "
        f"{len(out)} report{'s' if len(out) != 1 else ''})\n\n"
        "Read these to stay consistent and avoid repeating yourself:\n\n"
        + "\n\n---\n\n".join(out)
    )


def _few_shot_block(report_name_prefix: str = "") -> str:
    """Starred reports as reference examples. Uses the optional note as the
    'why-it's-great' tag the agent should learn from.
    """
    favs = list_favorites_with_notes()
    if not favs:
        return ""
    rdir = _project_reports_dir()
    legacy = rdir.parent / "reports"  # also check flat /reports
    lines = ["## Reference examples (starred reports for this project)\n"]
    kept = 0
    for f in favs:
        rname = f["report_name"]
        # Try project subfolder first, then flat
        candidates = [rdir / rname, legacy / rname]
        body = ""
        for c in candidates:
            if c.exists():
                try:
                    body = c.read_text(encoding="utf-8", errors="ignore")
                    break
                except Exception:
                    continue
        if not body:
            continue
        note = (f.get("note") or "").strip()
        snippet = body[:900].rstrip()
        why = f"\n> Why this is a good reference: {note}" if note else ""
        lines.append(f"### `{rname}`{why}\n\n{snippet}\n…")
        kept += 1
        if kept >= 2:
            break  # cap injected examples to 2 to keep context tight
    if kept == 0:
        return ""
    return "\n".join(lines)


def _notes_block(agent_key: str) -> str:
    notes = (get_agent_notes(agent_key) or "").strip()
    if not notes:
        return ""
    return (
        "## Your learnings notebook (curated by the operator)\n\n"
        "These are stable, durable lessons you've earned on this project. "
        "Apply them silently — don't quote them at the user.\n\n"
        f"{notes}"
    )


def _rejections_block(agent_key: str, limit: int = 5) -> str:
    rejs = recent_rejections(agent_key=agent_key, limit=limit)
    if not rejs:
        return ""
    lines = [
        "## Things to avoid (from recent operator feedback)",
        "",
        "Past outputs were rejected with these reasons. Don't repeat the "
        "patterns that led to them:",
        "",
    ]
    for r in rejs:
        when = (r.get("rejected_at") or "")[:10]
        rep = r.get("report_name") or "(no report)"
        lines.append(f"- **{when}** · `{rep}` → {r['reason']}")
    return "\n".join(lines)


def learnings_block(agent_key: str, agent_full_name: str,
                    include_past_reports: bool = True,
                    past_reports_n: int = 3) -> str:
    """Assemble the full learning context block for an agent.

    Returns "" if there is nothing meaningful to inject. Otherwise wraps the
    sub-blocks in a clearly-delimited section ready to append to a system
    prompt.
    """
    parts: List[str] = []
    notes = _notes_block(agent_key)
    if notes:
        parts.append(notes)
    rej = _rejections_block(agent_key)
    if rej:
        parts.append(rej)
    fewshot = _few_shot_block()
    if fewshot:
        parts.append(fewshot)
    if include_past_reports:
        digest = _past_reports_digest(agent_full_name, last_n=past_reports_n)
        if digest:
            parts.append(digest)
    if not parts:
        return ""
    return (
        "\n\n---\n\n"
        "# OPERATOR-CURATED LEARNINGS (auto-injected — every run)\n\n"
        + "\n\n".join(parts)
        + "\n\n---\n"
    )
