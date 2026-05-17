"""Shared UI helpers — portrait avatars, crew cards, status badges.

All HTML is inlined (no external CSS) so the Streamlit components render
crisply with no flash-of-unstyled-content. Portraits are base64-embedded
data URIs, cached by file path + mtime so they're only encoded once per
session (and re-encoded the moment you drop a new image in).
"""
from __future__ import annotations

import base64
import io
from pathlib import Path
from typing import Optional

import streamlit as st
from PIL import Image

from agents.personas import Persona

# --- branding -----------------------------------------------------------------
_BRAND_DIR = Path(__file__).resolve().parent.parent / "assets"
_LOGO_EXTS = (".png", ".jpg", ".jpeg", ".webp", ".svg")


def _logo_path() -> Optional[Path]:
    for ext in _LOGO_EXTS:
        p = _BRAND_DIR / f"logo{ext}"
        if p.exists() and p.stat().st_size > 200:
            return p
    return None


def _team_mamba_path() -> Optional[Path]:
    for ext in _LOGO_EXTS:
        p = _BRAND_DIR / f"team_mamba{ext}"
        if p.exists() and p.stat().st_size > 200:
            return p
    return None


@st.cache_data(show_spinner=False)
def _encode_logo(path_str: str, mtime: float) -> Optional[str]:
    p = Path(path_str)
    if not p.exists():
        return None
    try:
        if p.suffix.lower() == ".svg":
            data = p.read_text(encoding="utf-8")
            return "data:image/svg+xml;base64," + base64.b64encode(data.encode()).decode()
        # Raster: keep original transparency by encoding as PNG
        im = Image.open(p)
        im.thumbnail((512, 512), Image.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, "PNG", optimize=True)
        return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
    except Exception:
        return None


def logo_data_uri() -> Optional[str]:
    lp = _logo_path()
    if not lp:
        return None
    return _encode_logo(str(lp), lp.stat().st_mtime)


def team_mamba_data_uri() -> Optional[str]:
    tp = _team_mamba_path()
    if not tp:
        return None
    return _encode_logo(str(tp), tp.stat().st_mtime)


def page_icon() -> object:
    """Return a Streamlit page_icon — logo file if present, else 📈 emoji."""
    lp = _logo_path()
    if lp and lp.suffix.lower() != ".svg":
        try:
            return Image.open(lp)
        except Exception:
            pass
    return "📈"


def logo_html(height: int = 24, fallback_emoji: str = "📈") -> str:
    """Inline <img> for the logo (or fallback emoji span). Height in px."""
    uri = logo_data_uri()
    if uri:
        return (
            f'<img src="{uri}" alt="Stoptions.ai" '
            f'style="height:{height}px;width:auto;display:inline-block;'
            f'vertical-align:middle;" />'
        )
    return (
        f'<span style="font-size:{height}px;line-height:1;display:inline-block;'
        f'vertical-align:middle;">{fallback_emoji}</span>'
    )


def team_mamba_html(height: int = 20) -> str:
    """Inline <img> for the Team Mamba icon — empty string if no file present."""
    uri = team_mamba_data_uri()
    if not uri:
        return ""
    return (
        f'<img src="{uri}" alt="Team Mamba" '
        f'style="height:{height}px;width:auto;display:inline-block;'
        f'vertical-align:middle;opacity:0.95;" />'
    )


# --- accent palette (matches .streamlit/config.toml) --------------------------
ACCENT = "#3DDC97"
ACCENT_SOFT = "rgba(61,220,151,0.10)"
BG_PRIMARY = "#0E1117"
BG_CARD = "#161B22"
BORDER = "#30363D"
TEXT_PRIMARY = "#E6EDF3"
TEXT_MUTED = "#8B949E"


