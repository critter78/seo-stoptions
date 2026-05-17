"""CLI wrapper for running a saved schedule (or an ad-hoc prompt) from cron / launchd.

Usage:
    python scheduled_run.py --schedule 3
    python scheduled_run.py --prompt "Audit https://stoptions.ai/ for 'options trading'"
    python scheduled_run.py --prompt "..." --skip-marketer

Saves the resulting report to /reports/{ts}-scheduled.md and emits a JSON
summary on stdout for the cron log.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from app.db import list_schedules
from agents.graph import run_seo_crew


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--schedule", type=int, help="Run a saved schedule by ID")
    ap.add_argument("--prompt", help="Ad-hoc prompt (alternative to --schedule)")
    ap.add_argument("--skip-marketer", action="store_true")
    args = ap.parse_args()

    prompt = args.prompt
    skip_marketer = args.skip_marketer
    name = "adhoc"

    if args.schedule:
        schedules = {s["id"]: s for s in list_schedules()}
        s = schedules.get(args.schedule)
        if not s:
            print(json.dumps({"ok": False, "error": f"schedule {args.schedule} not found"}))
            sys.exit(1)
        prompt = s["prompt"]
        skip_marketer = bool(s["skip_marketer"])
        name = (s["name"] or "scheduled").lower().replace(" ", "-")[:40]

    if not prompt:
        ap.error("either --schedule or --prompt is required")

    ts = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = ROOT / "reports"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / f"{ts}-{name}.md"

    started = dt.datetime.utcnow().isoformat() + "Z"
    try:
        final = run_seo_crew(prompt, skip_marketer=skip_marketer)
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e), "trace": traceback.format_exc(), "started": started}))
        sys.exit(2)

    body = (
        f"# Scheduled crew run — {ts}\n\n"
        f"**Schedule:** {name}\n\n"
        f"**Prompt:** {prompt}\n\n---\n\n"
        f"## Research findings\n\n{final.get('research_findings','')}\n\n---\n\n"
        f"## Analyst report\n\n{final.get('analyst_report','')}\n\n"
    )
    if final.get("marketer_package"):
        body += f"\n---\n\n## Marketer package\n\n{final['marketer_package']}\n"
    out_path.write_text(body, encoding="utf-8")

    print(json.dumps({
        "ok": True,
        "started": started,
        "finished": dt.datetime.utcnow().isoformat() + "Z",
        "schedule": name,
        "report_path": str(out_path),
        "report_kb": out_path.stat().st_size // 1024,
    }))


if __name__ == "__main__":
    main()
