"""Lindsay "Linz" Ritter — SEO Project Manager (Team Mamba).

Callable on demand. Owns the backlog (decisions table) + outreach pipeline.
Not part of the auto-flow Researcher → Analyst → Marketer.
"""
from __future__ import annotations

from pathlib import Path
from langgraph.prebuilt import create_react_agent

from agents.llm import build_llm
from agents.personas import LINDSAY, persona_block
from app.db import (
    list_decisions,
    list_outreach,
    open_decisions_summary,
)
from app.learnings import learnings_block
from app.project_context import context_block_for_prompt
from tools import ALL_TOOLS

_PROMPT_BODY = (Path(__file__).resolve().parent.parent / "prompts" / "pm.md").read_text()


def _backlog_snapshot_block() -> str:
    """Inject the current backlog + outreach state into PM's context."""
    open_d = list_decisions(status="open")
    in_prog = list_decisions(status="in_progress")
    done = list_decisions(status="done")
    snoozed = list_decisions(status="snoozed")
    wontfix = list_decisions(status="wontfix")
    outreach = list_outreach()

    lines = ["## Current backlog snapshot (live from SQLite)\n"]
    lines.append(f"- Open: {len(open_d)}  ·  In progress: {len(in_prog)}  ·  "
                 f"Done: {len(done)}  ·  Snoozed: {len(snoozed)}  ·  Wontfix: {len(wontfix)}")
    lines.append(f"- Outreach prospects: {len(outreach)}")

    if open_d or in_prog:
        lines.append("\n### Open + in_progress decisions")
        for d in (open_d + in_prog)[:30]:
            scope = d.get("target_url") or d.get("target_keyword") or ""
            scope = f" · {scope}" if scope else ""
            lines.append(
                f"- #{d['id']} [{d['status'].upper()}] {d['title']}{scope}  "
                f"·  effort={d.get('effort') or '?'}  impact={d.get('impact') or '?'}  "
                f"created={d['created_at'][:10]}"
            )

    if outreach:
        lines.append("\n### Outreach pipeline")
        from collections import Counter
        by_status = Counter(o["status"] for o in outreach)
        lines.append("Status counts: " + ", ".join(
            f"{k}={v}" for k, v in sorted(by_status.items())))
        for o in outreach[:15]:
            lines.append(
                f"- #{o['id']} [{o['status'].upper()}] {o['prospect_url']}  "
                f"·  region={o.get('region') or '?'}  "
                f"contacted={o.get('contacted_at','')[:10] or '—'}  "
                f"replied={o.get('replied_at','')[:10] or '—'}"
            )

    return "\n".join(lines)


def _full_prompt() -> str:
    parts = [persona_block(LINDSAY), _PROMPT_BODY]
    ctx = context_block_for_prompt()
    if ctx:
        parts.append(ctx)
    parts.append("\n---\n\n" + _backlog_snapshot_block() + "\n")
    learnings = learnings_block(LINDSAY.key, LINDSAY.full_name)
    if learnings:
        parts.append(learnings)
    return "\n".join(parts)


def build_pm_agent():
    llm = build_llm(temperature=0.2, max_tokens=6000, agent=LINDSAY.key)
    return create_react_agent(
        model=llm,
        tools=ALL_TOOLS,
        prompt=_full_prompt(),
        name=LINDSAY.key,
    )


def run_pm(user_prompt: str) -> str:
    """One-shot PM invocation. Returns the agent's final text."""
    from langchain_core.messages import HumanMessage, AIMessage
    agent = build_pm_agent()
    out = agent.invoke({"messages": [HumanMessage(content=user_prompt)]})
    for m in reversed(out.get("messages", [])):
        if isinstance(m, AIMessage):
            content = m.content
            if isinstance(content, list):
                return "\n".join(
                    c.get("text", "") for c in content
                    if isinstance(c, dict) and c.get("type") == "text"
                ).strip()
            return (content or "").strip()
    return ""
