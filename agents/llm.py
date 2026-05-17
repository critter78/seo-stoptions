"""Single place to construct the Anthropic chat model with cost-tracking callbacks."""
from __future__ import annotations

from typing import Optional

from langchain_anthropic import ChatAnthropic

from app.config import ANTHROPIC_API_KEY, ANTHROPIC_MODEL
from app.cost_tracker import AnthropicCostCallback


def build_llm(
    temperature: float = 0.2,
    max_tokens: int = 4096,
    agent: str = "adhoc",
    run_id: str = "",
    prompt_label: str = "",
) -> ChatAnthropic:
    """Build a Claude model with an attached AnthropicCostCallback.

    Every LLM call automatically logs (input_tokens, output_tokens, cost_usd)
    to SQLite via app.db.log_cost(). Read summaries via app.db.cost_totals().
    """
    if not ANTHROPIC_API_KEY:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. Export it or add it to .env before running."
        )
    cb = AnthropicCostCallback(
        agent=agent, model=ANTHROPIC_MODEL, run_id=run_id, prompt_label=prompt_label,
    )
    return ChatAnthropic(
        model=ANTHROPIC_MODEL,
        temperature=temperature,
        max_tokens=max_tokens,
        api_key=ANTHROPIC_API_KEY,
        callbacks=[cb],
    )
