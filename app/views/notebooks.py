"""📓 Notebooks — per-agent learnings + rejection log.

Each agent has a free-form Markdown notebook scoped to the active project.
Whatever you write here is auto-injected into the agent's system prompt on
every run — a durable channel for teaching the team things you don't want
to repeat every time.

Also shows the recent rejection log (👎 feedback the operator gave on past
outputs) so you can see — and revoke — what's currently shaping behaviour.
"""
from __future__ import annotations

import streamlit as st

from app.db import (
    active_project,
    get_agent_notes,
    init_db,
    recent_rejections,
    set_agent_notes,
)
from app.ui_helpers import (
    ACCENT, BG_CARD, BORDER, TEXT_MUTED, TEXT_PRIMARY,
    empty_state_card, logo_html, severity_badge,
)
from agents.personas import KIRA, CASH, MAYA, LINDSAY

init_db()
_proj = active_project()
_proj_name = (_proj or {}).get("name", "no project")

st.markdown(
    f"""
    <div style="background:linear-gradient(135deg,#0d1117 0%,#161B22 100%);
                border:1px solid {BORDER};border-radius:14px;
                padding:20px 24px;margin-bottom:24px;">
      <div style="display:flex;align-items:center;gap:14px;margin-bottom:6px;">
        {logo_html(height=36)}
        <div style="font-size:0.78rem;color:{ACCENT};letter-spacing:0.14em;
                    text-transform:uppercase;font-weight:600;">Smarter over time</div>
      </div>
      <h1 style="margin:0 0 8px;font-size:1.7rem;color:{TEXT_PRIMARY};">
        📓 Agent Notebooks
      </h1>
      <div style="color:{TEXT_MUTED};font-size:0.92rem;line-height:1.55;">
        Free-form learnings per agent, scoped to <strong style="color:{TEXT_PRIMARY};">
        {_proj_name}</strong>. Notes are auto-injected into the agent's system
        prompt on every run, alongside recent ✋ rejections and ⭐ starred
        reference reports.
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

AGENTS = [KIRA, CASH, MAYA, LINDSAY]

tabs = st.tabs([f"{a.emoji} {a.nickname or a.full_name.split()[0]}" for a in AGENTS])

for tab, agent in zip(tabs, AGENTS):
    with tab:
        st.markdown(
            f"### {agent.full_name}  ·  *{agent.role}*"
        )
        st.caption(f'"{agent.tagline}"')

        c1, c2 = st.columns([2, 1], gap="medium")
        with c1:
            st.markdown("**Learnings notebook**")
            existing = get_agent_notes(agent.key)
            new_md = st.text_area(
                "Notes (Markdown — auto-injected into every run)",
                value=existing,
                height=420,
                key=f"notes_{agent.key}",
                placeholder=(
                    f"# Things {agent.nickname or agent.full_name.split()[0]} has learned\n\n"
                    "- The user's audience prefers concise, numbers-driven recommendations.\n"
                    "- Don't recommend blog-comment link building (ever).\n"
                    "- When citing competitors, prefer optionalpha.com over tastylive.com.\n"
                    "- Mobile Lighthouse scores < 70 are an automatic ★★★ impact item.\n\n"
                    "## Things to never do\n\n- ...\n"
                ),
                help=(
                    "Treat this like a private playbook you're updating for this agent. "
                    "Bullet points work great. Will be injected verbatim into every "
                    "prompt this agent runs."
                ),
            )
            col_a, col_b = st.columns([1, 1])
            with col_a:
                if st.button("💾 Save notebook", key=f"save_{agent.key}",
                             type="primary", use_container_width=True):
                    set_agent_notes(agent.key, new_md)
                    st.success("Saved. Next agent run will see the update.")
            with col_b:
                if existing and st.button("🗑 Clear", key=f"clr_{agent.key}",
                                          use_container_width=True):
                    set_agent_notes(agent.key, "")
                    st.rerun()

        with c2:
            st.markdown("**👎 Recent rejections**")
            rejs = recent_rejections(agent_key=agent.key, limit=10)
            if not rejs:
                st.markdown(
                    empty_state_card(
                        icon="👍",
                        title="No rejections yet",
                        body=(
                            f"When you 👎 one of {agent.full_name.split()[0]}'s reports "
                            "with a reason, it appears here and gets injected into the "
                            "agent's next-run prompt as 'things to avoid'."
                        ),
                    ),
                    unsafe_allow_html=True,
                )
            else:
                for r in rejs:
                    when = (r.get("rejected_at") or "")[:10]
                    rep = r.get("report_name") or "(no report)"
                    st.markdown(
                        f'<div style="background:{BG_CARD};border-left:3px solid #F85149;'
                        f'border-radius:6px;padding:8px 12px;margin:6px 0;'
                        f'font-size:0.85rem;">'
                        f'<div style="color:{TEXT_MUTED};font-size:0.72rem;">'
                        f'{when} · <code>{rep}</code></div>'
                        f'<div style="color:{TEXT_PRIMARY};margin-top:4px;">'
                        f'{r["reason"]}</div></div>',
                        unsafe_allow_html=True,
                    )

        st.markdown(
            f'<div style="margin-top:12px;font-size:0.75rem;color:{TEXT_MUTED};">'
            f'{severity_badge("info", "Note injected on every run")}'
            f'</div>',
            unsafe_allow_html=True,
        )

st.markdown("---")
st.caption(
    "Notes + rejections are scoped to the **active project** (sidebar dropdown). "
    "Switching project shows a different notebook for the same agent."
)
