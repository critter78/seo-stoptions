"""🔎 Kira "Recon" Nakamura — 1:1 chat with the SEO Researcher."""
from __future__ import annotations

import streamlit as st

from app.ui_helpers import (
    ACCENT, BORDER, TEXT_MUTED, TEXT_PRIMARY,
    avatar_html, logo_html,
)
from agents.personas import KIRA

st.markdown(
    f"""
    <div style="background:linear-gradient(135deg,#0d1117 0%,#161B22 100%);
                border:1px solid {BORDER};border-radius:14px;
                padding:20px 24px;margin-bottom:24px;">
      <div style="display:flex;align-items:center;gap:14px;margin-bottom:6px;">
        {logo_html(height=36)}
        <div style="font-size:0.78rem;color:{ACCENT};letter-spacing:0.14em;
                    text-transform:uppercase;font-weight:600;">SEO Researcher</div>
      </div>
      <div style="display:flex;align-items:center;gap:14px;">
        {avatar_html(KIRA, size=56)}
        <div>
          <h1 style="margin:0;font-size:1.5rem;color:{TEXT_PRIMARY};line-height:1.1;">
            Kira "Recon" Nakamura
          </h1>
          <div style="color:{TEXT_MUTED};font-size:0.85rem;">{KIRA.role}</div>
          <div style="color:{ACCENT};font-style:italic;font-size:0.85rem;margin-top:2px;">
            "{KIRA.tagline}"
          </div>
        </div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.caption("Ask Kira to investigate. She does SERPs, competitors, backlinks, keyword gaps. Quick prompts:")

quick = [
    ("🔎 SERP analysis",
     "Pull the top 10 SERP results for 'AI options trading' on google.com (USA). "
     "For each: title, URL, snippet, content type, and the one angle they're using "
     "that Stoptions.ai isn't covering yet."),
    ("🏟 Competitor scan",
     "Identify the 5 most credible direct competitors for Stoptions.ai right now. "
     "For each: their primary value prop, their top-ranking content, and one specific "
     "thing they're doing better than us."),
    ("🔗 Backlink opportunities",
     "Find sites linking to optionalpha.com, tastylive.com, or marketchameleon.com but "
     "NOT to stoptions.ai. Give me the top 10 prospects sorted by domain authority and "
     "topical relevance, with the existing competitor article they linked to."),
    ("🆕 Keyword gaps",
     "What keywords do our top competitors rank in the top 10 for that stoptions.ai "
     "doesn't rank on page 1 yet? Filter to commercial / informational intent only "
     "(skip brand queries). Top 20."),
]

if "kira_history" not in st.session_state:
    st.session_state.kira_history = []
if "kira_pending" not in st.session_state:
    st.session_state.kira_pending = None

cols = st.columns(2)
for i, (label, prompt) in enumerate(quick):
    with cols[i % 2]:
        if st.button(label, key=f"kiraq_{i}", use_container_width=True):
            st.session_state.kira_pending = prompt
            st.rerun()

for role, content in st.session_state.kira_history:
    with st.chat_message(role):
        st.markdown(content)

typed = st.chat_input("Ask Kira to research something…")
prompt = typed or st.session_state.kira_pending
st.session_state.kira_pending = None

if prompt:
    st.session_state.kira_history.append(("user", prompt))
    with st.chat_message("user"):
        st.markdown(prompt)
    with st.chat_message("assistant"):
        with st.spinner("Kira is on the field…"):
            from agents.researcher import run_researcher
            reply = run_researcher(prompt) or "(no response)"
        st.markdown(reply)
        st.session_state.kira_history.append(("assistant", reply))
