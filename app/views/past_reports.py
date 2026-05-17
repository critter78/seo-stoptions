"""📂 Past Reports — browse, search, favorite, delete, compare."""
from __future__ import annotations

import datetime as dt
import difflib
import re
from pathlib import Path

import streamlit as st

from app.briefing import (
    build_header_subtitle,
    extract_wins_losses,
    parse_health_score,
)
from app.db import (
    add_agent_rejection,
    init_db,
    is_favorite,
    list_favorites_with_notes,
    set_favorite_note,
    toggle_favorite,
)
from app.ui_helpers import (
    ACCENT, BG_CARD, BORDER, TEXT_MUTED, TEXT_PRIMARY,
    empty_state_card, logo_html, report_header_card,
)

REPORTS_DIR = Path(__file__).resolve().parent.parent.parent / "reports"
REPORTS_DIR.mkdir(exist_ok=True)

init_db()

st.markdown(
    f"""
    <div style="background:linear-gradient(135deg,#0d1117 0%,#161B22 100%);
                border:1px solid {BORDER};border-radius:14px;
                padding:20px 24px;margin-bottom:24px;">
      <div style="display:flex;align-items:center;gap:14px;margin-bottom:6px;">
        {logo_html(height=36)}
        <div style="font-size:0.78rem;color:{ACCENT};letter-spacing:0.14em;
                    text-transform:uppercase;font-weight:600;">Archive</div>
      </div>
      <h1 style="margin:0 0 8px;font-size:1.7rem;color:{TEXT_PRIMARY};">
        📂 Past Reports
      </h1>
      <div style="color:{TEXT_MUTED};font-size:0.92rem;line-height:1.55;">
        Star to pin favorites. Compare two reports side-by-side. Delete cleanup
        cruft. Full-text search across every report.
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# Sprint 5: glob both the active-project subfolder AND the legacy flat dir
from app.briefing import project_reports_dir as _project_reports_dir
_proj_dir = _project_reports_dir()
_all_candidates = list(_proj_dir.glob("*.md"))
if _proj_dir != REPORTS_DIR:
    _all_candidates.extend(REPORTS_DIR.glob("*.md"))
reports = sorted(
    [p for p in _all_candidates if p.is_file() and p.stat().st_size > 100],
    key=lambda p: (not is_favorite(p.name), -p.stat().st_mtime),
)

if not reports:
    st.markdown(
        empty_state_card(
            icon="📂",
            title="No reports yet",
            body=(
                "Reports are generated when you run the crew from the Home page or "
                "fire a scheduled audit. Every run is auto-saved as Markdown here, "
                "with full-text search, favorites, and side-by-side comparison."
            ),
            cta_helptext=("↗ Open <strong>🏠 Home</strong> and click a Quick Start "
                          "to generate your first report."),
        ),
        unsafe_allow_html=True,
    )
    st.stop()

mode = st.radio("Mode", ["Browse", "Compare two"], horizontal=True,
                label_visibility="collapsed")

if mode == "Compare two":
    col1, col2 = st.columns(2)
    options = [p.name for p in reports]
    with col1:
        a_name = st.selectbox("Report A", options, index=0)
    with col2:
        b_name = st.selectbox("Report B", options, index=min(1, len(options) - 1))
    if a_name and b_name and a_name != b_name:
        a_path = REPORTS_DIR / a_name
        b_path = REPORTS_DIR / b_name
        a_text = a_path.read_text(encoding="utf-8", errors="ignore")
        b_text = b_path.read_text(encoding="utf-8", errors="ignore")
        diff_lines = list(difflib.unified_diff(
            a_text.splitlines(), b_text.splitlines(),
            fromfile=a_name, tofile=b_name, n=2, lineterm="",
        ))
        st.markdown(f"**{len(diff_lines)} diff lines**")
        if diff_lines:
            st.code("\n".join(diff_lines[:300]), language="diff")
            if len(diff_lines) > 300:
                st.caption(f"…and {len(diff_lines) - 300} more lines truncated.")
        else:
            st.info("Files are identical.")
    elif a_name == b_name:
        st.info("Pick two different reports to compare.")
    st.stop()

# Browse mode
col1, col2, col3 = st.columns([2, 1, 1])
with col1:
    query = st.text_input("🔍 Search across all reports",
                          placeholder="e.g. iron condor, canonical, JSON-LD")
with col2:
    earliest = dt.date.fromtimestamp(min(p.stat().st_mtime for p in reports))
    today = dt.date.today()
    date_from = st.date_input("From", value=earliest, min_value=earliest, max_value=today)
with col3:
    date_to = st.date_input("To", value=today, min_value=earliest, max_value=today)

show_only_favs = st.checkbox("⭐ Show only favorites")

filtered = []
for p in reports:
    if show_only_favs and not is_favorite(p.name):
        continue
    mtime = dt.date.fromtimestamp(p.stat().st_mtime)
    if not (date_from <= mtime <= date_to):
        continue
    text = p.read_text(encoding="utf-8", errors="ignore")
    if query and query.lower() not in text.lower():
        continue
    filtered.append((p, text, mtime))

st.markdown(
    f"<div style='color:{TEXT_MUTED};font-size:0.85rem;margin:8px 0 16px;'>"
    f"<strong style='color:{TEXT_PRIMARY};'>{len(filtered)}</strong> report"
    f"{'s' if len(filtered)!=1 else ''} match"
    f"</div>",
    unsafe_allow_html=True,
)

for p, text, mtime in filtered:
    size_kb = p.stat().st_size // 1024
    star = "⭐ " if is_favorite(p.name) else ""
    header = f"{star}📄 {p.name}  ·  {mtime.isoformat()}  ·  {size_kb} KB"
    with st.expander(header):
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            if st.button(("⭐ Unfavorite" if is_favorite(p.name) else "☆ Favorite"),
                         key=f"fav_{p.name}", use_container_width=True):
                toggle_favorite(p.name)
                st.rerun()
        with c2:
            st.download_button(
                "⬇️ Download", data=text, file_name=p.name, mime="text/markdown",
                key=f"dl_{p.name}", use_container_width=True,
            )
        with c3:
            if st.button("👎 Reject", key=f"rej_{p.name}",
                         use_container_width=True,
                         help="Tell the agent what was wrong — gets injected into "
                              "their next-run prompt as 'things to avoid'."):
                st.session_state[f"rej_open_{p.name}"] = True
        with c4:
            if st.button("🗑 Delete", key=f"del_{p.name}", use_container_width=True):
                try:
                    p.unlink()
                    st.success(f"Deleted {p.name}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Could not delete: {e}")

        # ---- Sprint 6: rejection dialog (inline) ----
        if st.session_state.get(f"rej_open_{p.name}"):
            with st.container(border=True):
                st.markdown("**👎 Reject this output**")
                _agent_pick = st.selectbox(
                    "Which agent's output should learn from this?",
                    ["analyst", "researcher", "seo_marketer", "pm"],
                    format_func=lambda k: {
                        "analyst": "🧠 Cash (analyst)",
                        "researcher": "🔎 Kira (researcher)",
                        "seo_marketer": "📣 Maya (SEO marketer)",
                        "pm": "📋 Linz (PM)",
                    }.get(k, k),
                    key=f"rej_agent_{p.name}",
                )
                _reason = st.text_area(
                    "Reason (be specific — this is what the agent will see)",
                    placeholder="e.g. Buried the top recommendation under three paragraphs of caveats.",
                    height=80, key=f"rej_reason_{p.name}",
                )
                _rc1, _rc2 = st.columns(2)
                if _rc1.button("Log rejection", key=f"rej_log_{p.name}",
                               type="primary", use_container_width=True,
                               disabled=not (_reason or "").strip()):
                    add_agent_rejection(
                        agent_key=_agent_pick,
                        reason=_reason.strip(),
                        report_name=p.name,
                    )
                    st.session_state[f"rej_open_{p.name}"] = False
                    st.success("Logged. The next run for this agent will see it.")
                    st.rerun()
                if _rc2.button("Cancel", key=f"rej_cancel_{p.name}",
                               use_container_width=True):
                    st.session_state[f"rej_open_{p.name}"] = False
                    st.rerun()

        # ---- Sprint 6: few-shot note field, only when this report is starred ----
        if is_favorite(p.name):
            _existing_note = next(
                (f.get("note", "") for f in list_favorites_with_notes()
                 if f["report_name"] == p.name),
                "",
            )
            _note = st.text_input(
                "⭐ Reference note (why this report is a good example for the agents)",
                value=_existing_note or "",
                key=f"fnote_{p.name}",
                placeholder="e.g. Cash nailed the prioritisation — S/M/L effort + ★ ratings + named owners.",
            )
            if _note != (_existing_note or ""):
                if st.button("💾 Save note", key=f"fnote_save_{p.name}"):
                    set_favorite_note(p.name, _note)
                    st.success("Saved. Agents will see this with the reference example.")
                    st.rerun()

        if query:
            hits = [m.start() for m in re.finditer(re.escape(query), text, flags=re.IGNORECASE)]
            if hits:
                st.markdown(
                    f"<div style='color:{TEXT_MUTED};font-size:0.8rem;"
                    f"margin:8px 0 4px;'>{len(hits)} match"
                    f"{'es' if len(hits)!=1 else ''}</div>",
                    unsafe_allow_html=True,
                )
                for h in hits[:3]:
                    snippet = text[max(0, h - 100): h + 120].replace("\n", " ")
                    st.markdown(
                        f"<div style='background:{BG_CARD};border-left:3px solid {ACCENT};"
                        f"padding:6px 12px;margin:4px 0;font-size:0.85rem;"
                        f"color:{TEXT_PRIMARY};border-radius:4px;'>…{snippet}…</div>",
                        unsafe_allow_html=True,
                    )
                st.divider()

        # ---- Sprint 4: executive summary header card (parsed from the body)
        score = parse_health_score(p)
        wl = extract_wins_losses(text, max_each=3)
        st.markdown(
            report_header_card(
                score=score,
                top_wins=wl["wins"],
                top_losses=wl["losses"],
                subtitle=build_header_subtitle(p),
            ),
            unsafe_allow_html=True,
        )

        # ---- Sprint 4: TL;DR toggle for long reports
        if len(text) > 2000:
            preview = text[:1500].rsplit("\n", 1)[0] + "\n\n…"
            st.markdown(preview)
            with st.expander(f"📜 Show full report ({len(text):,} chars)"):
                st.markdown(text)
        else:
            st.markdown(text)