@st.cache_data(show_spinner=False)
def _encode_portrait(path_str: str, mtime: float, max_dim: int) -> Optional[str]:
    """Cached image → JPEG data URI. mtime in the key invalidates on file change."""
    p = Path(path_str)
    if not p.exists() or p.stat().st_size < 1024:
        return None
    try:
        im = Image.open(p).convert("RGB")
        im.thumbnail((max_dim, max_dim * 2), Image.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=85, optimize=True, progressive=True)
        return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
    except Exception:
        return None


def portrait_data_uri(p: Persona, max_dim: int = 600) -> Optional[str]:
    """Full-body / 4:5 portrait for the Crew page."""
    if not p.has_portrait:
        return None
    pp = p.portrait_path
    return _encode_portrait(str(pp), pp.stat().st_mtime, max_dim)


def avatar_data_uri(p: Persona, max_dim: int = 240) -> Optional[str]:
    """Tight headshot for circular avatars (falls back to portrait if no headshot)."""
    if not p.has_avatar:
        return None
    ap = p.avatar_path
    return _encode_portrait(str(ap), ap.stat().st_mtime, max_dim)


def avatar_html(p: Persona, size: int = 44, ring: str = ACCENT) -> str:
    """Small circular avatar — used in sidebar + live progress messages."""
    uri = avatar_data_uri(p, max_dim=max(size * 3, 240))
    if uri:
        return (
            f'<div style="width:{size}px;height:{size}px;border-radius:50%;'
            f'background-image:url({uri});background-size:cover;'
            f'background-position:center 15%;'
            f'border:2px solid {ring};flex-shrink:0;'
            f'box-shadow:0 0 0 1px rgba(0,0,0,0.4);"></div>'
        )
    # Fallback: emoji disc
    font_size = int(size * 0.5)
    return (
        f'<div style="width:{size}px;height:{size}px;border-radius:50%;'
        f'background:{BG_CARD};display:flex;align-items:center;'
        f'justify-content:center;font-size:{font_size}px;'
        f'border:2px solid {BORDER};flex-shrink:0;">{p.emoji}</div>'
    )


def _name_with_nickname(p: Persona) -> str:
    """Format as 'First "Nick" Last' (e.g. Kira "Recon" Nakamura)."""
    if not p.nickname:
        return p.full_name
    parts = p.full_name.split(" ", 1)
    first = parts[0]
    rest = parts[1] if len(parts) > 1 else ""
    return f'{first} &ldquo;{p.nickname}&rdquo; {rest}'.strip()


def sidebar_crew_row_html(p: Persona) -> str:
    """One row in the sidebar Crew list — avatar + name + role.

    Bio details (age, heritage, etc.) intentionally omitted here — those live
    on the 👥 The Crew page where the user opens the full bio.
    """
    return (
        f'<div style="display:flex;align-items:center;gap:10px;margin:8px 0;">'
        f'  {avatar_html(p, size=40)}'
        f'  <div style="line-height:1.25;min-width:0;">'
        f'    <div style="font-weight:600;color:{TEXT_PRIMARY};font-size:0.9rem;">'
        f'      {_name_with_nickname(p)}'
        f'    </div>'
        f'    <div style="font-size:0.72rem;color:{TEXT_MUTED};'
        f'      white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">'
        f'      {p.role}'
        f'    </div>'
        f'  </div>'
        f'</div>'
    )


