"""Home view — hero, Morning Briefing, Quick Starts, chat."""
from __future__ import annotations

import datetime as dt
import traceback
from pathlib import Path

import streamlit as st

from app.briefing import (
    compare_health_reports,
    latest_report_for,
    parse_health_score,
    parse_top_action,
    previous_report_for,
    rank_movers,
    time_ago,
)
from app.config import ANTHROPIC_API_KEY, DEFAULT_DOMAIN, DEFAULT_TARGET_URL
from app.ui_helpers import (
    ACCENT,
    BG_CARD,
    BORDER,
    TEXT_MUTED,
    TEXT_PRIMARY,
    empty_state_card,
    logo_html,
    progress_line_html,
    stat_card,
    team_mamba_html,
)
from agents.personas import KIRA, CASH, MAYA

REPORTS_DIR = Path(__file__).resolve().parent.parent.parent / "reports"

# session-state values set by sidebar widgets (entry script)
domain = st.session_state.get("default_domain", DEFAULT_DOMAIN)
target_url = st.session_state.get("default_target_url", DEFAULT_TARGET_URL)
skip_marketer = st.session_state.get("skip_marketer", False)
save_report = st.session_state.get("save_report", True)

if "history" not in st.session_state:
    st.session_state.history = []
if "pending_prompt" not in st.session_state:
    st.session_state.pending_prompt = None

