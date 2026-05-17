"""Load + edit project context auto-injected into agents.

Order of precedence (Sprint 5):
  1. Active project's `claude_md` field (per-project override) — if set.
  2. Top-level CLAUDE.md file at project root (legacy / shared default).
  3. Empty string.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTEXT_PATH = ROOT / "CLAUDE.md"


def _per_project_override() -> str:
    """Return the active project's claude_md override, or '' if unavailable."""
    try:
        from app.db import active_project
        proj = active_project()
        if proj and (proj.get("claude_md") or "").strip():
            return proj["claude_md"].strip()
    except Exception:
        pass
    return ""


def load_context() -> str:
    """Per-project override > top-level CLAUDE.md > ''."""
    override = _per_project_override()
    if override:
        return override
    if not CONTEXT_PATH.exists():
        return ""
    try:
        return CONTEXT_PATH.read_text(encoding="utf-8")
    except Exception:
        return ""


def context_block_for_prompt() -> str:
    """Wrapped context block ready to prepend to an agent's system prompt."""
    body = load_context().strip()
    if not body:
        return ""
    return (
        "\n\n---\n\n"
        "# PROJECT CONTEXT (applies to every run)\n\n"
        f"{body}\n\n"
        "---\n"
    )


def save_context(markdown: str) -> None:
    """Save the active project's claude_md override (or fall back to file).

    If there's an active project, the markdown is stored on that project
    row. If not, falls back to the shared CLAUDE.md file (legacy mode).
    """
    try:
        from app.db import active_project_id, update_project
        pid = active_project_id()
        if pid:
            update_project(pid, claude_md=markdown)
            return
    except Exception:
        pass
    CONTEXT_PATH.write_text(markdown, encoding="utf-8")
