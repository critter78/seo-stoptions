"""Centralised configuration loader.

All env vars are read here exactly once. Other modules import the constants.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()  # no-op if .env is missing


def _materialise_json_token(env_name: str, tmp_name: str) -> str:
    """Allow OAuth token env vars to hold EITHER a file path (local dev) OR the
    raw JSON contents (Streamlit Cloud secrets, where you can only store strings
    not files). If the value starts with '{' we treat it as inline JSON, write
    it to a tempfile, and return that path. Otherwise we pass the value through
    unchanged. This lets the rest of the codebase keep calling
    Credentials.from_authorized_user_file(path) without modification.
    """
    raw = os.getenv(env_name, "").strip()
    if not raw:
        return ""
    if raw.startswith("{"):
        # Inline JSON content — write to a stable tmp path so refresh writes
        # land somewhere they can be re-read for the lifetime of this container.
        tmp_path = Path(tempfile.gettempdir()) / tmp_name
        tmp_path.write_text(raw, encoding="utf-8")
        # Update env var so downstream code reading os.getenv also sees the path.
        os.environ[env_name] = str(tmp_path)
        return str(tmp_path)
    return raw

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5")

GOOGLE_PAGESPEED_API_KEY = os.getenv("GOOGLE_PAGESPEED_API_KEY", "")
WEBPAGETEST_API_KEY = os.getenv("WEBPAGETEST_API_KEY", "")

# Search Console — two auth modes supported:
#   1. OAuth (recommended for single-operator setups) — GSC_OAUTH_TOKEN_JSON
#   2. Service account — GSC_SERVICE_ACCOUNT_JSON (multi-tenant / SaaS)
GSC_OAUTH_TOKEN_JSON = _materialise_json_token("GSC_OAUTH_TOKEN_JSON", "gsc-token.json")
GSC_SERVICE_ACCOUNT_JSON = _materialise_json_token("GSC_SERVICE_ACCOUNT_JSON", "gsc-service-account.json")
GSC_DEFAULT_SITE = os.getenv("GSC_DEFAULT_SITE", "https://stoptions.ai/")

DEFAULT_DOMAIN = os.getenv("DEFAULT_DOMAIN", "stoptions.ai")
DEFAULT_TARGET_URL = os.getenv("DEFAULT_TARGET_URL", "https://stoptions.ai/")

# Cost guardrails
MONTHLY_BUDGET_USD = float(os.getenv("MONTHLY_BUDGET_USD", "50") or 50)

# Notification routing — multiple channels supported
NOTIFY_EMAIL_TO = os.getenv("NOTIFY_EMAIL_TO", "")
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587") or 587)
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
SMTP_FROM = os.getenv("SMTP_FROM", "")
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")

# In-process scheduler
ENABLE_INPROC_SCHEDULER = (os.getenv("ENABLE_INPROC_SCHEDULER", "1") or "1") == "1"

# GA4
GA4_PROPERTY_ID = os.getenv("GA4_PROPERTY_ID", "")
GA4_OAUTH_TOKEN_JSON = _materialise_json_token("GA4_OAUTH_TOKEN_JSON", "ga4-token.json")

# AEO scoreboard — optional engine API keys
PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
SERPAPI_KEY = os.getenv("SERPAPI_KEY", "")   # for Google AI Overviews

USER_AGENT = (
    "Mozilla/5.0 (compatible; StoptionsAISEOBot/1.0; "
    "+https://stoptions.ai/) Python-Requests"
)

REQUEST_TIMEOUT = 20  # seconds


def status_summary() -> dict:
    """Return what's wired up — used by the Streamlit sidebar."""
    return {
        "Anthropic API": bool(ANTHROPIC_API_KEY),
        "Anthropic model": ANTHROPIC_MODEL,
        "PageSpeed Insights": bool(GOOGLE_PAGESPEED_API_KEY),
        "WebPageTest": bool(WEBPAGETEST_API_KEY),
        "Search Console": bool(GSC_OAUTH_TOKEN_JSON or GSC_SERVICE_ACCOUNT_JSON),
        "Google Analytics 4": bool(GA4_PROPERTY_ID and GA4_OAUTH_TOKEN_JSON),
        "Notifications": bool(NOTIFY_EMAIL_TO or SLACK_WEBHOOK_URL or DISCORD_WEBHOOK_URL),
        "Default domain": DEFAULT_DOMAIN,
    }
