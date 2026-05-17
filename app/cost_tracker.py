"""Anthropic token-usage cost tracking via LangChain callbacks.

Attach AnthropicCostCallback to any ChatAnthropic call to log
(input_tokens, output_tokens, cost_usd) to SQLite. Read summaries via
app.db.cost_totals() / cost_daily_series().
"""
from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from langchain_core.callbacks import BaseCallbackHandler

from app.db import log_cost


class AnthropicCostCallback(BaseCallbackHandler):
    """Captures Anthropic token-usage from LLM responses and logs to SQLite."""

    def __init__(self, agent: str, model: str, run_id: str = "",
                 prompt_label: str = ""):
        super().__init__()
        self.agent = agent
        self.model = model
        self.run_id = run_id or uuid.uuid4().hex[:12]
        self.prompt_label = prompt_label
        self.total_in = 0
        self.total_out = 0
        self.total_usd = 0.0

    def _extract_tokens(self, response: Any) -> tuple[int, int]:
        """Pull (input, output) token counts from a LangChain LLMResult / AIMessage."""
        in_tok = out_tok = 0
        try:
            # LLMResult.llm_output sometimes contains usage at top level
            llm_output = getattr(response, "llm_output", None) or {}
            usage = (llm_output.get("usage") or {}) if isinstance(llm_output, dict) else {}
            in_tok = usage.get("input_tokens", 0) or 0
            out_tok = usage.get("output_tokens", 0) or 0
            # If empty, inspect AIMessage usage_metadata in generations
            if not (in_tok or out_tok):
                gens = getattr(response, "generations", []) or []
                for batch in gens:
                    for gen in batch:
                        msg = getattr(gen, "message", None)
                        if msg is None:
                            continue
                        um = getattr(msg, "usage_metadata", None) or {}
                        in_tok += um.get("input_tokens", 0) or 0
                        out_tok += um.get("output_tokens", 0) or 0
        except Exception:
            pass
        return in_tok, out_tok

    def on_llm_end(self, response: Any, **kwargs: Any) -> None:
        in_tok, out_tok = self._extract_tokens(response)
        if in_tok or out_tok:
            cost = log_cost(
                agent=self.agent, model=self.model,
                input_tokens=in_tok, output_tokens=out_tok,
                run_id=self.run_id, prompt_label=self.prompt_label,
            )
            self.total_in += in_tok
            self.total_out += out_tok
            self.total_usd += cost
