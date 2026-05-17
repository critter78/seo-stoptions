"""Maya Vega — SEO Marketer (Team Mamba)."""
from __future__ import annotations

from pathlib import Path
from langgraph.prebuilt import create_react_agent

from agents.llm import build_llm
from agents.personas import MAYA, persona_block
from app.db import open_decisions_summary
from app.learnings import learnings_block
from app.project_context import context_block_for_prompt
from tools import ALL_TOOLS

_PROMPT_BODY = (Path(__file__).resolve().parent.parent / "prompts" / "marketer.md").read_text()


def _full_prompt() -> str:
    parts = [persona_block(MAYA), _PROMPT_BODY]
    ctx = context_block_for_prompt()
    if ctx:
        parts.append(ctx)
    decisions = open_decisions_summary(max_items=20)
    if decisions:
        parts.append("\n" + decisions + "\n")
    learnings = learnings_block(MAYA.key, MAYA.full_name)
    if learnings:
        parts.append(learnings)
    return "\n".join(parts)


def build_marketer_agent():
    llm = build_llm(temperature=0.4, max_tokens=6000, agent=MAYA.key)
    return create_react_agent(
        model=llm,
        tools=ALL_TOOLS,
        prompt=_full_prompt(),
        name=MAYA.key,
    )


def run_marketer(user_prompt: str) -> str:
    """One-shot Maya invocation — used by the 1:1 chat view."""
    from langchain_core.messages import HumanMessage, AIMessage
    agent = build_marketer_agent()
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
