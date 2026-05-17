"""Stoptions.ai · Team Mamba — entry script.

Defines global page config, injects CSS, renders the persistent sidebar,
then dispatches to the selected page via st.navigation.
"""
from __future__ import annotations

import os

import streamlit as st

from app.config import (
    ANTHROPIC_API_KEY,
    DEFAULT_DOMAIN,
    DEFAULT_TARGET_URL,
    ENABLE_INPROC_SCHEDULER,
    MONTHLY_BUDGET_USD,
    status_summary,
)


# =============================================================================
# Sprint 7 follow-up: on Streamlit Cloud, bridge st.secrets into os.environ so
# the existing config code (os.getenv everywhere) works without modification.
# Local dev keeps reading from .env — st.secrets is empty there, no overrides.
# =============================================================================
try:
    for _k, _v in dict(st.secrets).items():
        if isinstance(_v, (str, int, float)) and not os.environ.get(_k):
            os.environ[_k] = str(_v)
except Exception:
    # No secrets.toml locally — that's normal
    pass

# =============================================================================
# Simple password gate when deployed publicly. Set APP_PASSWORD in Streamlit
# Cloud secrets (or .env locally). If unset, the gate is bypassed — local dev
# stays frictionless.
# =============================================================================
_APP_PASSWORD = os.getenv("APP_PASSWORD", "")
if not _APP_PASSWORD:
    # st.secrets only works when a secrets.toml exists or we're on Streamlit
    # Cloud. Touching it without a secrets file raises StreamlitSecretNotFoundError,
    # so guard with try/except.
    try:
        _APP_PASSWORD = st.secrets.get("APP_PASSWORD", "") or ""
    except Exception:
        _APP_PASSWORD = ""
if _APP_PASSWORD:
    if st.session_state.get("_authed") != _APP_PASSWORD:
        st.set_page_config(page_title="🔒 Critter Labs", layout="centered")
        st.markdown("# 🔒 Critter Labs · Stoptions.ai")
        st.caption("This dashboard is password-protected.")
        _pw = st.text_input("Password", type="password",
                            label_visibility="collapsed",
                            placeholder="Enter password")
        if st.button("Enter", type="primary", use_container_width=True):
            if _pw == _APP_PASSWORD:
                st.session_state._authed = _APP_PASSWORD
                st.rerun()
            else:
                st.error("Incorrect password.")
        st.stop()
from app.db import active_project_id, cost_totals, init_db, list_projects
from app.scheduler import sync_schedules
from app.ui_helpers import (
    ACCENT,
    TEXT_MUTED,
    TEXT_PRIMARY,
    logo_html,
    page_icon,
    sidebar_crew_row_html,
    status_pill_html,
    team_mamba_html,
)
from agents.personas import MAYA, ROSTER

# Boot the in-process scheduler once per Streamlit process and reconcile
# SQLite schedules onto APScheduler.
# Ensure projects table + multi-project migration runs at process start.
init_db()

if ENABLE_INPROC_SCHEDULER:
    try:
        sync_schedules()
    except Exception:
        pass  # never let scheduler boot crash the UI

# ================================================================ page config
st.set_page_config(
    page_title="Stoptions.ai · Team Mamba",
    page_icon=page_icon(),
    layout="wide",
    initial_sidebar_state="expanded",
)

# ================================================================ global CSS
st.markdown(
    """
    <style>
      /* Page */
      .block-container { padding-top: 2rem; max-width: 1100px; }
      h1, h2, h3 { letter-spacing: -0.01em; }

      /* Sidebar */
      [data-testid="stSidebar"] {
        background: #0d1117;
        border-right: 1px solid #21262D;
      }
      [data-testid="stSidebar"] .block-container { padding-top: 1rem; }
      [data-testid="stSidebar"] hr {
        margin: 14px 0;
        border: none;
        border-top: 1px solid #21262D;
      }

      /* Auto-page nav (Streamlit multipage) */
      [data-testid="stSidebarNav"] {
        background: transparent;
        padding-top: 4px;
        padding-bottom: 6px;
      }
      [data-testid="stSidebarNav"] ul { padding-left: 0; }
      [data-testid="stSidebarNav"] li a {
        border-radius: 8px;
        font-size: 0.9rem;
      }
      [data-testid="stSidebarNav"] li a:hover { background: #161B22; }
      [data-testid="stSidebarNavSeparator"] { border-color: #21262D; }

      /* Chat input */
      [data-testid="stChatInput"] {
        border-color: #30363D !important;
        background: #0d1117 !important;
      }

      /* Status widget */
      div[data-testid="stStatusWidget"] {
        background: #161B22 !important;
        border: 1px solid #30363D !important;
        border-radius: 10px !important;
      }

      /* Custom hero */
      .mamba-hero {
        background: linear-gradient(135deg, #0d1117 0%, #161B22 100%);
        border: 1px solid #30363D;
        border-radius: 14px;
        padding: 22px 26px;
        margin-bottom: 20px;
      }

      /* Quick-start buttons */
      div[data-testid="stButton"] > button {
        background: #161B22;
        border: 1px solid #30363D !important;
        color: #E6EDF3 !important;
        border-radius: 10px !important;
        padding: 14px 16px !important;
        font-weight: 500 !important;
        text-align: left !important;
        justify-content: flex-start !important;
        transition: all 0.15s ease;
        min-height: 56px;
      }
      div[data-testid="stButton"] > button:hover {
        background: #1c2330 !important;
        border-color: #3DDC97 !important;
        transform: translateY(-1px);
      }

      /* Link buttons (sidebar) */
      [data-testid="stSidebar"] div[data-testid="stLinkButton"] a {
        background: transparent !important;
        border: 1px solid #30363D !important;
        color: #E6EDF3 !important;
        font-size: 0.82rem !important;
        padding: 8px 12px !important;
        justify-content: space-between !important;
      }
      [data-testid="stSidebar"] div[data-testid="stLinkButton"] a:hover {
        border-color: #3DDC97 !important;
        background: #161B22 !important;
      }

      /* Section eyebrow utility */
      .sb-eyebrow {
        font-size: 0.7rem;
        color: #8B949E;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        font-weight: 600;
        margin: 14px 0 8px;
      }

      .sb-crew-card {
        background: #0E1117;
        border: 1px solid #21262D;
        border-radius: 12px;
        padding: 10px 12px;
      }
    </style>
    """,
    unsafe_allow_html=True,
)

