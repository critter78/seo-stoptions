"""🔎 AEO Scoreboard — track citation rate across AI engines."""
from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

from app.config import (
    ANTHROPIC_API_KEY,
    GEMINI_API_KEY,
    OPENAI_API_KEY,
    PERPLEXITY_API_KEY,
    SERPAPI_KEY,
)
from app.db import aeo_citation_history, init_db
from app.ui_helpers import (
    ACCENT, BG_CARD, BORDER, TEXT_MUTED, TEXT_PRIMARY,
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
                    text-transform:uppercase;font-weight:600;">Answer Engine Optimization</div>
      </div>
      <h1 style="margin:0 0 8px;font-size:1.7rem;color:{TEXT_PRIMARY};">
        🔎 AEO Scoreboard
      </h1>
      <div style="color:{TEXT_MUTED};font-size:0.92rem;line-height:1.55;">
        Track when stoptions.ai is cited by AI answer engines (Claude, Gemini,
        Perplexity, ChatGPT, Google AI Overviews) for priority queries.
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

init_db()

# Engine config status
engines_status = {
    "claude": bool(ANTHROPIC_API_KEY),
    "perplexity": bool(PERPLEXITY_API_KEY),
    "chatgpt": bool(OPENAI_API_KEY),
    "gemini": bool(GEMINI_API_KEY),
    "google_ai_overview": bool(SERPAPI_KEY),
}
cols = st.columns(5)
for col, (eng, ok) in zip(cols, engines_status.items()):
    label = {"claude": "Claude", "perplexity": "Perplexity", "chatgpt": "ChatGPT",
             "gemini": "Gemini", "google_ai_overview": "Google AI Overview"}[eng]
    col.markdown(
        f'<div style="text-align:center;padding:8px;background:{BG_CARD};'
        f'border:1px solid {BORDER};border-radius:8px;font-size:0.8rem;">'
        f'<div style="color:{"#3DDC97" if ok else "#6E7681"};font-size:1.2rem;">'
        f'{"●" if ok else "○"}</div>{label}</div>',
        unsafe_allow_html=True,
    )

st.markdown("---")

# Run a check
with st.expander("🔎 Run a citation check now", expanded=True):
    col1, col2 = st.columns([3, 1])
    with col1:
        q = st.text_input("Query", placeholder="best AI options trading platforms")
    with col2:
        st.write("")
        run = st.button("Check engines", type="primary", disabled=not q,
                        use_container_width=True)
    if run:
        enabled_engines = [e for e, ok in engines_status.items() if ok]
        if not enabled_engines:
            st.error("No engines configured. Add at least one API key in `.env`.")
        else:
            with st.spinner(f"Querying {len(enabled_engines)} engine(s)…"):
                from tools.aeo_scoreboard import check_ai_citations
                result = check_ai_citations.invoke({
                    "query": q,
                    "our_domains": ["stoptions.ai"],
                    "engines": enabled_engines,
                })
            summary = result.get("summary", {})
            st.success(
                f"**Citation rate: {summary.get('citation_rate_pct', 0)}%**  ·  "
                f"cited in {summary.get('engines_citing_us', 0)} / "
                f"{summary.get('engines_tested', 0)} engines"
            )
            for eng, r in result.get("results", {}).items():
                with st.container(border=True):
                    status = "✅ CITED" if r.get("cited") else "❌ not cited"
                    st.markdown(f"**{eng.upper()}** — {status} (count: {r.get('count', 0)})")
                    if r.get("citations_returned"):
                        st.caption("Sources returned: " + ", ".join(r["citations_returned"][:5]))
                    if r.get("response_preview"):
                        with st.expander("Response preview"):
                            st.markdown(r["response_preview"])
                    if r.get("error"):
                        st.error(r["error"])

st.markdown("---")

# Historical citation chart
history = aeo_citation_history(days=30)
if not history:
    st.markdown(
        empty_state_card(
            icon="🔎",
            title="No citation history yet",
            body=(
                "AEO history charts daily citation rate per engine over time, plus a "
                "per-query breakdown. The chart populates as you accumulate checks — "
                "run one above to seed the first data point."
            ),
            cta_helptext="↑ Use <strong>🔎 Run a citation check now</strong> with a priority query to start tracking.",
        ),
        unsafe_allow_html=True,
    )
else:
    df = pd.DataFrame(history)
    df["ts"] = pd.to_datetime(df["ts"])
    df["day"] = df["ts"].dt.date

    # ---- Leaderboard: cumulative citation rate per engine -----------------
    leaderboard = (
        df.groupby("engine")
          .agg(checks=("cited", "size"), cited=("cited", "sum"))
          .reset_index()
    )
    leaderboard["rate_pct"] = (leaderboard["cited"] / leaderboard["checks"] * 100).round(1)
    leaderboard = leaderboard.sort_values("rate_pct", ascending=True)

    st.markdown(
        f'<div style="font-size:0.78rem;color:{TEXT_MUTED};text-transform:uppercase;'
        f'letter-spacing:0.1em;margin:8px 0 6px;">🏆 Engine leaderboard — citation rate</div>',
        unsafe_allow_html=True,
    )
    bar = (
        alt.Chart(leaderboard)
        .mark_bar(cornerRadiusEnd=4)
        .encode(
            x=alt.X("rate_pct:Q", title="Citation rate (%)",
                    scale=alt.Scale(domain=[0, 100]),
                    axis=alt.Axis(labelColor="#8B949E", grid=True, gridColor="#21262D")),
            y=alt.Y("engine:N", title=None, sort="-x",
                    axis=alt.Axis(labelColor="#E6EDF3", labelFontSize=12)),
            color=alt.Color("rate_pct:Q", scale=alt.Scale(scheme="viridis"), legend=None),
            tooltip=[
                alt.Tooltip("engine:N", title="Engine"),
                alt.Tooltip("rate_pct:Q", title="Rate (%)", format=".1f"),
                alt.Tooltip("cited:Q", title="Cited"),
                alt.Tooltip("checks:Q", title="Checks"),
            ],
        )
        .properties(height=max(120, 38 * len(leaderboard)))
        .configure_view(strokeWidth=0)
        .configure_axis(domainColor="#30363D", tickColor="#30363D")
    )
    st.altair_chart(bar, use_container_width=True)

    # ---- Citation rate over time ------------------------------------------
    st.markdown(
        f'<div style="font-size:0.78rem;color:{TEXT_MUTED};text-transform:uppercase;'
        f'letter-spacing:0.1em;margin:20px 0 6px;">Daily citation rate by engine (%)</div>',
        unsafe_allow_html=True,
    )
    daily = (
        df.groupby(["day", "engine"])
          .agg(rate=("cited", "mean"))
          .reset_index()
    )
    daily["rate_pct"] = (daily["rate"] * 100).round(1)
    line = (
        alt.Chart(daily)
        .mark_line(point=alt.OverlayMarkDef(size=50, filled=True))
        .encode(
            x=alt.X("day:T", title=None,
                    axis=alt.Axis(format="%b %d", labelColor="#8B949E")),
            y=alt.Y("rate_pct:Q", title="Citation rate (%)",
                    scale=alt.Scale(domain=[0, 100]),
                    axis=alt.Axis(labelColor="#8B949E", grid=True, gridColor="#21262D")),
            color=alt.Color("engine:N", scale=alt.Scale(scheme="set2")),
            tooltip=[
                alt.Tooltip("engine:N"),
                alt.Tooltip("day:T", format="%b %d"),
                alt.Tooltip("rate_pct:Q", format=".1f"),
            ],
        )
        .properties(height=240)
        .configure_view(strokeWidth=0)
        .configure_axis(domainColor="#30363D", tickColor="#30363D")
        .configure_legend(labelColor="#E6EDF3", titleColor="#8B949E")
    )
    st.altair_chart(line, use_container_width=True)

    # Per-query breakdown
    st.markdown(
        f'<div style="font-size:0.78rem;color:{TEXT_MUTED};text-transform:uppercase;'
        f'letter-spacing:0.1em;margin:20px 0 6px;">Recent checks</div>',
        unsafe_allow_html=True,
    )
    show = df.sort_values("ts", ascending=False)[
        ["ts", "query", "engine", "cited", "citation_count"]
    ].head(50)
    show["cited"] = show["cited"].map({1: "✅", 0: "❌"})
    st.dataframe(show, use_container_width=True, hide_index=True)
