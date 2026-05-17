"""Outbound notifications — email (SMTP) + Slack + Discord webhooks.

Fires when a Daily KPI Snapshot or Weekly Full Audit finds 🔴 Critical issues.
All channels are optional — config any combination via .env.
"""
from __future__ import annotations

import smtplib
import ssl
from email.mime.text import MIMEText
from typing import List, Optional

import requests

from app.config import (
    DISCORD_WEBHOOK_URL,
    NOTIFY_EMAIL_TO,
    SLACK_WEBHOOK_URL,
    SMTP_FROM,
    SMTP_HOST,
    SMTP_PASS,
    SMTP_PORT,
    SMTP_USER,
)


def notify(
    subject: str,
    body_markdown: str,
    severity: str = "critical",
    extra_email_recipients: Optional[List[str]] = None,
) -> dict:
    """Fan out to every configured channel. Returns {channel: ok|error}."""
    results: dict = {}

    # Email
    recipients = [r.strip() for r in NOTIFY_EMAIL_TO.split(",") if r.strip()]
    if extra_email_recipients:
        recipients.extend(extra_email_recipients)
    if recipients and SMTP_HOST and SMTP_FROM:
        try:
            msg = MIMEText(body_markdown, "plain", "utf-8")
            msg["Subject"] = f"[{severity.upper()}] {subject}"
            msg["From"] = SMTP_FROM
            msg["To"] = ", ".join(recipients)
            ctx = ssl.create_default_context()
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as s:
                s.starttls(context=ctx)
                if SMTP_USER:
                    s.login(SMTP_USER, SMTP_PASS)
                s.sendmail(SMTP_FROM, recipients, msg.as_string())
            results["email"] = f"ok ({len(recipients)} recipients)"
        except Exception as e:
            results["email"] = f"error: {e}"

    # Slack
    if SLACK_WEBHOOK_URL:
        try:
            colour = {"critical": "#F85149", "warning": "#F4B940",
                      "info": "#3DDC97"}.get(severity, "#8B949E")
            payload = {
                "attachments": [{
                    "color": colour,
                    "title": f"[{severity.upper()}] {subject}",
                    "text": body_markdown[:3900],
                    "footer": "Stoptions.ai · Team Mamba",
                }]
            }
            r = requests.post(SLACK_WEBHOOK_URL, json=payload, timeout=10)
            results["slack"] = "ok" if r.ok else f"http {r.status_code}"
        except Exception as e:
            results["slack"] = f"error: {e}"

    # Discord
    if DISCORD_WEBHOOK_URL:
        try:
            colour_int = {"critical": 0xF85149, "warning": 0xF4B940,
                          "info": 0x3DDC97}.get(severity, 0x8B949E)
            payload = {
                "embeds": [{
                    "title": f"[{severity.upper()}] {subject}",
                    "description": body_markdown[:3900],
                    "color": colour_int,
                    "footer": {"text": "Stoptions.ai · Team Mamba"},
                }]
            }
            r = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
            results["discord"] = "ok" if r.status_code < 300 else f"http {r.status_code}"
        except Exception as e:
            results["discord"] = f"error: {e}"

    if not results:
        return {"skipped": "no channels configured"}
    return results


def configured_channels() -> List[str]:
    chans = []
    if NOTIFY_EMAIL_TO and SMTP_HOST and SMTP_FROM:
        chans.append("email")
    if SLACK_WEBHOOK_URL:
        chans.append("slack")
    if DISCORD_WEBHOOK_URL:
        chans.append("discord")
    return chans
