"""SoAI - Shared compaction token counting helpers [backend/features/agent/runtime/context_compaction/token_counting.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.openai.token_accounting import PromptOccupancy, count_history_prompt_occupancy
from features.agent.runtime.request_messages import strip_internal_message_metadata

if TYPE_CHECKING:
    from core.openai.token_counter import PromptTokenCounter
    from core.openai.token_estimation_profile import TokenEstimationProfile
    from core.types.json import JSONDict

__all__ = (
    "count_compaction_text_tokens",
    "count_compaction_history_occupancy",
    "count_history_prompt_tokens",
    "count_history_prompt_tokens_result",
    "history_within_budget",
)


def count_compaction_history_occupancy(
    *,
    prompt_token_counter: PromptTokenCounter,
    base_request_payload: JSONDict,
    message_history: list[JSONDict],
    token_estimation_profile: TokenEstimationProfile | None = None,
) -> PromptOccupancy:
    return count_history_prompt_occupancy(
        prompt_token_counter=prompt_token_counter,
        base_request_payload=base_request_payload,
        message_history=strip_internal_message_metadata(message_history),
        token_estimation_profile=token_estimation_profile,
    )


def count_compaction_text_tokens(
    prompt_token_counter: PromptTokenCounter,
    *,
    text: str,
    model_name: str | None,
    token_estimation_profile: TokenEstimationProfile | None = None,
) -> int:
    return int(
        prompt_token_counter.count_text_tokens(
            text,
            model_name=model_name,
            profile=token_estimation_profile,
        ),
    )


def count_history_prompt_tokens(
    *,
    prompt_token_counter: PromptTokenCounter,
    base_request_payload: JSONDict,
    message_history: list[JSONDict],
    token_estimation_profile: TokenEstimationProfile | None = None,
) -> int:
    occupancy = count_compaction_history_occupancy(
        prompt_token_counter=prompt_token_counter,
        base_request_payload=base_request_payload,
        message_history=message_history,
        token_estimation_profile=token_estimation_profile,
    )
    if occupancy.capped:
        return 2**31 - 1
    return int(occupancy.prompt_tokens)


def count_history_prompt_tokens_result(
    *,
    prompt_token_counter: PromptTokenCounter,
    base_request_payload: JSONDict,
    message_history: list[JSONDict],
    token_estimation_profile: TokenEstimationProfile | None = None,
) -> tuple[int, bool, str | None]:
    occupancy = count_compaction_history_occupancy(
        prompt_token_counter=prompt_token_counter,
        base_request_payload=base_request_payload,
        message_history=message_history,
        token_estimation_profile=token_estimation_profile,
    )
    return int(occupancy.prompt_tokens), bool(occupancy.capped), occupancy.capped_reason


def history_within_budget(
    *,
    prompt_token_counter: PromptTokenCounter,
    base_request_payload: JSONDict,
    message_history: list[JSONDict],
    max_prompt_tokens: int,
    token_estimation_profile: TokenEstimationProfile | None = None,
) -> bool:
    prompt_tokens, capped, _reason = count_history_prompt_tokens_result(
        prompt_token_counter=prompt_token_counter,
        base_request_payload=base_request_payload,
        message_history=message_history,
        token_estimation_profile=token_estimation_profile,
    )
    if capped:
        return False
    return int(prompt_tokens) <= int(max_prompt_tokens)
