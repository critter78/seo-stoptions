"""🗂 Projects — manage every brand/client this dashboard runs SEO for.

Each project = one row in the `projects` table. The active project (picked
from the sidebar dropdown) scopes all data: reports, decisions, schedules,
costs, AEO, content, GSC, GA4. Per-project CLAUDE.md override lives here too.
"""
from __future__ import annotations

import re

import streamlit as st

from app.db import (
    active_project_id,
    add_project,
    archive_project,
    get_project,
    init_db,
    list_projects,
    set_default_project,
    update_project,
)
from app.ui_helpers import (
    ACCENT, BG_CARD, BORDER, TEXT_MUTED, TEXT_PRIMARY,
    empty_state_card, logo_html, severity_badge, stat_card,
)

init_db()

# ================================================================ hero
st.markdown(
    f"""
    <div style="background:linear-gradient(135deg,#0d1117 0%,#161B22 100%);
                border:1px solid {BORDER};border-radius:14px;
                padding:20px 24px;margin-bottom:24px;">
      <div style="display:flex;align-items:center;gap:14px;margin-bottom:6px;">
        {logo_html(height=36)}
        <div style="font-size:0.78rem;color:{ACCENT};letter-spacing:0.14em;
                    text-transform:uppercase;font-weight:600;">Multi-domain</div>
      </div>
      <h1 style="margin:0 0 8px;font-size:1.7rem;color:{TEXT_PRIMARY};">
        🗂 Projects
      </h1>
      <div style="color:{TEXT_MUTED};font-size:0.92rem;line-height:1.55;">
        One row per brand / client / domain. Switching the active project (top
        of sidebar) re-scopes every page — reports, decisions, schedules, costs,
        AEO, content, and GSC + GA4 connections.
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---- KPI row
projects = list_projects(include_archived=True)
active = [p for p in projects if p["status"] == "active"]
archived = [p for p in projects if p["status"] == "archived"]
cur_id = active_project_id()
cur_proj = next((p for p in projects if p["id"] == cur_id), None)

cols = st.columns(3)
with cols[0]:
    st.markdown(stat_card("Active projects", str(len(active)), icon="🟢"),
                unsafe_allow_html=True)
with cols[1]:
    st.markdown(stat_card("Archived", str(len(archived)), icon="📦"),
                unsafe_allow_html=True)
with cols[2]:
    st.markdown(stat_card("Currently viewing",
                          cur_proj["name"] if cur_proj else "—",
                          delta=cur_proj["domain"] if cur_proj else "",
                          delta_kind="neutral", icon="📍"),
                unsafe_allow_html=True)

st.write("")
st.markdown("---")

# ================================================================ add new
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,30}$")

with st.expander("➕ Add a new project", expanded=not active):
    col1, col2 = st.columns(2)
    with col1:
        np_name = st.text_input(
            "Display name",
            placeholder="e.g. Acme Corp",
            help="Shown in the sidebar dropdown.",
        )
        np_slug = st.text_input(
            "Slug (URL-safe)",
            placeholder="e.g. acme",
            help="Lowercase letters, numbers, hyphens. Used in the URL path "
                 "(/mgmt/{slug}) and in /reports/{slug}/ subfolder.",
        )
        np_domain = st.text_input("Domain", placeholder="acme.com")
        np_target = st.text_input("Target URL",
                                  placeholder="https://acme.com/")
    with col2:
        np_gsc = st.text_input(
            "GSC site (optional)",
            placeholder="sc-domain:acme.com",
            help="Use sc-domain: prefix for Domain properties, or full https URL "
                 "for URL-prefix properties.",
        )
        np_ga4 = st.text_input(
            "GA4 property ID (optional)",
            placeholder="123456789",
            help="9-digit numeric property ID — find it in GA4 admin.",
        )
        np_accent = st.color_picker(
            "Brand accent color", "#3DDC97",
            help="Used in per-project theming (future).",
        )
    np_claude_md = st.text_area(
        "Project context (CLAUDE.md override) — optional",
        height=120,
        placeholder=(
            "Per-project brand voice, audience, strategic priorities. "
            "Auto-injected into every agent's prompt when this project is active. "
            "Leave blank to inherit the shared CLAUDE.md."
        ),
    )

    can_save = (np_name and np_slug and np_domain and np_target
                and SLUG_RE.match(np_slug or ""))
    if not (np_slug or "") or SLUG_RE.match(np_slug or ""):
        slug_warning = ""
    else:
        slug_warning = (
            "❗ Slug must be lowercase letters/numbers/hyphens, 2–31 chars."
        )
    if slug_warning:
        st.warning(slug_warning)

    if st.button("Create project", type="primary", disabled=not can_save):
        try:
            new_id = add_project(
                slug=np_slug, name=np_name, domain=np_domain,
                target_url=np_target, gsc_site=np_gsc,
                ga4_property_id=np_ga4, claude_md=np_claude_md,
                accent_color=np_accent,
            )
            st.success(f"Created **{np_name}** (#{new_id}). "
                       f"Switch via the sidebar dropdown.")
            st.rerun()
        except Exception as e:  # noqa: BLE001
            st.error(f"Couldn't create: {e}")

st.markdown("---")

# ================================================================ projects list
if not projects:
    st.markdown(
        empty_state_card(
            icon="🗂",
            title="No projects yet",
            body=(
                "Add your first project above. It becomes the active project "
                "automatically, and every page (reports, decisions, schedules, "
                "costs) will be scoped to it."
            ),
        ),
        unsafe_allow_html=True,
    )
    st.stop()

st.subheader("Active projects")
for p in active:
    with st.container(border=True):
        c1, c2, c3 = st.columns([3, 2, 1])
        with c1:
            badges_html = ""
            if p.get("is_default"):
                badges_html += severity_badge("good", "Default")
            if cur_id == p["id"]:
                badges_html += " " + severity_badge("info", "Currently active")
            st.markdown(
                f"### {p['name']}  &nbsp; {badges_html}",
                unsafe_allow_html=True,
            )
            st.caption(
                f"slug=`{p['slug']}` · domain=`{p['domain']}` · "
                f"target=`{p['target_url']}`"
            )
            integ_bits = []
            if p.get("gsc_site"):
                integ_bits.append(f"🔵 GSC `{p['gsc_site']}`")
            if p.get("ga4_property_id"):
                integ_bits.append(f"🟡 GA4 `{p['ga4_property_id']}`")
            if p.get("claude_md"):
                integ_bits.append("📖 custom CLAUDE.md")
            if integ_bits:
                st.caption(" · ".join(integ_bits))
        with c2:
            if cur_id != p["id"]:
                if st.button("➜ Switch to", key=f"sw_{p['id']}",
                             use_container_width=True):
                    st.session_state.active_project_id = p["id"]
                    st.rerun()
            if not p.get("is_default"):
                if st.button("⭐ Make default", key=f"def_{p['id']}",
                             use_container_width=True):
                    set_default_project(p["id"])
                    st.rerun()
        with c3:
            if not p.get("is_default"):
                if st.button("📦 Archive", key=f"arc_{p['id']}",
                             use_container_width=True):
                    archive_project(p["id"])
                    st.success("Archived.")
                    st.rerun()

        with st.expander("✏️ Edit"):
            e1, e2 = st.columns(2)
            with e1:
                e_name = st.text_input("Name", value=p["name"],
                                        key=f"en_{p['id']}")
                e_domain = st.text_input("Domain", value=p["domain"],
                                          key=f"ed_{p['id']}")
                e_target = st.text_input("Target URL", value=p["target_url"],
                                          key=f"et_{p['id']}")
            with e2:
                e_gsc = st.text_input("GSC site", value=p.get("gsc_site", ""),
                                       key=f"eg_{p['id']}")
                e_ga4 = st.text_input("GA4 property ID",
                                       value=p.get("ga4_property_id", ""),
                                       key=f"ea_{p['id']}")
                e_accent = st.color_picker(
                    "Accent",
                    value=p.get("accent_color") or "#3DDC97",
                    key=f"eac_{p['id']}",
                )
            e_claude = st.text_area(
                "Project context (CLAUDE.md override)",
                value=p.get("claude_md") or "",
                height=120, key=f"ec_{p['id']}",
                help="Leave blank to inherit the shared CLAUDE.md.",
            )
            if st.button("Save changes", key=f"esave_{p['id']}",
                         type="primary"):
                update_project(
                    p["id"], name=e_name, domain=e_domain,
                    target_url=e_target, gsc_site=e_gsc,
                    ga4_property_id=e_ga4, claude_md=e_claude,
                    accent_color=e_accent,
                )
                st.success("Saved.")
                st.rerun()

if archived:
    st.markdown("---")
    with st.expander(f"📦 Archived ({len(archived)})"):
        for p in archived:
            cols = st.columns([4, 1])
            cols[0].markdown(f"**{p['name']}** · `{p['domain']}` · slug=`{p['slug']}`")
            if cols[1].button("♻️ Restore", key=f"rest_{p['id']}",
                              use_container_width=True):
                update_project(p["id"], status="active")
                st.rerun()
