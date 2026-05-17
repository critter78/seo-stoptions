"""The Crew — Team Mamba full roster."""
from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.ui_helpers import (
    ACCENT,
    BG_CARD,
    BORDER,
    TEXT_MUTED,
    TEXT_PRIMARY,
    crew_card_html,
    logo_html,
    page_icon,
    team_mamba_html,
)
from agents.personas import KIRA, CASH, MAYA, ROSTER, TEAM_ETHOS

st.set_page_config(page_title="The Crew · Team Mamba", page_icon=page_icon(), layout="wide")

st.markdown(
    """
    <style>
      .block-container { padding-top: 2.5rem; max-width: 1200px; }
      h1, h2, h3 { letter-spacing: -0.01em; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ----- hero
st.markdown(
    f"""
    <div style="background:linear-gradient(135deg,#0d1117 0%,#161B22 100%);
                border:1px solid {BORDER};border-radius:14px;
                padding:20px 24px;margin-bottom:24px;">
      <div style="display:flex;align-items:center;gap:14px;margin-bottom:6px;">
        {logo_html(height=40)}
        <div style="font-size:0.78rem;color:{ACCENT};letter-spacing:0.14em;
                    text-transform:uppercase;font-weight:600;">Team Mamba</div>
        {team_mamba_html(height=28)}
      </div>
      <h1 style="margin:0 0 8px;font-size:1.9rem;color:{TEXT_PRIMARY};">
        Meet the crew
      </h1>
      <div style="color:{TEXT_MUTED};font-size:0.95rem;line-height:1.55;">
        Three elite operators working on <strong style="color:{TEXT_PRIMARY};">
        https://stoptions.ai/</strong>. Mamba mentality — obsessive prep,
        no hedging, refuse to lose.
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ----- roster (three cards, equal height)
cols = st.columns(3, gap="medium")
for col, p in zip(cols, ROSTER):
    with col:
        st.markdown(crew_card_html(p), unsafe_allow_html=True)
        with st.expander("Voice samples"):
            st.markdown(p.voice_examples)

st.write("")
st.divider()

# ----- team ethos + workflow
left, right = st.columns([3, 2], gap="large")
with left:
    st.markdown("### Team ethos")
    st.markdown(TEAM_ETHOS)

with right:
    st.markdown("### How they work together")
    st.markdown(
        f"""
1. You drop a task into the main chat.
2. **{KIRA.full_name}** crawls, audits, queries SERPs, and assembles cited findings.
3. **{CASH.full_name}** reads Kira's brief and writes the executive-tight report with prioritised actions.
4. **{MAYA.full_name}** turns Cash's hand-off into outreach lists, content briefs, on-page rewrites, CTA copy, and a distribution plan.
5. The full report (all three sections) is saved to `/reports` and added to the **📂 Past Reports** archive.

Skip Maya from the sidebar if you only want research + analyst output.
"""
    )

st.divider()

# ----- portrait status
needs_portrait = [p for p in ROSTER if not p.has_portrait]
if needs_portrait:
    st.markdown(
        f"<div style='background:{BG_CARD};border:1px dashed {BORDER};"
        f"border-radius:10px;padding:14px 18px;color:{TEXT_MUTED};font-size:0.9rem;'>"
        f"📷 Still need portraits for: "
        f"<strong style='color:{TEXT_PRIMARY};'>"
        f"{', '.join(p.full_name for p in needs_portrait)}</strong>. "
        f"Drop a file as <code>assets/team/{needs_portrait[0].key}.png</code> "
        f"(or use the first-name shortcut, e.g. <code>cash.png</code>) "
        f"and refresh."
        f"</div>",
        unsafe_allow_html=True,
    )
