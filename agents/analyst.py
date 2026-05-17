"""Cassius "Cash" Reed — Principal Technical SEO Analyst (Team Mamba)."""
from __future__ import annotations

from pathlib import Path
from langgraph.prebuilt import create_react_agent

from agents.llm import build_llm
from agents.personas import CASH, persona_block
from app.db import open_decisions_summary
from app.learnings import learnings_block
from app.project_context import context_block_for_prompt
from tools import ALL_TOOLS

_PROMPT_BODY = (Path(__file__).resolve().parent.parent / "prompts" / "analyst.md").read_text()


def _full_prompt() -> str:
    parts = [persona_block(CASH), _PROMPT_BODY]
    ctx = context_block_for_prompt()
    if ctx:
        parts.append(ctx)
    decisions = open_decisions_summary(max_items=20)
    if decisions:
        parts.append("\n" + decisions + "\n")
    learnings = learnings_block(CASH.key, CASH.full_name)
    if learnings:
        parts.append(learnings)
    return "\n".join(parts)


def build_analyst_agent():
    llm = build_llm(temperature=0.2, max_tokens=6000, agent=CASH.key)
    return create_react_agent(
        model=llm,
        tools=ALL_TOOLS,
        prompt=_full_prompt(),
        name=CASH.key,
    )
