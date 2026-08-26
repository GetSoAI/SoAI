"""SoAI - Final context compaction budget validation [backend/features/agent/runtime/context_compaction/final_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.openai.token_accounting import PromptOccupancy
from core.validation.strict_numbers import require_positive_int_strict
from features.agent.runtime.context_compaction.token_counting import (
    count_compaction_history_occupancy,
)

if TYPE_CHECKING:
    from core.openai.token_counter import PromptTokenCounter
    from core.openai.token_estimation_profile import TokenEstimationProfile
    from core.types.json import JSONDict

__all__ = ("require_compacted_history_within_budget",)


def require_compacted_history_within_budget(
    *,
    prompt_token_counter: PromptTokenCounter,
    base_request_payload: JSONDict,
    message_history: list[JSONDict],
    target_prompt_tokens: int,
    maximum_prompt_tokens: int,
    protected_floor_reached: bool,
    token_estimation_profile: TokenEstimationProfile | None = None,
) -> PromptOccupancy:
    resolved_target = require_positive_int_strict(
        target_prompt_tokens,
        error_message="Compaction target prompt budget must be >= 1.",
    )
    resolved_maximum = require_positive_int_strict(
        maximum_prompt_tokens,
        error_message="Compaction maximum prompt budget must be >= 1.",
    )
    if resolved_target > resolved_maximum:
        raise ValidationError("Compaction target prompt budget cannot exceed its maximum.")
    occupancy = count_compaction_history_occupancy(
        prompt_token_counter=prompt_token_counter,
        base_request_payload=base_request_payload,
        message_history=message_history,
        token_estimation_profile=token_estimation_profile,
    )
    if occupancy.capped:
        raise ValidationError(
            f"Prompt token counting capped after compaction (reason={occupancy.capped_reason}, maximum_tokens={resolved_maximum}).",
        )
    if int(occupancy.prompt_tokens) > resolved_maximum:
        raise ValidationError(
            f"Prompt exceeds the maximum after preserving required context (prompt_tokens={occupancy.prompt_tokens}, maximum_tokens={resolved_maximum}).",
        )
    if int(occupancy.prompt_tokens) > resolved_target and not protected_floor_reached:
        raise ValidationError(
            f"Prompt exceeds the compaction target before reaching the protected context floor (prompt_tokens={occupancy.prompt_tokens}, target_tokens={resolved_target}).",
        )
    return occupancy
