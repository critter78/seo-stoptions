"""📬 Outreach — Maya's prospect pipeline."""
from __future__ import annotations

import streamlit as st

from app.db import add_outreach, init_db, list_outreach, update_outreach_status
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
                    text-transform:uppercase;font-weight:600;">Link Building</div>
      </div>
      <h1 style="margin:0 0 8px;font-size:1.7rem;color:{TEXT_PRIMARY};">
        📬 Outreach Pipeline
      </h1>
      <div style="color:{TEXT_MUTED};font-size:0.92rem;line-height:1.55;">
        Track every prospect from queued → contacted → replied → link placed.
        Maya generates the prospect lists; you manage the pipeline here.
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

init_db()

with st.expander("➕ Add a prospect manually", expanded=False):
    col1, col2 = st.columns(2)
    with col1:
        purl = st.text_input("Prospect URL", placeholder="https://...")
        pname = st.text_input("Prospect / publication name")
        region = st.selectbox("Region", ["", "US", "EU", "UK", "CA", "AU", "APAC"])
    with col2:
        angle = st.text_input("Angle", placeholder="unlinked mention, broken link, guest post…")
        email = st.text_input("Contact email")
    pitch = st.text_area("Pitch template / notes", height=100)
    if st.button("Add prospect", type="primary", disabled=not purl):
        add_outreach(prospect_url=purl, prospect_name=pname, region=region,
                     angle=angle, pitch_template=pitch, contact_email=email)
        st.success("Added to queue.")
        st.rerun()

st.markdown("---")

STAGES = ["queued", "contacted", "no_reply", "replied", "placed", "declined"]
tabs = st.tabs(["📋 Queued", "📤 Contacted", "🔇 No reply",
                "💬 Replied", "🔗 Placed", "❌ Declined"])

for tab, status in zip(tabs, STAGES):
    with tab:
        items = list_outreach(status=status)
        if not items:
            _hint = {
                "queued": "Add prospects manually above, or ask Maya to generate a prospect list from the Home page.",
                "contacted": "Move prospects here once you've sent the pitch. Linz flags anything that's gone 6+ days without a reply.",
                "no_reply": "Prospects who didn't respond after follow-up. Worth re-pitching with a fresh angle in 60–90 days.",
                "replied": "They wrote back. Either move to placed (link landed) or declined (they passed).",
                "placed": "Live backlinks. Track placed_url so Cash can monitor referral traffic + DR uplift.",
                "declined": "They said no. Keep the record so you don't pitch them again in 6 months.",
            }.get(status, "")
            st.markdown(
                empty_state_card(
                    icon={"queued":"📋","contacted":"📤","no_reply":"🔇","replied":"💬","placed":"🔗","declined":"❌"}[status],
                    title=f"Nothing in {status}",
                    body=_hint,
                ),
                unsafe_allow_html=True,
            )
            continue
        for o in items:
            with st.container(border=True):
                col1, col2 = st.columns([4, 1])
                with col1:
                    name = o.get("prospect_name") or o["prospect_url"]
                    st.markdown(f"**#{o['id']} · [{name}]({o['prospect_url']})**")
                    meta = []
                    if o.get("region"):
                        meta.append(f"🌍 {o['region']}")
                    if o.get("angle"):
                        meta.append(f"🎯 {o['angle']}")
                    if o.get("contact_email"):
                        meta.append(f"✉️ {o['contact_email']}")
                    if o.get("contacted_at"):
                        meta.append(f"contacted {o['contacted_at'][:10]}")
                    if o.get("replied_at"):
                        meta.append(f"replied {o['replied_at'][:10]}")
                    if o.get("placed_url"):
                        meta.append(f"placed: [{o['placed_url']}]({o['placed_url']})")
                    if meta:
                        st.caption(" · ".join(meta))
                    if o.get("pitch_template"):
                        with st.expander("Pitch / notes"):
                            st.markdown(o["pitch_template"])
                    if o.get("status_note"):
                        st.caption(f"_Note: {o['status_note']}_")
                with col2:
                    next_status = st.selectbox(
                        "Move to", [""] + STAGES,
                        key=f"omv_{o['id']}_{status}",
                        label_visibility="collapsed",
                    )
                    placed_url = ""
                    if next_status == "placed":
                        placed_url = st.text_input("Placed URL", key=f"opu_{o['id']}_{status}",
                                                    placeholder="https://...",
                                                    label_visibility="collapsed")
                    note = st.text_input("Note", key=f"on_{o['id']}_{status}",
                                         placeholder="optional",
                                         label_visibility="collapsed")
                    if next_status and next_status != o["status"]:
                        if st.button("Update", key=f"oupd_{o['id']}_{status}"):
                            update_outreach_status(o["id"], next_status, note, placed_url)
                            st.rerun()
