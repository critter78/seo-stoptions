"""⚙️ Project Context — edit CLAUDE.md from the dashboard."""
from __future__ import annotations

import streamlit as st

from app.project_context import CONTEXT_PATH, load_context, save_context
from app.ui_helpers import ACCENT, BORDER, TEXT_MUTED, TEXT_PRIMARY, logo_html

st.markdown(
    f"""
    <div style="background:linear-gradient(135deg,#0d1117 0%,#161B22 100%);
                border:1px solid {BORDER};border-radius:14px;
                padding:20px 24px;margin-bottom:24px;">
      <div style="display:flex;align-items:center;gap:14px;margin-bottom:6px;">
        {logo_html(height=36)}
        <div style="font-size:0.78rem;color:{ACCENT};letter-spacing:0.14em;
                    text-transform:uppercase;font-weight:600;">Knowledge</div>
      </div>
      <h1 style="margin:0 0 8px;font-size:1.7rem;color:{TEXT_PRIMARY};">
        ⚙️ Project Context (CLAUDE.md)
      </h1>
      <div style="color:{TEXT_MUTED};font-size:0.92rem;line-height:1.55;">
        This Markdown file is <strong>auto-injected into every agent's system prompt</strong>.
        Add brand voice, tech stack, strategic priorities, things-to-avoid — anything
        that should persist across every run. Saved at <code>{CONTEXT_PATH}</code>.
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

current = load_context()
edited = st.text_area("CLAUDE.md", value=current, height=600, label_visibility="collapsed")

col1, col2 = st.columns([1, 5])
with col1:
    if st.button("💾 Save", type="primary"):
        save_context(edited)
        st.success("Saved. Agents will pick up the new context on their next build.")
        st.rerun()
with col2:
    st.caption(f"Length: {len(edited):,} chars · ~{len(edited)//4:,} tokens")
