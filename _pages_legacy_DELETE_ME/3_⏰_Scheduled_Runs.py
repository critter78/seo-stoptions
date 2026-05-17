"""Scheduled crew runs — define cron-style schedules, generate the launchd /
cron snippet, persist them in SQLite for reference.

The actual execution is done by the host's scheduler (cron / launchd / systemd
timer / GitHub Actions) calling `python scheduled_run.py --schedule <id>`. We
do this rather than spin up our own scheduler thread so the runs are reliable
even when Streamlit is restarted.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.db import add_schedule, delete_schedule, init_db, list_schedules
from app.config import DEFAULT_DOMAIN, DEFAULT_TARGET_URL

st.set_page_config(page_title="Scheduled Runs", page_icon="⏰", layout="wide")
st.title("⏰ Scheduled Runs")
st.caption(
    "Define a recurring SEO crew task. The actual scheduling is done by the host's "
    "cron / launchd / systemd timer / GitHub Actions — we generate the snippet for you."
)

init_db()

# ---------- new schedule
with st.expander("➕ New scheduled run", expanded=True):
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

# ---------- existing schedules
st.divider()
st.subheader("Saved schedules")
schedules = list_schedules()

if not schedules:
    st.info("No schedules saved yet.")
else:
    for s in schedules:
        with st.container(border=True):
            st.markdown(f"**#{s['id']} — {s['name']}**")
            st.markdown(f"- Cron: `{s['cron']}`")
            st.markdown(f"- Skip marketer: `{bool(s['skip_marketer'])}`")
            st.markdown(f"- Prompt: _{s['prompt'][:200]}{'…' if len(s['prompt']) > 200 else ''}_")
            cmd = (
                f"cd {ROOT} && /usr/bin/env python3 scheduled_run.py --schedule {s['id']} "
                f">> {ROOT}/reports/cron.log 2>&1"
            )
            st.code(f"# crontab line:\n{s['cron']}  {cmd}", language="bash")
            if st.button("Delete", key=f"del_{s['id']}"):
                delete_schedule(s["id"])
                st.rerun()

st.divider()
st.subheader("How to wire it to your host's scheduler")
st.markdown("""
**Linux / Mac (cron):**
```bash
crontab -e
# paste the snippet shown above
```

**macOS launchd** — copy `launchd/com.stoptions.seo-crew.plist` (generated below)
into `~/Library/LaunchAgents/` then `launchctl load` it.

**Docker host:** add a sibling service to `docker-compose.yml`:
```yaml
  cron:
    image: stoptions/seo-crew:latest
    command: ["sh", "-c", "while true; do python scheduled_run.py --schedule 1; sleep 604800; done"]
    env_file: .env
    volumes:
      - ./reports:/app/reports
      - ./data:/app/data
```

**GitHub Actions** (runs in the cloud, free tier):
```yaml
on:
  schedule: [{cron: "0 8 * * 1"}]
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
```
""")