def crew_card_html(p: Persona) -> str:
    """Full-size crew card for the Crew page — portrait + bio."""
    uri = portrait_data_uri(p, max_dim=900)
    if uri:
        portrait_block = (
            f'<div style="aspect-ratio:4/5;width:100%;'
            f'background-image:url({uri});background-size:cover;'
            f'background-position:center top;border-radius:10px;'
            f'box-shadow:0 8px 24px rgba(0,0,0,0.45);"></div>'
        )
    else:
        portrait_block = (
            f'<div style="aspect-ratio:4/5;width:100%;'
            f'background:linear-gradient(135deg,{BG_CARD},{BG_PRIMARY});'
            f'border:1px solid {BORDER};border-radius:10px;'
            f'display:flex;align-items:center;justify-content:center;'
            f'font-size:6rem;">{p.emoji}</div>'
        )

    bg = []
    for b in p.background:
        bg.append(f'<li style="margin:4px 0;">{b}</li>')
    exp = []
    for e in p.expertise:
        exp.append(f'<li style="margin:4px 0;">{e}</li>')

    return f'''
<div style="background:{BG_CARD};border:1px solid {BORDER};border-radius:14px;
            padding:18px;height:100%;display:flex;flex-direction:column;gap:14px;">
  {portrait_block}
  <div>
    <div style="font-size:1.2rem;font-weight:600;color:{TEXT_PRIMARY};line-height:1.25;">
      {p.emoji} {_name_with_nickname(p)}
    </div>
    <div style="font-size:0.85rem;color:{TEXT_MUTED};margin-top:2px;">
      {p.pronouns} &middot; {p.role}
    </div>
  </div>
  <div style="font-style:italic;color:{ACCENT};font-size:0.92rem;
              padding:10px 14px;background:{ACCENT_SOFT};
              border-left:3px solid {ACCENT};border-radius:4px;">
    "{p.tagline}"
  </div>
  <div style="display:grid;grid-template-columns:auto 1fr;gap:6px 12px;
              font-size:0.85rem;color:{TEXT_PRIMARY};">
    <div style="color:{TEXT_MUTED};">Age</div><div>{p.age}</div>
    <div style="color:{TEXT_MUTED};">Height</div><div>{p.height}</div>
    <div style="color:{TEXT_MUTED};">Status</div><div>{p.marital_status}</div>
    <div style="color:{TEXT_MUTED};">Heritage</div><div>{p.nationality}</div>
    <div style="color:{TEXT_MUTED};">Training</div><div>{p.education}</div>
  </div>
  <div>
    <div style="font-size:0.78rem;color:{TEXT_MUTED};text-transform:uppercase;
                letter-spacing:0.08em;margin-bottom:6px;">Background</div>
    <ul style="margin:0;padding-left:18px;font-size:0.88rem;color:{TEXT_PRIMARY};
               line-height:1.5;">{"".join(bg)}</ul>
  </div>
  <div>
    <div style="font-size:0.78rem;color:{TEXT_MUTED};text-transform:uppercase;
                letter-spacing:0.08em;margin-bottom:6px;">Where the edge comes from</div>
    <ul style="margin:0;padding-left:18px;font-size:0.88rem;color:{TEXT_PRIMARY};
               line-height:1.5;">{"".join(exp)}</ul>
  </div>
  <div style="margin-top:auto;padding-top:10px;border-top:1px solid {BORDER};
              font-size:0.82rem;color:{TEXT_MUTED};line-height:1.45;">
    <strong style="color:{TEXT_PRIMARY};">Mamba trait:</strong> {p.mamba_trait}
  </div>
</div>
'''


def status_pill_html(label: str, ok: bool, value: str = "", optional: bool = False) -> str:
    """Status pill. ok=True → green. ok=False → red (or grey if optional=True)."""
    if ok:
        color = ACCENT
        bg = "rgba(61,220,151,0.08)"
        dot = "●"
    elif optional:
        color = "#6E7681"
        bg = "rgba(110,118,129,0.10)"
        dot = "○"
    else:
        color = "#F85149"
        bg = "rgba(248,81,73,0.08)"
        dot = "●"
    val_html = (
        f'<span style="color:{TEXT_MUTED};margin-left:auto;font-size:0.78rem;">{value}</span>'
        if value else ""
    )
    return (
        f'<div style="display:flex;align-items:center;gap:8px;'
        f'padding:6px 10px;background:{bg};border-radius:6px;'
        f'border:1px solid {BORDER};margin:4px 0;font-size:0.82rem;">'
        f'<span style="color:{color};">{dot}</span>'
        f'<span style="color:{TEXT_PRIMARY};">{label}</span>'
        f'{val_html}'
        f'</div>'
    )


