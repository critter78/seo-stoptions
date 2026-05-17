"""Keyword rank-tracking history — chart positions over time."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.db import all_history, history_for, list_keywords, init_db
from app.config import DEFAULT_DOMAIN
from app.ui_helpers import ACCENT, BG_CARD, BORDER, TEXT_MUTED, TEXT_PRIMARY, logo_html, page_icon

st.set_page_config(page_title="Rank Tracker · Team Mamba", page_icon=page_icon(), layout="wide")

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
                    text-transform:uppercase;font-weight:600;">Telemetry</div>
      </div>
      <h1 style="margin:0 0 8px;font-size:1.7rem;color:{TEXT_PRIMARY};">
        📊 Rank Tracker
      </h1>
      <div style="color:{TEXT_MUTED};font-size:0.92rem;line-height:1.55;">
        Every <code>estimate_keyword_rank</code> call is logged here.
        Lower line = better rank. Gaps mean the domain wasn't in the top N.
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

init_db()

# manual check
with st.expander("➕ Add a manual rank check", expanded=False):
    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        kw = st.text_input("Keyword", value="")
    with col2:
        dom = st.text_input("Domain", value=DEFAULT_DOMAIN)
    with col3:
        depth = st.number_input("Depth", value=30, min_value=5, max_value=100, step=5)
    if st.button("Run rank check now", disabled=not (kw and dom)):
        with st.spinner("Querying DuckDuckGo…"):
            from tools.rank_tracker import estimate_keyword_rank
            r = estimate_keyword_rank.invoke({"keyword": kw, "domain": dom, "depth": int(depth)})
        pos = r.get('position') or f"not in top {depth}"
        st.success(f"Position: {pos} · matched: {r.get('matched_url') or '—'}")
        st.rerun()

# pick keyword
keywords = list_keywords()
if not keywords:
    st.info("No rank history yet. Either run the crew with a rank-tracking task, "
            "or add a manual check above.")
    st.stop()

selected = st.multiselect("Keywords to chart", keywords, default=keywords[:1])
if not selected:
    st.warning("Pick at least one keyword.")
    st.stop()

frames = []
for kw in selected:
    rows = history_for(kw)
    df = pd.DataFrame(rows)
    if df.empty:
        continue
    df["ts"] = pd.to_datetime(df["ts"])
    df["keyword"] = kw
    frames.append(df)

df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
if df.empty:
    st.info("No data points for the selected keywords yet.")
    st.stop()

chart_df = df.pivot_table(index="ts", columns="keyword", values="position", aggfunc="last")
st.line_chart(chart_df.rename_axis(None, axis=1))

st.write("")
st.markdown(
    f'<div style="font-size:0.78rem;color:{TEXT_MUTED};'
    f'text-transform:uppercase;letter-spacing:0.1em;margin-bottom:6px;">'
    f'Recent checks</div>',
    unsafe_allow_html=True,
)
st.dataframe(
    df.sort_values("ts", ascending=False)[["ts", "keyword", "domain", "position", "matched_url", "engine"]],
    use_container_width=True, hide_index=True,
)
