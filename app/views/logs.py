"""📜 Logs — scheduled-run history with errors."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from app.db import init_db, recent_scheduler_runs
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
                    text-transform:uppercase;font-weight:600;">Diagnostics</div>
      </div>
      <h1 style="margin:0 0 8px;font-size:1.7rem;color:{TEXT_PRIMARY};">
        📜 Scheduler Logs
      </h1>
      <div style="color:{TEXT_MUTED};font-size:0.92rem;line-height:1.55;">
        Every scheduled run — success, errors, duration, cost. Drill into the trace
        when something fails at 8am.
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

init_db()
runs = recent_scheduler_runs(limit=200)
if not runs:
    st.markdown(
        empty_state_card(
            icon="📜",
            title="No scheduler runs yet",
            body=(
                "Every fired schedule lands here with status, duration, cost, and "
                "(when relevant) full error traces. Logs become invaluable when a 6am "
                "audit fails — you'll know exactly why."
            ),
            cta_helptext="↗ Configure a schedule on <strong>⏰ Scheduled Runs</strong> to start populating this log.",
        ),
        unsafe_allow_html=True,
    )
    st.stop()

filter_status = st.selectbox("Filter", ["all", "success", "error", "running"], index=0)
filtered = [r for r in runs if filter_status == "all" or r["status"] == filter_status]

st.caption(f"{len(filtered)} of {len(runs)} runs shown")

for r in filtered:
    icon = {"success": "✅", "error": "❌", "running": "🟡"}.get(r["status"], "•")
    dur = f"{r['duration_sec']:.0f}s" if r.get("duration_sec") else "—"
    cost = f"${r['cost_usd']:.3f}" if r.get("cost_usd") else "$0"
    with st.expander(f"{icon} {r['started_at'][:19]} — {r['name']} — "
                     f"{r['status']} · {dur} · {cost}"):
        cols = st.columns(4)
        cols[0].metric("Duration", dur)
        cols[1].metric("Cost", cost)
        cols[2].metric("Input tokens", f"{r.get('input_tokens', 0):,}")
        cols[3].metric("Output tokens", f"{r.get('output_tokens', 0):,}")
        if r.get("report_path"):
            st.caption(f"📄 Report: `{r['report_path']}`")
        if r["status"] == "error" and r.get("error_text"):
            st.error("Error trace:")
            st.code(r["error_text"])