def progress_line_html(p: Persona, message: str) -> str:
    """Avatar + message line for the live status panel."""
    return (
        f'<div style="display:flex;align-items:center;gap:12px;padding:8px 0;">'
        f'  {avatar_html(p, size=36)}'
        f'  <div style="color:{TEXT_PRIMARY};font-weight:500;">{message}</div>'
        f'</div>'
    )


# =============================================================================
# Sprint 4 — Design system: reusable components used across every dashboard
# =============================================================================
#
# Severity palette — single source of truth for badge + delta colours.
SEVERITY = {
    "critical": {"bg": "rgba(248,81,73,0.14)",  "fg": "#F85149", "label": "Critical", "icon": "🔴"},
    "high":     {"bg": "rgba(248,81,73,0.10)",  "fg": "#F85149", "label": "High",     "icon": "🔴"},
    "medium":   {"bg": "rgba(244,185,64,0.14)", "fg": "#F4B940", "label": "Medium",   "icon": "🟠"},
    "low":      {"bg": "rgba(110,118,129,0.14)","fg": "#8B949E", "label": "Low",      "icon": "⚪"},
    "good":     {"bg": "rgba(61,220,151,0.12)", "fg": "#3DDC97", "label": "Good",     "icon": "🟢"},
    "info":     {"bg": "rgba(89,148,255,0.12)", "fg": "#5994FF", "label": "Info",     "icon": "🔵"},
}


def severity_badge(level: str, label: Optional[str] = None) -> str:
    """Inline pill badge — `severity_badge("high", "LCP > 4s")`.

    Levels: critical, high, medium, low, good, info. Unknown falls back to info.
    """
    spec = SEVERITY.get((level or "info").lower(), SEVERITY["info"])
    text = label or spec["label"]
    return (
        f'<span style="display:inline-flex;align-items:center;gap:5px;'
        f'padding:3px 9px;border-radius:999px;background:{spec["bg"]};'
        f'color:{spec["fg"]};font-size:0.75rem;font-weight:600;'
        f'line-height:1.4;white-space:nowrap;">'
        f'<span style="font-size:0.7rem;line-height:1;">{spec["icon"]}</span>'
        f'<span>{text}</span></span>'
    )


# Words that drive severity detection in agent-written reports.
_SEVERITY_KEYWORDS = [
    ("critical", ["critical", "blocker", "broken", "fatal", "blocking"]),
    ("high",     ["high priority", "high impact", "urgent", "must fix", "p0", "p1", "★★★"]),
    ("medium",   ["medium", "moderate", "p2", "★★"]),
    ("low",      ["low priority", "low impact", "minor", "nit", "p3", "★ "]),
    ("good",     ["✅", "good", "passing", "healthy", "resolved", "+ "]),
]


def infer_severity(text: str) -> str:
    """Map a free-form line to a severity bucket. Heuristic only."""
    if not text:
        return "info"
    t = text.lower()
    for level, words in _SEVERITY_KEYWORDS:
        for w in words:
            if w in t:
                return level
    return "info"


