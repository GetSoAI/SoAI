"""SoAI - Manual compaction summary token budgeting [backend/features/api/routes/webui/conversation_agent_compaction/summary.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.openai.token_accounting import count_prompt_occupancy
from features.agent.runtime.context_compaction.budget import truncate_message_content_to_fit_budget
from features.agent.runtime.context_compaction.summary import (
    build_summary_message,
    extract_context_summary,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from features.api.runtime.context import ApiContext

__all__ = ("truncate_summary_to_budget",)


def truncate_summary_to_budget(
    *,
    api_context: ApiContext,
    model: str,
    summary_text: str,
    target_prompt_tokens: int,
) -> str:
    base_payload: JSONDict = {"model": model}
    payload = dict(base_payload)
    payload["messages"] = [build_summary_message(summary_text)]
    initial_occupancy = count_prompt_occupancy(
        prompt_token_counter=api_context.dependencies.prompt_token_counter,
        request_payload=payload,
    )
    if initial_occupancy.capped:
        raise ValidationError(
            "Compaction summary exceeds the supported token-counting limit.",
        )
    initial_tokens = initial_occupancy.prompt_tokens
    if initial_tokens <= target_prompt_tokens:
        return summary_text
    messages = truncate_message_content_to_fit_budget(
        prompt_token_counter=api_context.dependencies.prompt_token_counter,
        base_request_payload=base_payload,
        message_history=[build_summary_message(summary_text)],
        message_index=0,
        max_prompt_tokens=target_prompt_tokens,
    )
    fitted_summary = extract_context_summary(messages)
    if not fitted_summary:
        raise ValidationError(
            "Compaction target prompt budget is too small to fit any summary content."
        )
    final_payload = dict(base_payload)
    final_payload["messages"] = [build_summary_message(fitted_summary)]
    final_occupancy = count_prompt_occupancy(
        prompt_token_counter=api_context.dependencies.prompt_token_counter,
        request_payload=final_payload,
    )
    if final_occupancy.capped:
        raise ValidationError(
            "Compaction summary exceeds the supported token-counting limit.",
        )
    final_tokens = final_occupancy.prompt_tokens
    if final_tokens > target_prompt_tokens:
        raise ValidationError("Compaction summary exceeds the configured prompt budget.")
    return fitted_summary
