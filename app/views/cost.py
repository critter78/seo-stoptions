"""💰 Cost — Anthropic token usage + monthly budget tracking."""
from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

from app.config import ANTHROPIC_MODEL, MONTHLY_BUDGET_USD
from app.db import cost_daily_series, cost_daily_series_by_agent, cost_totals, init_db
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
                    text-transform:uppercase;font-weight:600;">Spend</div>
      </div>
      <h1 style="margin:0 0 8px;font-size:1.7rem;color:{TEXT_PRIMARY};">
        💰 Anthropic Cost Tracker
      </h1>
      <div style="color:{TEXT_MUTED};font-size:0.92rem;line-height:1.55;">
        Every crew run's token usage is logged here.
        Model in use: <code>{ANTHROPIC_MODEL}</code>.
        Monthly budget alert at <code>${MONTHLY_BUDGET_USD:.2f}</code>.
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

init_db()
totals_30 = cost_totals(days=30)
totals_today = totals_30["today_usd"]
spent_30 = totals_30["total_usd"]
pct_budget = (spent_30 / MONTHLY_BUDGET_USD * 100) if MONTHLY_BUDGET_USD else 0

c1, c2, c3, c4 = st.columns(4)
c1.metric("Today (UTC)", f"${totals_today:.3f}")
c2.metric("Last 30 days", f"${spent_30:.2f}",
          delta=f"{pct_budget:.0f}% of monthly budget")
c3.metric("Total calls", f"{totals_30['call_count']:,}")
c4.metric("Tokens (in/out)",
          f"{totals_30['input_tokens']:,} / {totals_30['output_tokens']:,}")

if MONTHLY_BUDGET_USD and pct_budget >= 80:
    st.warning(
        f"⚠️ You've used **{pct_budget:.0f}%** of your monthly budget "
        f"(${MONTHLY_BUDGET_USD:.2f}). Consider raising MONTHLY_BUDGET_USD in `.env` "
        f"or pausing scheduled runs."
    )

st.markdown(
    f'<div style="font-size:0.78rem;color:{TEXT_MUTED};text-transform:uppercase;'
    f'letter-spacing:0.1em;margin:20px 0 6px;">Daily spend (last 30 days)</div>',
    unsafe_allow_html=True,
)
by_agent_series = cost_daily_series_by_agent(days=30)
if by_agent_series:
    df = pd.DataFrame(by_agent_series).rename(
        columns={"day": "Date", "s": "USD", "agent": "Agent"}
    )
    df["Date"] = pd.to_datetime(df["Date"])

    # Stacked-area chart by agent
    area = (
        alt.Chart(df)
        .mark_area(opacity=0.85)
        .encode(
            x=alt.X("Date:T", title=None,
                    axis=alt.Axis(format="%b %d", labelColor="#8B949E")),
            y=alt.Y("USD:Q", title="USD / day", stack="zero",
                    axis=alt.Axis(labelColor="#8B949E", grid=True,
                                  gridColor="#21262D")),
            color=alt.Color("Agent:N", scale=alt.Scale(scheme="tableau10")),
            tooltip=[
                alt.Tooltip("Agent:N"),
                alt.Tooltip("Date:T", format="%b %d"),
                alt.Tooltip("USD:Q", format="$.4f"),
            ],
        )
        .properties(height=260)
    )

    # Daily-equivalent budget reference line (monthly budget / 30)
    if MONTHLY_BUDGET_USD:
        daily_budget = MONTHLY_BUDGET_USD / 30
        rule = (
            alt.Chart(pd.DataFrame({"y": [daily_budget]}))
            .mark_rule(color="#F4B940", strokeDash=[4, 4], size=2)
            .encode(y="y:Q",
                    tooltip=alt.Tooltip("y:Q",
                                        title=f"Daily-equiv budget (${daily_budget:.3f})"))
        )
        chart = (area + rule)
    else:
        chart = area

    chart = (
        chart.configure_view(strokeWidth=0)
        .configure_axis(domainColor="#30363D", tickColor="#30363D")
        .configure_legend(labelColor="#E6EDF3", titleColor="#8B949E")
    )
    st.altair_chart(chart, use_container_width=True)
else:
    st.markdown(
        empty_state_card(
            icon="💸",
            title="No cost data yet",
            body=(
                "Anthropic token usage is logged on every crew run. Run the crew "
                "from the Home page or fire a scheduled run, and spend will appear here."
            ),
        ),
        unsafe_allow_html=True,
    )

st.markdown(
    f'<div style="font-size:0.78rem;color:{TEXT_MUTED};text-transform:uppercase;'
    f'letter-spacing:0.1em;margin:20px 0 6px;">By agent (last 30 days)</div>',
    unsafe_allow_html=True,
)
if totals_30["by_agent"]:
    df = pd.DataFrame(totals_30["by_agent"]).rename(
        columns={"agent": "Agent", "s": "USD", "n": "Calls"})
    df["USD"] = df["USD"].round(4)
    st.dataframe(df.sort_values("USD", ascending=False),
                 use_container_width=True, hide_index=True)
else:
    st.caption("Per-agent breakdown will populate after the first crew run.")