def stat_card(
    label: str,
    value: str,
    delta: Optional[str] = None,
    delta_kind: str = "neutral",   # "up", "down", "neutral"
    icon: str = "",
    helptext: str = "",
) -> str:
    """Compact KPI card — `stat_card("Health score", "82", "+4", "up")`.

    Returns an HTML string; wrap in st.markdown(..., unsafe_allow_html=True).
    """
    delta_html = ""
    if delta:
        if delta_kind == "up":
            d_color, d_arrow = "#3DDC97", "▲"
        elif delta_kind == "down":
            d_color, d_arrow = "#F85149", "▼"
        else:
            d_color, d_arrow = TEXT_MUTED, "▶"
        delta_html = (
            f'<div style="margin-top:4px;font-size:0.78rem;color:{d_color};'
            f'font-weight:600;">{d_arrow} {delta}</div>'
        )
    icon_html = (
        f'<span style="font-size:1rem;margin-right:6px;opacity:0.85;">{icon}</span>'
        if icon else ""
    )
    help_html = (
        f'<div style="margin-top:6px;font-size:0.72rem;color:{TEXT_MUTED};'
        f'line-height:1.4;">{helptext}</div>' if helptext else ""
    )
    return (
        f'<div style="background:{BG_CARD};border:1px solid {BORDER};'
        f'border-radius:10px;padding:14px 16px;height:100%;">'
        f'<div style="font-size:0.7rem;color:{TEXT_MUTED};text-transform:uppercase;'
        f'letter-spacing:0.08em;font-weight:600;margin-bottom:6px;">'
        f'{icon_html}{label}</div>'
        f'<div style="font-size:1.55rem;color:{TEXT_PRIMARY};font-weight:700;'
        f'line-height:1.1;">{value}</div>'
        f'{delta_html}{help_html}</div>'
    )


def empty_state_card(
    icon: str,
    title: str,
    body: str,
    cta_label: Optional[str] = None,
    cta_url: Optional[str] = None,
    cta_helptext: Optional[str] = None,
) -> str:
    """Friendly empty-state placeholder card.

    Returns HTML; for actionable CTAs that need st.button, render the card
    via st.markdown then add the button separately and use cta_helptext only.
    """
    cta_html = ""
    if cta_label and cta_url:
        cta_html = (
            f'<a href="{cta_url}" target="_self" '
            f'style="display:inline-block;margin-top:14px;padding:8px 16px;'
            f'background:{ACCENT};color:#0E1117;border-radius:8px;'
            f'text-decoration:none;font-weight:600;font-size:0.88rem;">'
            f'{cta_label} →</a>'
        )
    elif cta_helptext:
        cta_html = (
            f'<div style="margin-top:14px;padding:8px 14px;background:{ACCENT_SOFT};'
            f'border-left:3px solid {ACCENT};border-radius:6px;font-size:0.85rem;'
            f'color:{TEXT_PRIMARY};">{cta_helptext}</div>'
        )
    return (
        f'<div style="background:{BG_CARD};border:1px dashed {BORDER};'
        f'border-radius:12px;padding:32px 28px;text-align:center;'
        f'margin:12px 0;">'
        f'<div style="font-size:2.4rem;line-height:1;margin-bottom:14px;'
        f'opacity:0.85;">{icon}</div>'
        f'<div style="color:{TEXT_PRIMARY};font-size:1.05rem;font-weight:600;'
        f'margin-bottom:8px;">{title}</div>'
        f'<div style="color:{TEXT_MUTED};font-size:0.88rem;line-height:1.55;'
        f'max-width:480px;margin:0 auto;">{body}</div>'
        f'{cta_html}</div>'
    )