# ==================================================================== hero
st.markdown(
    f"""
    <div class="mamba-hero" style="padding:18px 22px;">
      <div style="display:flex;align-items:center;justify-content:space-between;gap:14px;">
        <div style="display:flex;align-items:center;gap:12px;">
          {logo_html(height=36)}
          <div>
            <h1 style="margin:0;font-size:1.4rem;color:{TEXT_PRIMARY};line-height:1.15;">
              Stoptions.ai SEO Crew
            </h1>
            <div style="display:flex;align-items:center;gap:6px;margin-top:2px;">
              <span style="font-size:0.7rem;color:{ACCENT};letter-spacing:0.12em;
                          text-transform:uppercase;font-weight:600;">Team Mamba</span>
              {team_mamba_html(height=14)}
              <span style="color:{TEXT_MUTED};font-size:0.8rem;margin-left:6px;">
                · Trial signups → PRO+ subs → organic growth
              </span>
            </div>
          </div>
        </div>
        <div style="text-align:right;font-size:0.75rem;color:{TEXT_MUTED};
                    line-height:1.4;max-width:240px;">
          🌍 USA → EU → UK → CA → AU → APAC
        </div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ==================================================================== morning briefing
def _render_morning_briefing():
    latest = latest_report_for("daily-health-check")
    if not latest:
        st.markdown(
            empty_state_card(
                icon="🌅",
                title="Morning Briefing — no data yet",
                body=(
                    "Run the Daily Health Check below to seed the first briefing. "
                    "Wire it to <strong>⏰ Scheduled Runs</strong> for an automated "
                    "snapshot every morning."
                ),
            ),
            unsafe_allow_html=True,
        )
        if st.button("⚡ Run Daily Health Check now", key="run_dhc_empty",
                     use_container_width=True, type="primary"):
            from app.db import DAILY_HEALTH_CHECK_PROMPT
            st.session_state.pending_prompt = DAILY_HEALTH_CHECK_PROMPT
            st.rerun()
        st.write("")
        return

    score = parse_health_score(latest)
    top_action = parse_top_action(latest)
    movers = rank_movers(top_n=5)
    ran_at = dt.datetime.fromtimestamp(latest.stat().st_mtime)
    previous = previous_report_for("daily-health-check")
    diff = compare_health_reports(latest, previous) if previous else None

    # ---- Sprint 4: Stat-card snapshot row above the briefing ----
    from app.db import cost_totals
    try:
        spend_30 = cost_totals(days=30)
        spend_today = spend_30["today_usd"]
    except Exception:
        spend_30 = {"total_usd": 0}
        spend_today = 0

    up_movers = sum(1 for m in movers if m.get("delta", 0) > 0)
    down_movers = sum(1 for m in movers if m.get("delta", 0) < 0)
    score_delta_str = ""
    score_delta_kind = "neutral"
    if diff and diff.score_delta is not None and diff.score_delta != 0:
        score_delta_str = f"{abs(diff.score_delta)} pts vs last check"
        score_delta_kind = "up" if diff.score_delta > 0 else "down"

    cards = [
        stat_card(
            "Health score",
            f"{score}/100" if score is not None else "—",
            delta=score_delta_str,
            delta_kind=score_delta_kind,
            icon="🩺",
        ),
        stat_card(
            "Rank movers",
            f"{up_movers + down_movers}",
            delta=f"▲{up_movers}  ▼{down_movers}",
            delta_kind="up" if up_movers > down_movers else ("down" if down_movers > up_movers else "neutral"),
            icon="📊",
        ),
        stat_card(
            "Last run",
            time_ago(ran_at),
            delta=ran_at.strftime("%b %d · %H:%M"),
            delta_kind="neutral",
            icon="🕐",
        ),
        stat_card(
            "30-day spend",
            f"${spend_30.get('total_usd', 0):.2f}",
            delta=f"today: ${spend_today:.2f}",
            delta_kind="neutral",
            icon="💰",
        ),
    ]
    cols = st.columns(4, gap="small")
    for col, html in zip(cols, cards):
        with col:
            st.markdown(html, unsafe_allow_html=True)
    st.write("")

    if score is None:
        score_html = '<span style="color:#8B949E;font-size:1.6rem;font-weight:600;">—</span>'
        score_color = "#8B949E"
    else:
        if score >= 90:
            score_color = "#3DDC97"
        elif score >= 70:
            score_color = "#F4B940"
        else:
            score_color = "#F85149"
        score_html = (
            f'<span style="color:{score_color};font-size:2.4rem;font-weight:700;'
            f'line-height:1;">{score}</span>'
            f'<span style="color:{TEXT_MUTED};font-size:0.9rem;">/100</span>'
        )

    movers_html = ""
    if movers:
        rows = []
        for m in movers:
            arrow = "▲" if m["delta"] > 0 else "▼"
            color = "#3DDC97" if m["delta"] > 0 else "#F85149"
            from_str = m["from"] if m["from"] is not None else "—"
            to_str = m["to"] if m["to"] is not None else "out"
            rows.append(
                f'<div style="display:flex;align-items:center;gap:8px;'
                f'padding:4px 0;font-size:0.85rem;">'
                f'<span style="color:{color};font-weight:600;width:34px;">'
                f'{arrow} {abs(m["delta"])}</span>'
                f'<span style="color:{TEXT_PRIMARY};flex:1;'
                f'overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">'
                f'{m["keyword"]}</span>'
                f'<span style="color:{TEXT_MUTED};font-size:0.78rem;">'
                f'{from_str} → {to_str}</span>'
                f'</div>'
            )
        movers_html = "".join(rows)
    else:
        movers_html = (
            f'<div style="color:{TEXT_MUTED};font-size:0.85rem;">'
            f'No rank movement yet — keep running checks to build history.</div>'
        )

    action_html = (
        f'<div style="margin-top:10px;padding:10px 12px;background:{ACCENT}1F;'
        f'border-left:3px solid {ACCENT};border-radius:6px;color:{TEXT_PRIMARY};'
        f'font-size:0.88rem;line-height:1.5;">'
        f'<strong style="color:{ACCENT};">Top action today:</strong> {top_action}'
        f'</div>'
        if top_action
        else ""
    )

    # ---- Diff vs last check
    diff_html = ""
    if diff:
        parts = []

        # Score delta chip
        if diff.score_delta is not None:
            arrow = "▲" if diff.score_delta > 0 else ("▼" if diff.score_delta < 0 else "▶")
            color = "#3DDC97" if diff.score_delta > 0 else ("#F85149" if diff.score_delta < 0 else "#8B949E")
            parts.append(
                f'<div style="display:flex;align-items:center;gap:6px;'
                f'padding:4px 10px;background:{color}1F;border-radius:6px;">'
                f'<span style="color:{color};font-weight:600;">'
                f'{arrow} {abs(diff.score_delta)} pts</span>'
                f'<span style="color:{TEXT_MUTED};font-size:0.78rem;">score</span>'
                f'</div>'
            )
        # New / resolved counts
        if diff.new_issues:
            parts.append(
                f'<div style="display:flex;align-items:center;gap:6px;'
                f'padding:4px 10px;background:#F851491F;border-radius:6px;">'
                f'<span style="color:#F85149;font-weight:600;">+ {len(diff.new_issues)}</span>'
                f'<span style="color:{TEXT_MUTED};font-size:0.78rem;">new</span>'
                f'</div>'
            )
        if diff.resolved_issues:
            parts.append(
                f'<div style="display:flex;align-items:center;gap:6px;'
                f'padding:4px 10px;background:#3DDC971F;border-radius:6px;">'
                f'<span style="color:#3DDC97;font-weight:600;">− {len(diff.resolved_issues)}</span>'
                f'<span style="color:{TEXT_MUTED};font-size:0.78rem;">resolved</span>'
                f'</div>'
            )

        if parts:
            chips_html = (
                f'<div style="display:flex;flex-wrap:wrap;gap:8px;align-items:center;">'
                f'{"".join(parts)}'
                f'</div>'
            )
            # New issue bullets (max 3)
            new_list = ""
            if diff.new_issues:
                items = "".join(
                    f'<li style="margin:2px 0;color:{TEXT_PRIMARY};">{i}</li>'
                    for i in diff.new_issues[:3]
                )
                more = (f'<li style="color:{TEXT_MUTED};font-size:0.8rem;">'
                        f'…and {len(diff.new_issues) - 3} more</li>'
                        if len(diff.new_issues) > 3 else "")
                new_list = (
                    f'<div style="margin-top:8px;">'
                    f'<div style="font-size:0.72rem;color:#F85149;text-transform:uppercase;'
                    f'letter-spacing:0.08em;font-weight:600;margin-bottom:4px;">'
                    f'🆕 New issues</div>'
                    f'<ul style="margin:0;padding-left:18px;font-size:0.85rem;line-height:1.5;">'
                    f'{items}{more}</ul></div>'
                )
            resolved_list = ""
            if diff.resolved_issues:
                items = "".join(
                    f'<li style="margin:2px 0;color:{TEXT_PRIMARY};">{i}</li>'
                    for i in diff.resolved_issues[:3]
                )
                more = (f'<li style="color:{TEXT_MUTED};font-size:0.8rem;">'
                        f'…and {len(diff.resolved_issues) - 3} more</li>'
                        if len(diff.resolved_issues) > 3 else "")
                resolved_list = (
                    f'<div style="margin-top:8px;">'
                    f'<div style="font-size:0.72rem;color:#3DDC97;text-transform:uppercase;'
                    f'letter-spacing:0.08em;font-weight:600;margin-bottom:4px;">'
                    f'✅ Resolved</div>'
                    f'<ul style="margin:0;padding-left:18px;font-size:0.85rem;line-height:1.5;">'
                    f'{items}{more}</ul></div>'
                )
            prev_when = dt.datetime.fromtimestamp(previous.stat().st_mtime)
            diff_html = (
                f'<div style="margin-top:14px;padding-top:14px;'
                f'border-top:1px dashed {BORDER};">'
                f'<div style="display:flex;align-items:center;justify-content:space-between;'
                f'margin-bottom:10px;">'
                f'<div style="font-size:0.7rem;color:{TEXT_MUTED};'
                f'text-transform:uppercase;letter-spacing:0.1em;font-weight:600;">'
                f'Since last check</div>'
                f'<div style="font-size:0.78rem;color:{TEXT_MUTED};">'
                f'vs {time_ago(prev_when)}</div>'
                f'</div>'
                f'{chips_html}{new_list}{resolved_list}</div>'
            )

    st.markdown(
        f"""
        <div style="background:{BG_CARD};border:1px solid {BORDER};
                    border-radius:12px;padding:18px 22px;margin-bottom:18px;">
          <div style="display:flex;align-items:center;justify-content:space-between;
                      margin-bottom:14px;">
            <div>
              <div style="font-size:0.7rem;color:{TEXT_MUTED};text-transform:uppercase;
                          letter-spacing:0.1em;font-weight:600;">🌅 Morning Briefing</div>
              <div style="font-size:0.82rem;color:{TEXT_MUTED};margin-top:2px;">
                Last run {time_ago(ran_at)} · {ran_at.strftime("%b %d, %H:%M")}
              </div>
            </div>
            <div style="text-align:right;">{score_html}</div>
          </div>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:18px;">
            <div>
              <div style="font-size:0.7rem;color:{TEXT_MUTED};text-transform:uppercase;
                          letter-spacing:0.08em;margin-bottom:6px;">Top rank movers</div>
              {movers_html}
            </div>
            <div>
              <div style="font-size:0.7rem;color:{TEXT_MUTED};text-transform:uppercase;
                          letter-spacing:0.08em;margin-bottom:6px;">Health summary</div>
              <div style="font-size:0.85rem;color:{TEXT_PRIMARY};line-height:1.5;">
                Open the full report below or visit <strong>📂 Past Reports</strong>
                to read the analyst's breakdown.
              </div>
            </div>
          </div>
          {action_html}
          {diff_html}
        </div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns([1, 1])
    with col1:
        with st.expander(f"📄 Open latest health check — {latest.name}"):
            st.markdown(latest.read_text(encoding="utf-8", errors="ignore"))
    with col2:
        if st.button("⚡ Run Daily Health Check now", key="run_dhc",
                     use_container_width=True, type="primary"):
            from app.db import DAILY_HEALTH_CHECK_PROMPT
            st.session_state.pending_prompt = DAILY_HEALTH_CHECK_PROMPT
            st.rerun()


_render_morning_briefing()

# ==================================================================== prior history
for role, content in st.session_state.history:
    with st.chat_message(role):
        # Auto-collapse long outputs to keep the page scannable
        if isinstance(content, str) and len(content) > 2000:
            preview = content[:1500].rsplit("\n", 1)[0] + "\n\n…"
            st.markdown(preview, unsafe_allow_html=True)
            with st.expander(f"Show all ({len(content):,} chars)"):
                st.markdown(content, unsafe_allow_html=True)
        else:
            st.markdown(content, unsafe_allow_html=True)

# ==================================================================== quick starts
if not st.session_state.history:
    st.markdown(
        f"""
        <div style="display:flex;align-items:center;justify-content:space-between;
                    margin:4px 2px 10px;">
          <div style="font-size:0.7rem;color:{TEXT_MUTED};text-transform:uppercase;
                      letter-spacing:0.1em;font-weight:600;">Quick Starts</div>
          <div style="font-size:0.75rem;color:{TEXT_MUTED};">
            Each one fires the full crew · saved to <code>/reports</code>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    quick_prompts = [
        ("🩺  Audit Homepage", f"Run a comprehensive technical SEO audit on {target_url} for the keyword 'AI options trading'. Use PageSpeed Insights for mobile + desktop and prioritise the top 5 fixes."),
        ("🎯  Content Brief", "Write a content brief for the keyword 'AI option trade setups' targeted at intermediate-to-advanced retail option traders. Include outline, FAQ block with JSON-LD, internal links, and word-count target."),
        ("🔗  Link Prospects", f"Find 10 high-quality link-building prospects for {domain} in the AI options/stock trading niche across the priority markets (USA / EU / UK / CA / AU / APAC). Include outreach angles for each."),
        ("⚔️  Competitor Compare", f"Compare {domain} against the top 3 organic competitors for 'AI options trading' and 'AI stock trade setups'. Use SERP analysis to identify them, then compare content depth, schema, backlinks, and Core Web Vitals. Where are we losing and what's the fastest way to close the gap?"),
        (
            "🌐  Full Website Audit — On/Off Page SEO",
            f"Run a comprehensive full-website SEO audit on {domain}. "
            f"Cover all three layers: "
            f"(1) **Technical SEO** — robots.txt, sitemap coverage, crawlability, Core Web Vitals on the homepage + top 3 templates, schema implementation, canonical and hreflang chains, internal-link architecture and orphan pages; "
            f"(2) **On-page SEO** — title / meta / H1 hygiene, content depth, target-keyword density and semantic n-grams, E-E-A-T signals, mobile-friendliness across the top URLs; "
            f"(3) **Off-page SEO** — backlink profile (free signals), unlinked-mention opportunities, competitive gap analysis vs optionalpha.com and tastylive.com across the priority markets (USA / EU / UK / CA / AU / APAC). "
            f"Deliver the prioritised Top 10 fixes with effort/impact and clear ownership, then hand off outreach prospects + content briefs to Maya."
        ),
        (
            "🤖  Run AEO Audit",
            f"Run a full **Answer Engine Optimization (AEO)** audit on {domain} — how well the site is set up to be cited and surfaced by AI answer engines (ChatGPT, Perplexity, Google AI Overviews / SGE, Bing Copilot, Claude, Gemini). "
            f"Cover: "
            f"(1) **AI crawler access** — robots.txt rules for GPTBot, ClaudeBot, PerplexityBot, Google-Extended, CCBot, Bingbot; presence and content of `/llms.txt` and `/llms-full.txt`; sitemap freshness. "
            f"(2) **Citability / answer-ready structure** — TL;DR or definition blocks above the fold, scannable headings, FAQ sections, concise direct-answer paragraphs, semantic HTML, table-of-contents anchors. "
            f"(3) **Structured data for answers** — `FAQPage`, `HowTo`, `Article`, `Product`, `Organization`, `Person` (author), `Breadcrumb`, `WebSite` + SearchAction; validation of JSON-LD; speakable schema where useful. "
            f"(4) **Entity & E-E-A-T clarity** — Organization markup, About / contact / author bio pages, original research / proprietary data, citations of authoritative sources, byline credentials. "
            f"(5) **Brand-mention surface area** — measure how often {domain} is mentioned across the open web for the priority queries (use `duckduckgo_search` + `find_backlink_signals`); flag unlinked-mention reclamation targets that double as AI-citation seeds. "
            f"(6) **Geo coverage for AI answers** — quick spot-checks across the priority markets (USA / EU / UK / CA / AU / APAC). "
            f"Deliver: a prioritised Top 10 AEO fixes (What → Why → How → Effort → Impact), the AI-crawler robots block to ship, the JSON-LD blocks ready to paste, and a content-restructuring brief Maya can hand to a writer."
        ),
    ]
    # 3-column grid for tighter density (was 2-column)
    qp_cols = st.columns(3, gap="small")
    for i, (label, prompt) in enumerate(quick_prompts):
        with qp_cols[i % 3]:
            if st.button(label, key=f"qp_{i}", use_container_width=True):
                st.session_state.pending_prompt = prompt
                st.rerun()
    st.write("")

# ==================================================================== API key gate
if not ANTHROPIC_API_KEY:
    st.error("🔴 `ANTHROPIC_API_KEY` is not set. Add it to `.env` and restart Streamlit.")
    st.stop()


# ==================================================================== crew runner
def _run_crew(prompt: str):
    """Stream the crew execution and render progress + final outputs."""
    from agents.graph import stream_seo_crew

    status = st.status("⚡ Booting Team Mamba…", expanded=True)
    final_state = {"research_findings": "", "analyst_report": "", "marketer_package": ""}

    try:
        for event in stream_seo_crew(prompt, skip_marketer=skip_marketer):
            for node, payload in event.items():
                if node == "researcher":
                    status.update(label=f"🔎 {KIRA.full_name} is on the field…", state="running")
                    with status:
                        st.markdown(progress_line_html(KIRA, "Gathering evidence…"),
                                    unsafe_allow_html=True)
                    if payload.get("research_findings"):
                        final_state["research_findings"] = payload["research_findings"]
                        with status:
                            with st.expander(f"🔎 {KIRA.full_name} — raw research findings"):
                                st.markdown(payload["research_findings"])

                elif node == "analyst":
                    status.update(label=f"🧠 {CASH.full_name} is calling the play…", state="running")
                    with status:
                        st.markdown(progress_line_html(CASH, "Writing the report…"),
                                    unsafe_allow_html=True)
                    if payload.get("analyst_report"):
                        final_state["analyst_report"] = payload["analyst_report"]
                        with status:
                            with st.expander(f"🧠 {CASH.full_name} — analyst report", expanded=True):
                                st.markdown(payload["analyst_report"])

                elif node == "seo_marketer":
                    status.update(label=f"📣 {MAYA.full_name} is loading the package…", state="running")
                    with status:
                        st.markdown(progress_line_html(MAYA, "Building the execution package…"),
                                    unsafe_allow_html=True)
                    if payload.get("marketer_package"):
                        final_state["marketer_package"] = payload["marketer_package"]
                        with status:
                            with st.expander(f"📣 {MAYA.full_name} — execution package", expanded=True):
                                st.markdown(payload["marketer_package"])

        status.update(label="✅ Team Mamba finished", state="complete", expanded=False)
    except Exception as e:
        status.update(label=f"❌ Crew error: {e}", state="error")
        with status:
            st.code(traceback.format_exc())
        return

    # Save report
    if save_report and final_state.get("analyst_report"):
        from app.briefing import project_reports_dir
        ts = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        out_dir = project_reports_dir()  # per-active-project subfolder
        out_path = out_dir / f"{ts}-report.md"
        body = (
            f"# Team Mamba — {ts}\n\n"
            f"**Prompt:** {prompt}\n\n---\n\n"
            f"## 🔎 {KIRA.full_name} — research findings\n\n"
            f"{final_state.get('research_findings','')}\n\n---\n\n"
            f"## 🧠 {CASH.full_name} — analyst report\n\n"
            f"{final_state.get('analyst_report','')}\n\n"
        )
        if final_state.get("marketer_package"):
            body += f"\n---\n\n## 📣 {MAYA.full_name} — execution package\n\n{final_state['marketer_package']}\n"
        out_path.write_text(body, encoding="utf-8")
        st.success(f"📄 Saved to `reports/{out_path.name}`")
        st.download_button("⬇️ Download Markdown", data=body,
                           file_name=out_path.name, mime="text/markdown")

        # Sprint 4-cleanup — mirror to Supabase so the Next.js admin can
        # read recent reports in the Peek modal. Best-effort: failures
        # don't interrupt the local-disk save.
        try:
            from app.db import save_report_to_pg, active_project
            active = active_project() or {}
            slug = active.get("slug") or "stoptions"
            title = prompt[:120] if prompt else None
            template = (
                "daily-health-check" if "daily" in (prompt or "").lower() and "health" in (prompt or "").lower()
                else "weekly-full-audit" if "weekly" in (prompt or "").lower() and "audit" in (prompt or "").lower()
                else None
            )
            save_report_to_pg(
                project_slug=slug,
                filename=out_path.name,
                body=body,
                title=title,
                template=template,
                author="Cash",  # analyst owns the report by convention
            )
        except Exception as _pg_err:
            # Surface only as a soft caption; local save already succeeded.
            st.caption(f"(Postgres mirror skipped: {_pg_err})")

    # Persist a compact summary to chat history
    summary_md = ""
    if final_state.get("analyst_report"):
        summary_md += f"### 🧠 {CASH.full_name} — analyst report\n\n" + final_state["analyst_report"] + "\n\n"
    if final_state.get("marketer_package"):
        summary_md += f"### 📣 {MAYA.full_name} — execution package\n\n" + final_state["marketer_package"]
    st.session_state.history.append(("assistant", summary_md or "Crew completed with no output."))


# ==================================================================== chat input
typed = st.chat_input(f"Drop an SEO task for the crew (e.g. audit {target_url})")
prompt = typed or st.session_state.pending_prompt
st.session_state.pending_prompt = None

if prompt:
    st.session_state.history.append(("user", prompt))
    with st.chat_message("user"):
        st.markdown(prompt)
    with st.chat_message("assistant"):
        _run_crew(prompt)
