"""SoAI - Manual compaction summary token budgeting [backend/features/api/routes/webui/conversation_agent_compaction/summary.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.openai.token_accounting import count_prompt_occupancy
from core.openai.truncation import build_prefix_truncation_text
from features.agent.runtime.context_compaction.summary import build_summary_message

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from features.api.runtime.context import ApiContext

__all__ = (
    "TruncationCandidate",
    "truncate_summary_to_budget",
)


@dataclass(frozen=True, slots=True)
class TruncationCandidate:
    content: str


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
    low, high = 0, len(summary_text)
    best: TruncationCandidate | None = None
    while low <= high:
        mid = (low + high) // 2
        candidate_text = build_prefix_truncation_text(
            original=summary_text,
            prefix_length=mid,
        )
        candidate_payload = dict(base_payload)
        candidate_payload["messages"] = [build_summary_message(candidate_text)]
        candidate_occupancy = count_prompt_occupancy(
            prompt_token_counter=api_context.dependencies.prompt_token_counter,
            request_payload=candidate_payload,
        )
        candidate_tokens = candidate_occupancy.prompt_tokens
        if not candidate_occupancy.capped and candidate_tokens <= target_prompt_tokens:
            best = TruncationCandidate(content=candidate_text)
            low = mid + 1
            continue
        high = mid - 1
    if best is None:
        raise ValidationError(
            "Compaction target prompt budget is too small to fit any summary content.",
        )
    final_payload = dict(base_payload)
    final_payload["messages"] = [build_summary_message(best.content)]
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
    return best.content
