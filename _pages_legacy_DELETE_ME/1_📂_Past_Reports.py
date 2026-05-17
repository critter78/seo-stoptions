"""Past Reports browser — list, filter, search, view, download."""
from __future__ import annotations

import datetime as dt
import re
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.ui_helpers import ACCENT, BG_CARD, BORDER, TEXT_MUTED, TEXT_PRIMARY, logo_html, page_icon

st.set_page_config(page_title="Past Reports · Team Mamba", page_icon=page_icon(), layout="wide")

st.markdown(
    """<style>.block-container { padding-top: 2.5rem; max-width: 1100px; }</style>""",
    unsafe_allow_html=True,
)

# hero
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
        Every saved analyst report from <code>/reports</code> — filter by date,
        full-text search, download, re-open.
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

REPORTS_DIR = Path(__file__).resolve().parent.parent / "reports"
REPORTS_DIR.mkdir(exist_ok=True)

reports = sorted(
    [p for p in REPORTS_DIR.glob("*.md") if p.is_file()],
    key=lambda p: p.stat().st_mtime,
    reverse=True,
)

if not reports:
    st.info("No reports yet. Run the crew from the main page and they'll show up here.")
    st.stop()

# filters
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

# filter
filtered = []
for p in reports:
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
    header = f"📄 {p.name}  ·  {mtime.isoformat()}  ·  {size_kb} KB"
    with st.expander(header):
        st.download_button(
            "⬇️ Download Markdown", data=text, file_name=p.name,
            mime="text/markdown", key=f"dl_{p.name}",
        )
        if query:
            hits = [m.start() for m in re.finditer(re.escape(query), text, flags=re.IGNORECASE)]
            if hits:
                st.markdown(
                    f"<div style='color:{TEXT_MUTED};font-size:0.8rem;"
                    f"margin:8px 0 4px;'>{len(hits)} match"
                    f"{'es' if len(hits)!=1 else ''} — preview:</div>",
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
        st.markdown(text)