def report_header_card(
    score: Optional[int] = None,
    top_wins: Optional[list] = None,
    top_losses: Optional[list] = None,
    subtitle: str = "",
) -> str:
    """Executive summary card injected at the top of any agent report.

    `top_wins` / `top_losses` are short bullet strings (clip to 3 each).
    """
    top_wins = (top_wins or [])[:3]
    top_losses = (top_losses or [])[:3]

    # Score block
    if score is None:
        score_block = (
            f'<div style="font-size:1rem;color:{TEXT_MUTED};">No score</div>'
        )
    else:
        if score >= 90:
            sc = "#3DDC97"
        elif score >= 70:
            sc = "#F4B940"
        else:
            sc = "#F85149"
        score_block = (
            f'<div style="display:flex;align-items:baseline;gap:4px;">'
            f'<span style="font-size:2.8rem;font-weight:700;color:{sc};'
            f'line-height:1;">{score}</span>'
            f'<span style="font-size:0.9rem;color:{TEXT_MUTED};">/100</span>'
            f'</div>'
        )

    def _bullets(items, color, icon):
        if not items:
            return (
                f'<div style="font-size:0.82rem;color:{TEXT_MUTED};'
                f'font-style:italic;">None highlighted</div>'
            )
        return "".join(
            f'<div style="display:flex;align-items:flex-start;gap:6px;'
            f'padding:3px 0;font-size:0.85rem;line-height:1.45;">'
            f'<span style="color:{color};flex-shrink:0;">{icon}</span>'
            f'<span style="color:{TEXT_PRIMARY};">{i}</span></div>'
            for i in items
        )

    sub_html = (
        f'<div style="font-size:0.82rem;color:{TEXT_MUTED};margin-top:4px;">{subtitle}</div>'
        if subtitle else ""
    )

    return (
        f'<div style="background:linear-gradient(135deg,#0d1117 0%,#161B22 100%);'
        f'border:1px solid {BORDER};border-radius:12px;padding:18px 22px;'
        f'margin:10px 0 16px;">'
        f'<div style="display:flex;align-items:center;justify-content:space-between;'
        f'margin-bottom:14px;">'
        f'<div>'
        f'<div style="font-size:0.7rem;color:{TEXT_MUTED};text-transform:uppercase;'
        f'letter-spacing:0.1em;font-weight:600;">Executive summary</div>'
        f'{sub_html}'
        f'</div>'
        f'{score_block}'
        f'</div>'
        f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:18px;">'
        f'<div>'
        f'<div style="font-size:0.7rem;color:#3DDC97;text-transform:uppercase;'
        f'letter-spacing:0.08em;font-weight:600;margin-bottom:6px;">'
        f'✅ Top wins</div>'
        f'{_bullets(top_wins, "#3DDC97", "✓")}'
        f'</div>'
        f'<div>'
        f'<div style="font-size:0.7rem;color:#F85149;text-transform:uppercase;'
        f'letter-spacing:0.08em;font-weight:600;margin-bottom:6px;">'
        f'⚠ Top losses</div>'
        f'{_bullets(top_losses, "#F85149", "!")}'
        f'</div>'
        f'</div>'
        f'</div>'
    )


def section_eyebrow(label: str, color: str = ACCENT) -> str:
    """Tiny uppercase label used above a section block."""
    return (
        f'<div style="font-size:0.7rem;color:{color};text-transform:uppercase;'
        f'letter-spacing:0.1em;font-weight:600;margin:8px 0;">{label}</div>'
    )


def section_card_open(title: str = "", subtitle: str = "") -> str:
    """Open a card div — pair with section_card_close().
    Use for grouping a stat row + body content cleanly.
    """
    hdr = ""
    if title or subtitle:
        sub = (
            f'<div style="color:{TEXT_MUTED};font-size:0.85rem;line-height:1.5;'
            f'margin-top:2px;">{subtitle}</div>' if subtitle else ""
        )
        title_html = (
            f'<div style="color:{TEXT_PRIMARY};font-size:1.05rem;font-weight:600;">'
            f'{title}</div>' if title else ""
        )
        hdr = (
            f'<div style="margin-bottom:12px;">{title_html}{sub}</div>'
        )
    return (
        f'<div style="background:{BG_CARD};border:1px solid {BORDER};'
        f'border-radius:12px;padding:18px 22px;margin:8px 0;">{hdr}'
    )


def section_card_close() -> str:
    return '</div>'


def quick_start_card_html(label: str, icon: str, subtitle: str) -> str:
    """Markdown for a Quick Start tile (used together with a hidden st.button)."""
    return (
        f'<div style="text-align:left;">'
        f'<div style="font-size:1.1rem;margin-bottom:2px;">{icon} {label}</div>'
        f'<div style="font-size:0.78rem;color:{TEXT_MUTED};line-height:1.4;">'
        f'{subtitle}</div></div>'
    )