# ================================================================ sidebar (persistent across pages)
with st.sidebar:
    # ---- project switcher (only renders if you have 2+ projects)
    _projects = list_projects()
    if len(_projects) >= 2:
        st.markdown(
            f'<div style="font-size:0.7rem;color:{TEXT_MUTED};text-transform:uppercase;'
            f'letter-spacing:0.1em;font-weight:600;margin:6px 0 4px;">Active project</div>',
            unsafe_allow_html=True,
        )
        _opts = {p["name"]: p["id"] for p in _projects}
        _current_id = active_project_id()
        _current_name = next(
            (n for n, pid in _opts.items() if pid == _current_id),
            list(_opts.keys())[0],
        )
        _picked_name = st.selectbox(
            "Active project",
            list(_opts.keys()),
            index=list(_opts.keys()).index(_current_name),
            label_visibility="collapsed",
            key="project_picker",
        )
        _picked_id = _opts[_picked_name]
        if _picked_id != _current_id:
            st.session_state.active_project_id = _picked_id
            st.rerun()
        st.markdown("<hr style='margin:8px 0 12px;'>", unsafe_allow_html=True)
    elif _projects:
        # Single-project install — still set session state so downstream
        # helpers always have a value.
        st.session_state.setdefault("active_project_id", _projects[0]["id"])

    # ---- brand block
    st.markdown(
        f"""
        <div style="padding:6px 4px 14px;border-bottom:1px solid #21262D;
                    margin-bottom:6px;">
          <div style="display:flex;align-items:center;gap:10px;">
            {logo_html(height=30)}
            <div style="font-size:1.1rem;font-weight:600;color:{TEXT_PRIMARY};
                        line-height:1;">Stoptions.ai</div>
          </div>
          <div style="display:flex;align-items:center;gap:8px;margin-top:8px;
                      padding-left:2px;">
            <span style="font-size:0.7rem;color:{ACCENT};letter-spacing:0.12em;
                         text-transform:uppercase;font-weight:600;">Team Mamba</span>
            {team_mamba_html(height=16)}
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ---- The Crew
    st.markdown('<div class="sb-eyebrow">The Crew</div>', unsafe_allow_html=True)
    crew_rows_html = "".join(sidebar_crew_row_html(p) for p in ROSTER)
    st.markdown(
        f'<div class="sb-crew-card">{crew_rows_html}</div>',
        unsafe_allow_html=True,
    )
    st.caption("Full bios → 👥 The Crew")

    # ---- System status
    st.markdown('<div class="sb-eyebrow">System</div>', unsafe_allow_html=True)
    status = status_summary()
    st.markdown(status_pill_html("Anthropic API", status["Anthropic API"],
                value=status["Anthropic model"]), unsafe_allow_html=True)
    st.markdown(status_pill_html("PageSpeed Insights", status["PageSpeed Insights"]),
                unsafe_allow_html=True)
    st.markdown(status_pill_html("WebPageTest", status["WebPageTest"],
                value="Pro plan only", optional=True),
                unsafe_allow_html=True)
    st.markdown(status_pill_html("Search Console", status["Search Console"]),
                unsafe_allow_html=True)
    st.markdown(status_pill_html("Google Analytics 4", status["Google Analytics 4"],
                optional=not status["Google Analytics 4"]),
                unsafe_allow_html=True)
    st.markdown(status_pill_html("Notifications", status["Notifications"],
                optional=not status["Notifications"]),
                unsafe_allow_html=True)
    st.markdown(status_pill_html("Target domain", True,
                value=status["Default domain"]), unsafe_allow_html=True)
    if not all([status["PageSpeed Insights"], status["Search Console"]]):
        st.caption("Wire missing keys → ⚙️ Setup")

    # Cost badge
    try:
        ct = cost_totals(days=30)
        if MONTHLY_BUDGET_USD:
            pct = ct["total_usd"] / MONTHLY_BUDGET_USD * 100
        else:
            pct = 0
        st.markdown(
            f'<div style="margin-top:8px;padding:6px 10px;background:#161B22;'
            f'border:1px solid {BORDER};border-radius:6px;font-size:0.78rem;'
            f'color:{TEXT_MUTED};">💰 30-day spend: '
            f'<strong style="color:{TEXT_PRIMARY};">${ct["total_usd"]:.2f}</strong>'
            f'{" / $" + str(int(MONTHLY_BUDGET_USD)) if MONTHLY_BUDGET_USD else ""}'
            f' ({pct:.0f}% of budget)</div>',
            unsafe_allow_html=True,
        )
    except Exception:
        pass

    # ---- Run controls
    st.markdown('<div class="sb-eyebrow">Run controls</div>', unsafe_allow_html=True)
    st.toggle(
        f"Skip {MAYA.full_name}",
        value=False, key="skip_marketer",
        help="Run only Kira (research) + Cash (analysis).",
    )
    st.toggle(
        "Auto-save reports",
        value=True, key="save_report",
        help="Every run is saved to /reports as Markdown.",
    )

    # ---- Defaults (collapsed)
    with st.expander("⚙️ Defaults", expanded=False):
        st.text_input("Domain", value=DEFAULT_DOMAIN, key="default_domain")
        st.text_input("Target URL", value=DEFAULT_TARGET_URL, key="default_target_url")

    # ---- External links
    st.markdown('<div class="sb-eyebrow">Quick links</div>', unsafe_allow_html=True)
    st.link_button("→  Stoptions.ai", "https://stoptions.ai/", use_container_width=True)
    st.link_button("→  Google Search Console", "https://search.google.com/search-console", use_container_width=True)
    st.link_button("→  Anthropic Console", "https://console.anthropic.com/", use_container_width=True)
    st.link_button("→  PageSpeed Insights", "https://pagespeed.web.dev/", use_container_width=True)

    # ---- footer
    st.markdown(
        f"""
        <div style="margin-top:24px;padding-top:14px;border-top:1px solid #21262D;
                    font-size:0.7rem;color:{TEXT_MUTED};text-align:center;
                    line-height:1.5;">
          Powered by Claude<br>
          <span style="color:#555;">LangGraph · Streamlit</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

# ================================================================ navigation
home = st.Page("app/views/home.py", title="Home", icon="🏠", default=True)
past_reports = st.Page("app/views/past_reports.py", title="Past Reports", icon="📂")
rank_tracker = st.Page("app/views/rank_tracker.py", title="Rank Tracker", icon="📊")
decisions = st.Page("app/views/decisions.py", title="Decisions", icon="🗂")
cost = st.Page("app/views/cost.py", title="Cost Tracker", icon="💰")
aeo = st.Page("app/views/aeo.py", title="AEO Scoreboard", icon="🔎")
schema = st.Page("app/views/schema.py", title="Schema Validator", icon="🧬")
content = st.Page("app/views/content.py", title="Content Calendar", icon="📝")
outreach = st.Page("app/views/outreach.py", title="Outreach", icon="📬")
the_crew = st.Page("app/views/the_crew.py", title="The Crew", icon="👥")
pm = st.Page("app/views/pm.py", title="PM (Linz)", icon="📋")
scheduled_runs = st.Page("app/views/scheduled_runs.py", title="Scheduled Runs", icon="⏰")
logs = st.Page("app/views/logs.py", title="Logs", icon="📜")
tools = st.Page("app/views/tools.py", title="Tools", icon="🛠")
setup = st.Page("app/views/setup.py", title="Setup & Integrations", icon="⚙️")
project_context = st.Page("app/views/project_context.py", title="Project Context", icon="📖")
projects = st.Page("app/views/projects.py", title="Projects", icon="🗂")
notebooks = st.Page("app/views/notebooks.py", title="Agent Notebooks", icon="📓")

nav = st.navigation(
    {
        "Dashboard": [home],
        "SEO ops": [past_reports, rank_tracker, decisions, aeo, schema],
        "Marketing": [content, outreach],
        "Team": [the_crew, pm, notebooks],
        "Automation": [scheduled_runs, logs],
        "Toolkit": [tools],
        "Settings": [projects, cost, setup, project_context],
    }
)
nav.run()
