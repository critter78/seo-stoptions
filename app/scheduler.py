"""In-process APScheduler that fires saved schedules on their cron expressions.

Singleton — `get_scheduler()` returns the same BackgroundScheduler across all
Streamlit reruns. On boot we call `sync_schedules()` to read SQLite and (re)register
every enabled schedule as a CronTrigger job.

Each job runs `scheduled_run.py` logic in-process (via `run_seo_crew`), saves the
report to /reports, logs start/finish + cost to scheduler_runs, and fires
notifications if the resulting report has critical issues.
"""
from __future__ import annotations

import datetime as dt
import re
import sys
import traceback
from pathlib import Path
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import ENABLE_INPROC_SCHEDULER
from app.db import (
    finish_scheduler_run,
    list_schedules,
    start_scheduler_run,
)
from app.notifications import notify, configured_channels

ROOT = Path(__file__).resolve().parent.parent
REPORTS_DIR = ROOT / "reports"
sys.path.insert(0, str(ROOT))

_scheduler: Optional[BackgroundScheduler] = None
_registered_ids: set = set()


def _parse_cron(expr: str) -> Optional[CronTrigger]:
    """Convert a 5-field cron expression to an APScheduler CronTrigger."""
    parts = (expr or "").split()
    if len(parts) != 5:
        return None
    minute, hour, day, month, day_of_week = parts
    try:
        return CronTrigger(
            minute=minute, hour=hour, day=day, month=month,
            day_of_week=day_of_week, timezone="UTC",
        )
    except Exception:
        return None


def _run_schedule_job(schedule_id: int, name: str, prompt: str, skip_marketer: bool):
    """Job callable — runs the crew, persists results + cost, fires notifications."""
    run_id = start_scheduler_run(schedule_id, name)
    started = dt.datetime.utcnow()
    try:
        # Lazy import to avoid heavy boot when scheduler not used
        from agents.graph import run_seo_crew

        final = run_seo_crew(prompt, skip_marketer=skip_marketer)

        # Save report
        REPORTS_DIR.mkdir(exist_ok=True)
        ts = started.strftime("%Y%m%d-%H%M%S")
        slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:40]
        out_path = REPORTS_DIR / f"{ts}-{slug}.md"
        body = (
            f"# Scheduled crew run — {ts} — {name}\n\n"
            f"**Prompt:** {prompt}\n\n---\n\n"
            f"## Research findings\n\n{final.get('research_findings','')}\n\n---\n\n"
            f"## Analyst report\n\n{final.get('analyst_report','')}\n\n"
        )
        if final.get("marketer_package"):
            body += f"\n---\n\n## Marketer package\n\n{final['marketer_package']}\n"
        out_path.write_text(body, encoding="utf-8")

        finish_scheduler_run(run_id, status="success", report_path=str(out_path))

        # Fire notifications on critical issues
        report_text = final.get("analyst_report", "")
        if _has_critical_issues(report_text) and configured_channels():
            crit = _extract_critical_block(report_text)
            notify(
                subject=f"{name} — critical issues found",
                body_markdown=(
                    f"Schedule **{name}** finished and flagged critical issues:\n\n"
                    f"{crit}\n\n---\n\nFull report saved to: `{out_path.name}`"
                ),
                severity="critical",
            )
    except Exception as e:
        finish_scheduler_run(
            run_id, status="error", error_text=f"{e}\n{traceback.format_exc()[:2000]}",
        )


_CRITICAL_HEADER_RE = re.compile(r"^##\s*🔴\s*Critical", re.MULTILINE | re.IGNORECASE)


def _has_critical_issues(report_text: str) -> bool:
    if not report_text:
        return False
    m = _CRITICAL_HEADER_RE.search(report_text)
    if not m:
        return False
    # Grab the section after the header — if it has any non-placeholder bullets, fire
    after = report_text[m.end():]
    next_section = re.search(r"^##\s", after, re.MULTILINE)
    block = after[: next_section.start()] if next_section else after
    bullets = [
        ln.strip("-* ").strip()
        for ln in block.splitlines()
        if ln.strip().startswith(("-", "*"))
    ]
    placeholders = {"", "(none)", "none", "—", "-", "n/a", "na"}
    real = [b for b in bullets if b.lower() not in placeholders]
    return len(real) > 0


def _extract_critical_block(report_text: str) -> str:
    m = _CRITICAL_HEADER_RE.search(report_text)
    if not m:
        return ""
    after = report_text[m.end():]
    next_section = re.search(r"^##\s", after, re.MULTILINE)
    return after[: next_section.start()].strip() if next_section else after.strip()


def get_scheduler() -> Optional[BackgroundScheduler]:
    global _scheduler
    if not ENABLE_INPROC_SCHEDULER:
        return None
    if _scheduler is None:
        _scheduler = BackgroundScheduler(timezone="UTC", daemon=True)
        _scheduler.start()
    return _scheduler


def sync_schedules() -> dict:
    """Reconcile SQLite schedules with APScheduler. Idempotent."""
    sched = get_scheduler()
    if sched is None:
        return {"enabled": False, "registered": 0}

    desired_ids: set = set()
    registered_now: list = []
    skipped: list = []

    for s in list_schedules():
        if not s.get("enabled", 1):
            continue
        sid = s["id"]
        trig = _parse_cron(s["cron"])
        if not trig:
            skipped.append({"id": sid, "name": s["name"], "reason": "bad cron"})
            continue
        job_id = f"schedule_{sid}"
        desired_ids.add(sid)

        sched.add_job(
            _run_schedule_job, trigger=trig, id=job_id, replace_existing=True,
            kwargs={
                "schedule_id": sid, "name": s["name"], "prompt": s["prompt"],
                "skip_marketer": bool(s["skip_marketer"]),
            },
            max_instances=1, coalesce=True, misfire_grace_time=600,
        )
        registered_now.append({"id": sid, "name": s["name"], "cron": s["cron"]})

    # Remove jobs that aren't in SQLite anymore
    for job in list(sched.get_jobs()):
        if job.id.startswith("schedule_"):
            try:
                jid = int(job.id.split("_", 1)[1])
                if jid not in desired_ids:
                    sched.remove_job(job.id)
            except Exception:
                pass

    global _registered_ids
    _registered_ids = desired_ids
    return {
        "enabled": True,
        "registered": len(registered_now),
        "schedules": registered_now,
        "skipped": skipped,
    }


def job_next_run(schedule_id: int) -> Optional[dt.datetime]:
    sched = get_scheduler()
    if sched is None:
        return None
    job = sched.get_job(f"schedule_{schedule_id}")
    return getattr(job, "next_run_time", None) if job else None


def run_schedule_now(schedule_id: int) -> bool:
    """Fire a saved schedule immediately (without waiting for its cron)."""
    sched = get_scheduler()
    if sched is None:
        return False
    job = sched.get_job(f"schedule_{schedule_id}")
    if job is None:
        return False
    job.modify(next_run_time=dt.datetime.now(dt.timezone.utc))
    return True
