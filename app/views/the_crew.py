"""The Crew view — Team Mamba full roster."""
from __future__ import annotations

import streamlit as st

from app.ui_helpers import (
    ACCENT,
    BG_CARD,
    BORDER,
    TEXT_MUTED,
    TEXT_PRIMARY,
    crew_card_html,
    logo_html,
    team_mamba_html,
)
from agents.personas import KIRA, CASH, MAYA, LINDSAY, ROSTER, TEAM_ETHOS

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
        Four elite operators working on <strong style="color:{TEXT_PRIMARY};">
        https://stoptions.ai/</strong>. Mamba mentality — obsessive prep,
        no hedging, refuse to lose.
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ----- roster (cards, 3 per row so portraits stay readable)
def _render_card(p):
    st.markdown(crew_card_html(p), unsafe_allow_html=True)
    with st.expander("Voice samples"):
        st.markdown(p.voice_examples)


per_row = 3
for row_start in range(0, len(ROSTER), per_row):
    row = ROSTER[row_start:row_start + per_row]
    cols = st.columns(per_row, gap="medium")
    for col, p in zip(cols, row):
        with col:
            _render_card(p)
    # leave any trailing columns in the last row empty for a clean grid

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
6. **{LINDSAY.full_name}** ("{LINDSAY.nickname}") is on-call — ping her from the **📋 PM** page for backlog status, stalled work, or a weekly status report.

Skip Maya from the sidebar if you only want research + analyst output.
"""
    )

st.divider()

needs_portrait = [p for p in ROSTER if not p.has_portrait]
if needs_portrait:
    st.markdown(
        f"<div style='background:{BG_CARD};border:1px dashed {BORDER};"
        f"border-radius:10px;padding:14px 18px;color:{TEXT_MUTED};font-size:0.9rem;'>"
        f"📷 Still need portraits for: "
        f"<strong style='color:{TEXT_PRIMARY};'>"
        f"{', '.join(p.full_name for p in needs_portrait)}</strong>. "
        f"Drop a file as <code>assets/team/{needs_portrait[0].key}.png</code> "
        f"and refresh."
        f"</div>",
        unsafe_allow_html=True,
    )
