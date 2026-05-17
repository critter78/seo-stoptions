"""📣 Maya Vega — 1:1 chat with the SEO Marketer."""
from __future__ import annotations

import streamlit as st

from app.ui_helpers import (
    ACCENT, BORDER, TEXT_MUTED, TEXT_PRIMARY,
    avatar_html, logo_html,
)
from agents.personas import MAYA

st.markdown(
    f"""
    <div style="background:linear-gradient(135deg,#0d1117 0%,#161B22 100%);
                border:1px solid {BORDER};border-radius:14px;
                padding:20px 24px;margin-bottom:24px;">
      <div style="display:flex;align-items:center;gap:14px;margin-bottom:6px;">
        {logo_html(height=36)}
        <div style="font-size:0.78rem;color:{ACCENT};letter-spacing:0.14em;
                    text-transform:uppercase;font-weight:600;">SEO Marketer</div>
      </div>
      <div style="display:flex;align-items:center;gap:14px;">
        {avatar_html(MAYA, size=56)}
        <div>
          <h1 style="margin:0;font-size:1.5rem;color:{TEXT_PRIMARY};line-height:1.1;">
            Maya Vega
          </h1>
          <div style="color:{TEXT_MUTED};font-size:0.85rem;">{MAYA.role}</div>
          <div style="color:{ACCENT};font-style:italic;font-size:0.85rem;margin-top:2px;">
            "{MAYA.tagline}"
          </div>
        </div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.caption("Ask Maya to ship the package — outreach, posts, distribution. Quick prompts:")

quick = [
    ("📬 Outreach pitch",
     "Draft a personalised outreach pitch for a backlink to stoptions.ai. Reference "
     "something specific the prospect has published. Tell me: subject line, 2 short "
     "paragraph body, one ask. Plain text, no fluff. Pick the prospect yourself "
     "from the most promising open opportunity in our pipeline."),
    ("🔁 Re-engagement",
     "Look at the outreach pipeline. Which prospects were contacted >7 days ago but "
     "haven't replied? For each, write a 2-sentence follow-up that's not pushy and "
     "gives them a new reason to respond."),
    ("📝 LinkedIn post",
     "Take the most recent Daily Health Check insight and turn it into a LinkedIn "
     "post for intermediate-to-advanced retail option traders. Hook first line, "
     "150-200 words, no hashtags spam, one concrete data point, one CTA to "
     "stoptions.ai."),
    ("🎯 5 audience hooks",
     "For the next content piece on Stoptions.ai (you pick the topic), give me 5 "
     "headline + hook angles tailored to: (1) day traders, (2) swing traders, "
     "(3) IV/vol traders, (4) wheel sellers, (5) hedgers. One sentence each."),
]

if "maya_history" not in st.session_state:
    st.session_state.maya_history = []
if "maya_pending" not in st.session_state:
    st.session_state.maya_pending = None

cols = st.columns(2)
for i, (label, prompt) in enumerate(quick):
    with cols[i % 2]:
        if st.button(label, key=f"mayaq_{i}", use_container_width=True):
            st.session_state.maya_pending = prompt
            st.rerun()

for role, content in st.session_state.maya_history:
    with st.chat_message(role):
        st.markdown(content)

typed = st.chat_input("Ask Maya to write or distribute something…")
prompt = typed or st.session_state.maya_pending
st.session_state.maya_pending = None

if prompt:
    st.session_state.maya_history.append(("user", prompt))
    with st.chat_message("user"):
        st.markdown(prompt)
    with st.chat_message("assistant"):
        with st.spinner("Maya is loading the package…"):
            from agents.marketer import run_marketer
            reply = run_marketer(prompt) or "(no response)"
        st.markdown(reply)
        st.session_state.maya_history.append(("assistant", reply))
