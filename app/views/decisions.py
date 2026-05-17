"""🗂 Decisions — open backlog + wontfix log."""
from __future__ import annotations

import datetime as dt

import pandas as pd
import streamlit as st

from app.db import add_decision, init_db, list_decisions, update_decision_status
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
                    text-transform:uppercase;font-weight:600;">Backlog</div>
      </div>
      <h1 style="margin:0 0 8px;font-size:1.7rem;color:{TEXT_PRIMARY};">
        🗂 Decisions
      </h1>
      <div style="color:{TEXT_MUTED};font-size:0.92rem;line-height:1.55;">
        Open recommendations + their status. Agents auto-inject this list into every
        run so they never re-flag a <code>wontfix</code> or chase a closed item.
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

init_db()

with st.expander("➕ Add a decision manually", expanded=False):
    col1, col2 = st.columns([2, 1])
    with col1:
        d_title = st.text_input("Title", placeholder="e.g. Fix broken canonical on /blog/iron-condor")
        d_detail = st.text_area("Detail", height=80)
    with col2:
        d_target = st.text_input("Target URL or keyword", placeholder="https://stoptions.ai/...")
        d_effort = st.selectbox("Effort", ["", "S", "M", "L"], index=0)
        d_impact = st.selectbox("Impact", ["", "★", "★★", "★★★"], index=0)
    if st.button("Add to backlog", type="primary", disabled=not d_title):
        add_decision(d_title, detail=d_detail, target_url=d_target,
                     effort=d_effort, impact=d_impact)
        st.success("Added to backlog.")
        st.rerun()

st.markdown("---")

tabs = st.tabs(["📌 Open", "🛠 In progress", "✅ Done", "❄️ Snoozed", "🚫 Wontfix"])

for tab, status in zip(tabs,
                       ["open", "in_progress", "done", "snoozed", "wontfix"]):
    with tab:
        items = list_decisions(status=status)
        if not items:
            _hint = {
                "open": "Agents file new recommendations here automatically when they audit your site. You can also add items manually above.",
                "in_progress": "Move open items to in_progress when work starts. Anything stalled >7 days will surface on Linz's status report.",
                "done": "Items moved to done get measured by the agents at +14d and +28d to confirm the recommendation actually worked.",
                "snoozed": "Use snoozed for items you'll revisit later (e.g. waiting on a dev sprint).",
                "wontfix": "Wontfix items are remembered forever — agents won't re-flag them in future audits.",
            }.get(status, "")
            st.markdown(
                empty_state_card(
                    icon={"open":"📌","in_progress":"🛠","done":"✅","snoozed":"❄️","wontfix":"🚫"}[status],
                    title=f"Nothing in {status} right now",
                    body=_hint,
                ),
                unsafe_allow_html=True,
            )
            continue
        for d in items:
            with st.container(border=True):
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.markdown(
                        f"**#{d['id']} · {d['title']}**  \n"
                        f"<span style='color:{TEXT_MUTED};font-size:0.82rem'>"
                        f"effort {d.get('effort') or '?'} · impact {d.get('impact') or '?'} · "
                        f"created {d['created_at'][:10]}"
                        f"{(' · source: ' + d['source_report']) if d.get('source_report') else ''}"
                        f"</span>",
                        unsafe_allow_html=True,
                    )
                    if d.get("detail"):
                        st.caption(d["detail"])
                    if d.get("status_note"):
                        st.caption(f"_Note: {d['status_note']}_")
                with col2:
                    next_status = st.selectbox(
                        "Move to", ["", "open", "in_progress", "done", "snoozed", "wontfix"],
                        key=f"move_{d['id']}_{status}", label_visibility="collapsed",
                    )
                    if next_status and next_status != d["status"]:
                        note = st.text_input("Reason (optional)",
                                              key=f"note_{d['id']}_{status}",
                                              label_visibility="collapsed",
                                              placeholder="why?")
                        if st.button("Update", key=f"upd_{d['id']}_{status}"):
                            update_decision_status(d["id"], next_status, note)
                            st.rerun()
