"""LangGraph orchestration for the 3-agent SEO crew.

Flow:
    user → SEO Researcher → Technical SEO Analyst → SEO Marketer → user

Each agent is a ReAct-style sub-agent with full tool access. The supervisor
graph forwards the running message history between them so each agent has
the full context, and saves intermediate artefacts in the graph state.

Usage:
    from agents.graph import run_seo_crew
    for event in run_seo_crew("Audit https://stoptions.ai/ for the keyword 'options trading'"):
        print(event)
"""
from __future__ import annotations

import re
from typing import Annotated, Iterator, List, Optional, TypedDict

from langchain_core.messages import AIMessage, HumanMessage, BaseMessage, SystemMessage
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages

from agents.researcher import build_researcher_agent
from agents.analyst import build_analyst_agent
from agents.marketer import build_marketer_agent


class CrewState(TypedDict, total=False):
    messages: Annotated[List[BaseMessage], add_messages]
    research_findings: str
    analyst_report: str
    marketer_package: str
    skip_marketer: bool


# Build the three sub-agents lazily so importing this module doesn't require
# the API key (useful for tests / Streamlit boot).
_researcher = None
_analyst = None
_marketer = None


def _get_researcher():
    global _researcher
    if _researcher is None:
        _researcher = build_researcher_agent()
    return _researcher


def _get_analyst():
    global _analyst
    if _analyst is None:
        _analyst = build_analyst_agent()
    return _analyst


def _get_marketer():
    global _marketer
    if _marketer is None:
        _marketer = build_marketer_agent()
    return _marketer


def _last_ai_text(messages: List[BaseMessage]) -> str:
    for m in reversed(messages):
        if isinstance(m, AIMessage):
            content = m.content
            if isinstance(content, list):
                # Anthropic returns a list of content blocks
                parts = []
                for c in content:
                    if isinstance(c, dict) and c.get("type") == "text":
                        parts.append(c.get("text", ""))
                return "\n".join(parts).strip()
            return (content or "").strip()
    return ""


def _researcher_node(state: CrewState) -> CrewState:
    agent = _get_researcher()
    out = agent.invoke({"messages": state["messages"]})
    new_msgs = out["messages"]
    findings = _last_ai_text(new_msgs)
    # Re-tag as a system note so the next agent sees clean context.
    handoff = SystemMessage(
        content=f"## Research findings (from SEO Researcher)\n\n{findings}"
    )
    return {
        "messages": [handoff],
        "research_findings": findings,
    }


def _analyst_node(state: CrewState) -> CrewState:
    agent = _get_analyst()
    msgs = list(state["messages"]) + [
        HumanMessage(
            content=(
                "Please now produce the final SEO Markdown report based on the "
                "Researcher's findings above. Follow your output format exactly."
            )
        )
    ]
    out = agent.invoke({"messages": msgs})
    report = _last_ai_text(out["messages"])
    handoff = SystemMessage(content=f"## Analyst report (from Technical SEO Analyst)\n\n{report}")
    return {
        "messages": [handoff],
        "analyst_report": report,
    }


def _seo_marketer_node(state: CrewState) -> CrewState:
    if state.get("skip_marketer"):
        return {"marketer_package": ""}
    agent = _get_marketer()
    msgs = list(state["messages"]) + [
        HumanMessage(
            content=(
                "Please now produce the marketing execution package for Stoptions.ai "
                "based on the Analyst's report above. Use real prospects when possible "
                "(call tools if you need to verify them)."
            )
        )
    ]
    out = agent.invoke({"messages": msgs})
    package = _last_ai_text(out["messages"])
    return {
        "messages": [AIMessage(content=package)],
        "marketer_package": package,
    }


def _route_after_analyst(state: CrewState) -> str:
    return END if state.get("skip_marketer") else "seo_marketer"


def build_graph():
    g = StateGraph(CrewState)
    g.add_node("researcher", _researcher_node)
    g.add_node("analyst", _analyst_node)
    g.add_node("seo_marketer", _seo_marketer_node)
    g.add_edge(START, "researcher")
    g.add_edge("researcher", "analyst")
    g.add_conditional_edges("analyst", _route_after_analyst, {"seo_marketer": "seo_marketer", END: END})
    g.add_edge("seo_marketer", END)
    return g.compile()


_compiled_graph = None


def get_graph():
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_graph()
    return _compiled_graph


def run_seo_crew(user_request: str, skip_marketer: bool = False) -> dict:
    """Run the full crew end-to-end and return the final state."""
    graph = get_graph()
    initial: CrewState = {
        "messages": [HumanMessage(content=user_request)],
        "skip_marketer": skip_marketer,
    }
    final = graph.invoke(initial, config={"recursion_limit": 60})
    return final


def stream_seo_crew(user_request: str, skip_marketer: bool = False) -> Iterator[dict]:
    """Stream node-level updates so the UI can show progress."""
    graph = get_graph()
    initial: CrewState = {
        "messages": [HumanMessage(content=user_request)],
        "skip_marketer": skip_marketer,
    }
    for event in graph.stream(initial, config={"recursion_limit": 60}, stream_mode="updates"):
        yield event
