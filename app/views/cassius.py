"""🧠 Cassius "Cash" Reed — 1:1 chat with the Principal Technical SEO Analyst."""
from __future__ import annotations

import streamlit as st

from app.ui_helpers import (
    ACCENT, BORDER, TEXT_MUTED, TEXT_PRIMARY,
    avatar_html, logo_html,
)
from agents.personas import CASH

st.markdown(
    f"""
    <div style="background:linear-gradient(135deg,#0d1117 0%,#161B22 100%);
                border:1px solid {BORDER};border-radius:14px;
                padding:20px 24px;margin-bottom:24px;">
      <div style="display:flex;align-items:center;gap:14px;margin-bottom:6px;">
        {logo_html(height=36)}
        <div style="font-size:0.78rem;color:{ACCENT};letter-spacing:0.14em;
                    text-transform:uppercase;font-weight:600;">Principal Analyst</div>
      </div>
      <div style="display:flex;align-items:center;gap:14px;">
        {avatar_html(CASH, size=56)}
        <div>
          <h1 style="margin:0;font-size:1.5rem;color:{TEXT_PRIMARY};line-height:1.1;">
            Cassius "Cash" Reed
          </h1>
          <div style="color:{TEXT_MUTED};font-size:0.85rem;">{CASH.role}</div>
          <div style="color:{ACCENT};font-style:italic;font-size:0.85rem;margin-top:2px;">
            "{CASH.tagline}"
          </div>
        </div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.caption("Ask Cash for the diagnosis. He turns data into reports and ranked actions. Quick prompts:")

quick = [
    ("📊 Site health score",
     "Audit https://stoptions.ai/ end-to-end (on-page, schema, PageSpeed, mobile, "
     "links). Score it out of 100 with the deductions itemised. Tell me the single "
     "highest-leverage fix and the owner I should assign."),
    ("📈 Win/loss this week",
     "Compare this week's GSC clicks + ranks against the prior 7 days. List the "
     "top 5 winning queries and top 5 losing queries with click delta and average "
     "position delta. Explain what likely caused each."),
    ("🎯 ROI-ranked actions",
     "Take all open decisions in the backlog and rank them by ROI (impact ÷ effort). "
     "Give me top 10 with: rationale, expected lift, suggested owner, and rough "
     "deadline. Be specific."),
    ("📉 What broke?",
     "Compare today's Daily Health Check against the previous one. Surface every "
     "regression (rank drops, schema errors, PageSpeed degradations, indexation "
     "changes). For each: severity, likely root cause, fix plan."),
]

if "cash_history" not in st.session_state:
    st.session_state.cash_history = []
if "cash_pending" not in st.session_state:
    st.session_state.cash_pending = None

cols = st.columns(2)
for i, (label, prompt) in enumerate(quick):
    with cols[i % 2]:
        if st.button(label, key=f"cashq_{i}", use_container_width=True):
            st.session_state.cash_pending = prompt
            st.rerun()

for role, content in st.session_state.cash_history:
    with st.chat_message(role):
        st.markdown(content)

typed = st.chat_input("Ask Cash to analyze something…")
prompt = typed or st.session_state.cash_pending
st.session_state.cash_pending = None

if prompt:
    st.session_state.cash_history.append(("user", prompt))
    with st.chat_message("user"):
        st.markdown(prompt)
    with st.chat_message("assistant"):
        with st.spinner("Cash is writing the report…"):
            from agents.analyst import run_analyst
            reply = run_analyst(prompt) or "(no response)"
        st.markdown(reply)
        st.session_state.cash_history.append(("assistant", reply))
