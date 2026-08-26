"""SoAI - Agent output token cap resolution [backend/features/agent/session/agent_output_tokens.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.openai.output_token_cap import resolve_output_token_cap

if TYPE_CHECKING:
    from core.agent.settings_types import AgentSettings
    from core.types.json import JSONDict
    from features.agent.session.compaction_budget import ResolvedCompactionBudget

__all__ = (
    "has_explicit_agent_output_token_cap",
    "resolve_agent_output_token_limit",
)


def has_explicit_agent_output_token_cap(request_json: JSONDict) -> bool:
    return resolve_output_token_cap(request_json) is not None


def resolve_agent_output_token_limit(
    *,
    request_json: JSONDict,
    agent_settings: AgentSettings,
    compaction_budget: ResolvedCompactionBudget,
    prompt_tokens: int | None = None,
) -> int:
    resolved_cap = int(agent_settings.max_output_tokens)
    resolved_cap = min(resolved_cap, int(compaction_budget.context_window_tokens))
    user_cap = resolve_output_token_cap(request_json)
    if user_cap is not None:
        resolved_cap = min(resolved_cap, int(user_cap))
    if prompt_tokens is not None:
        remaining_tokens = max(
            0,
            int(compaction_budget.context_window_tokens) - int(prompt_tokens),
        )
        resolved_cap = min(resolved_cap, remaining_tokens)
    return max(0, int(resolved_cap))
