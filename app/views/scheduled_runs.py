"""Scheduled Runs view — cron-style scheduler with seed templates."""
from __future__ import annotations

from pathlib import Path

import streamlit as st

from app.config import DEFAULT_TARGET_URL, ENABLE_INPROC_SCHEDULER
from app.db import (
    add_schedule,
    delete_schedule,
    init_db,
    last_run_for,
    list_schedules,
    recent_scheduler_runs,
    seed_default_schedules,
)
from app.scheduler import get_scheduler, job_next_run, run_schedule_now, sync_schedules
from app.ui_helpers import (
    ACCENT, BG_CARD, BORDER, TEXT_MUTED, TEXT_PRIMARY,
    empty_state_card, logo_html,
)

ROOT = Path(__file__).resolve().parent.parent.parent

st.markdown(
    f"""
    <div style="background:linear-gradient(135deg,#0d1117 0%,#161B22 100%);
                border:1px solid {BORDER};border-radius:14px;
                padding:20px 24px;margin-bottom:24px;">
      <div style="display:flex;align-items:center;gap:14px;margin-bottom:6px;">
        {logo_html(height=36)}
        <div style="font-size:0.78rem;color:{ACCENT};letter-spacing:0.14em;
                    text-transform:uppercase;font-weight:600;">Automation</div>
      </div>
      <h1 style="margin:0 0 8px;font-size:1.7rem;color:{TEXT_PRIMARY};">
        ⏰ Scheduled Runs
      </h1>
      <div style="color:{TEXT_MUTED};font-size:0.92rem;line-height:1.55;">
        Recurring crew tasks. Two defaults seeded for you. Execution is done by
        your host's cron / launchd / GitHub Actions calling <code>scheduled_run.py</code>.
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

init_db()
seeded = seed_default_schedules()
if seeded:
    st.success(
        "✨ Seeded two default schedules: **Daily KPI Snapshot** and **Weekly Full Audit**."
    )

# Ensure APScheduler knows about current SQLite schedules
sync_result = sync_schedules()
if sync_result.get("enabled"):
    sched = get_scheduler()
    n = sync_result.get("registered", 0)
    st.info(
        f"⚡ **In-process scheduler is running** — {n} schedule"
        f"{'s' if n != 1 else ''} registered. "
        "Cron fires automatically while this Streamlit process is alive."
    )
else:
    st.warning(
        "Scheduler is disabled (`ENABLE_INPROC_SCHEDULER=0`). "
        "Schedules will only fire via host cron / launchd / GitHub Actions."
    )

with st.expander("➕ New scheduled run", expanded=False):
    name = st.text_input("Name", value="Weekly stoptions.ai audit")
    prompt = st.text_area(
        "Prompt to send to the crew",
        value=f"Audit {DEFAULT_TARGET_URL} for the keyword 'AI options trading' "
              f"and produce the full report + marketing package.",
        height=100,
    )
    cron = st.text_input("Cron expression (UTC)", value="0 8 * * 1",
                         help="Minute Hour Day Month DayOfWeek — e.g. '0 8 * * 1' = Mondays at 08:00 UTC")
    skip_marketer = st.checkbox("Skip SEO Marketer (research + analyst only)", value=False)
    if st.button("Save schedule"):
        sid = add_schedule(name=name, cron=cron, prompt=prompt, skip_marketer=skip_marketer)
        st.success(f"Saved schedule #{sid}")
        st.rerun()

st.divider()
st.subheader("Saved schedules")
schedules = list_schedules()

if not schedules:
    st.markdown(
        empty_state_card(
            icon="⏰",
            title="No schedules saved yet",
            body=(
                "Schedules run the crew automatically on a cron expression. The two "
                "defaults — Daily KPI Snapshot and Weekly Full Audit — should be seeded "
                "for you. Otherwise, expand <em>New scheduled run</em> above to create your first."
            ),
            cta_helptext="↑ Open <strong>➕ New scheduled run</strong> to add a recurring crew task.",
        ),
        unsafe_allow_html=True,
    )
else:
    for s in schedules:
        with st.container(border=True):
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown(f"**#{s['id']} — {s['name']}**")
                st.markdown(f"- Cron (UTC): `{s['cron']}`  ·  Skip marketer: `{bool(s['skip_marketer'])}`")
                next_run = job_next_run(s["id"]) if ENABLE_INPROC_SCHEDULER else None
                if next_run:
                    st.markdown(f"- ⏭ **Next run:** {next_run.strftime('%Y-%m-%d %H:%M UTC')}")
                last = last_run_for(s["id"])
                if last:
                    icon = {"success": "✅", "running": "🟡", "error": "❌"}.get(last["status"], "•")
                    dur = f" ({last['duration_sec']:.0f}s)" if last.get("duration_sec") else ""
                    cost = f" · ${last['cost_usd']:.3f}" if last.get("cost_usd") else ""
                    st.markdown(f"- {icon} **Last run:** {last['started_at'][:16]} — "
                                f"{last['status']}{dur}{cost}")
                    if last["status"] == "error" and last.get("error_text"):
                        with st.expander("Error trace"):
                            st.code(last["error_text"])
                preview = s['prompt'][:240] + ('…' if len(s['prompt']) > 240 else '')
                st.caption(f"Prompt: _{preview}_")

            with col2:
                if st.button("⚡ Run now", key=f"run_{s['id']}", use_container_width=True):
                    if run_schedule_now(s["id"]):
                        st.success("Queued — will run in a few seconds.")
                    else:
                        st.error("Scheduler not running or schedule not registered.")
                if st.button("🗑 Delete", key=f"del_{s['id']}", use_container_width=True):
                    delete_schedule(s["id"])
                    sync_schedules()
                    st.rerun()

st.markdown("---")
st.subheader("Recent runs (last 50)")
recent = recent_scheduler_runs(limit=50)
if recent:
    import pandas as pd
    df = pd.DataFrame(recent)[["started_at", "name", "status", "duration_sec",
                                "cost_usd", "report_path", "error_text"]]
    df = df.rename(columns={
        "started_at": "Started", "name": "Schedule", "status": "Status",
        "duration_sec": "Sec", "cost_usd": "USD",
        "report_path": "Report", "error_text": "Error",
    })
    st.dataframe(df, use_container_width=True, hide_index=True)
else:
    st.caption("Recent runs will appear here after the first scheduled fire.")

st.divider()
with st.expander("📖 How to wire it to your host's scheduler", expanded=False):
    st.markdown("""
**Linux / macOS (cron):**
```bash
crontab -e
# paste the snippet shown above each schedule
```

**macOS launchd** — wraps cron syntax in a `.plist`. Use [launched](https://launched.zerowidth.com) for an easy generator, or copy from the existing `scheduled_run.py` invocation.

**Docker host:** add a sibling service to `docker-compose.yml`:
```yaml
  cron:
    image: stoptions-ai/seo-crew:latest
    command: ["sh", "-c", "while true; do python scheduled_run.py --schedule 1; sleep 86400; done"]
    env_file: .env
    volumes:
      - ./reports:/app/reports
      - ./data:/app/data
```

**GitHub Actions** (runs in the cloud, free tier):
```yaml
on:
  schedule: [{cron: "0 8 * * *"}]
jobs:
  run-crew:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: {python-version: "3.11"}
      - run: pip install -r requirements.txt
      - run: python scheduled_run.py --schedule 1
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          GOOGLE_PAGESPEED_API_KEY: ${{ secrets.GOOGLE_PAGESPEED_API_KEY }}
```
""")
