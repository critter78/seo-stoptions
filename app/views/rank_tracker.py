"""Rank Tracker view."""
from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

from app.config import DEFAULT_DOMAIN
from app.db import history_for, init_db, list_keywords
from app.ui_helpers import (
    ACCENT, BORDER, TEXT_MUTED, TEXT_PRIMARY,
    empty_state_card, logo_html,
)

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

keywords = list_keywords()
if not keywords:
    st.markdown(
        empty_state_card(
            icon="📊",
            title="No rank history yet",
            body=(
                "Rank Tracker logs every <code>estimate_keyword_rank</code> call so you "
                "can chart position changes over time per keyword. To start, add a "
                "manual check above — or ask the crew to track a keyword on the Home page."
            ),
            cta_helptext="↑ Open <strong>Add a manual rank check</strong> above and enter a keyword to seed the first data point.",
        ),
        unsafe_allow_html=True,
    )
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
    st.markdown(
        empty_state_card(
            icon="📭",
            title="No data points yet for these keywords",
            body=(
                "The keywords are registered but no checks have been logged. "
                "Run a manual check above or wait for the next scheduled audit."
            ),
        ),
        unsafe_allow_html=True,
    )
    st.stop()

# --- Sprint 4.3: Altair line chart with inverted axis + hover tooltips
chart_df = df.copy()
# Use a sentinel for "not in top N" so the line breaks; chart hides nulls
chart_df["position_value"] = chart_df["position"].fillna(0).where(
    chart_df["position"].notna(), None,
)
line = (
    alt.Chart(chart_df)
    .mark_line(point=alt.OverlayMarkDef(size=70, filled=True))
    .encode(
        x=alt.X("ts:T", title="Date", axis=alt.Axis(format="%b %d", labelColor="#8B949E")),
        y=alt.Y(
            "position:Q",
            title="Position (lower is better)",
            scale=alt.Scale(reverse=True, domain=[1, 30], clamp=True),
            axis=alt.Axis(labelColor="#8B949E", grid=True, gridColor="#21262D"),
        ),
        color=alt.Color(
            "keyword:N",
            title="Keyword",
            scale=alt.Scale(scheme="set2"),
        ),
        tooltip=[
            alt.Tooltip("keyword:N", title="Keyword"),
            alt.Tooltip("ts:T", title="When", format="%b %d, %H:%M"),
            alt.Tooltip("position:Q", title="Position"),
            alt.Tooltip("matched_url:N", title="URL"),
        ],
    )
    .properties(height=320)
    .configure_view(strokeWidth=0)
    .configure_axis(domainColor="#30363D", tickColor="#30363D")
    .configure_legend(labelColor="#E6EDF3", titleColor="#8B949E")
)
st.altair_chart(line, use_container_width=True)

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
