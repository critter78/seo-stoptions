"""📋 PM — chat with Lindsay "Linz" Ritter about the backlog."""
from __future__ import annotations

import streamlit as st

from app.db import init_db, list_decisions, list_outreach
from app.ui_helpers import (
    ACCENT, BG_CARD, BORDER, TEXT_MUTED, TEXT_PRIMARY,
    avatar_html, logo_html,
)
from agents.personas import LINDSAY

st.markdown(
    f"""
    <div style="background:linear-gradient(135deg,#0d1117 0%,#161B22 100%);
                border:1px solid {BORDER};border-radius:14px;
                padding:20px 24px;margin-bottom:24px;">
      <div style="display:flex;align-items:center;gap:14px;margin-bottom:6px;">
        {logo_html(height=36)}
        <div style="font-size:0.78rem;color:{ACCENT};letter-spacing:0.14em;
                    text-transform:uppercase;font-weight:600;">PM</div>
      </div>
      <div style="display:flex;align-items:center;gap:14px;">
        {avatar_html(LINDSAY, size=56)}
        <div>
          <h1 style="margin:0;font-size:1.5rem;color:{TEXT_PRIMARY};line-height:1.1;">
            Lindsay "Linz" Ritter
          </h1>
          <div style="color:{TEXT_MUTED};font-size:0.85rem;">{LINDSAY.role}</div>
          <div style="color:{ACCENT};font-style:italic;font-size:0.85rem;margin-top:2px;">
            "{LINDSAY.tagline}"
          </div>
        </div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

init_db()
open_count = len(list_decisions(status="open"))
in_prog_count = len(list_decisions(status="in_progress"))
outreach_count = len(list_outreach())

c1, c2, c3 = st.columns(3)
c1.metric("Open decisions", open_count)
c2.metric("In progress", in_prog_count)
c3.metric("Outreach prospects", outreach_count)

st.markdown("---")
st.caption("Ask Linz anything about the backlog. Quick prompts:")

quick = [
    ("📊 Weekly status report",
     "Write me a weekly status report — what shipped, what's in progress (esp. stalled), "
     "top 5 next-up by ROI, and what I'd start next sprint."),
    ("🎯 Top 5 by ROI",
     "What are the top 5 open backlog items ranked by ROI (effort × impact)? "
     "Tell me who should own each and by when."),
    ("⏰ What's stalled?",
     "What decisions have been in_progress for more than 3 days? "
     "For each, tell me what's blocking it and how to unstick it."),
    ("📈 Close-the-loop",
     "What decisions were marked done in the last 14-28 days but don't have an outcome measured yet? "
     "Tell Cash to pull the rank/traffic data for each."),
]

if "pm_history" not in st.session_state:
    st.session_state.pm_history = []
if "pm_pending" not in st.session_state:
    st.session_state.pm_pending = None

cols = st.columns(2)
for i, (label, prompt) in enumerate(quick):
    with cols[i % 2]:
        if st.button(label, key=f"pmq_{i}", use_container_width=True):
            st.session_state.pm_pending = prompt
            st.rerun()

for role, content in st.session_state.pm_history:
    with st.chat_message(role):
        st.markdown(content)

typed = st.chat_input("Ask Linz anything about the backlog…")
prompt = typed or st.session_state.pm_pending
st.session_state.pm_pending = None

if prompt:
    st.session_state.pm_history.append(("user", prompt))
    with st.chat_message("user"):
        st.markdown(prompt)
    with st.chat_message("assistant"):
        with st.spinner("Linz is thinking…"):
            from agents.pm import run_pm
            reply = run_pm(prompt) or "(no response)"
        st.markdown(reply)
        st.session_state.pm_history.append(("assistant", reply))
