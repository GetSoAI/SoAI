"""SoAI - Agent context compaction [backend/features/agent/runtime/context_compaction/service.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from functools import partial
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.logging.trace import get_logger
from core.openai.tool_message_sequence_repair import (
    repair_openai_tool_message_sequence_for_internal_contracts,
)
from core.validation.strict_numbers import require_positive_int_strict
from features.agent.runtime.context_compaction.deterministic_reduction import (
    reduce_history_deterministically,
)
from features.agent.runtime.context_compaction.final_validation import (
    require_compacted_history_within_budget,
)
from features.agent.runtime.context_compaction.history import split_compaction_buckets
from features.agent.runtime.context_compaction.llm_outcome import (
    try_build_llm_compaction_outcome,
)
from features.agent.runtime.context_compaction.outcome import (
    COMPACTION_SUMMARY_SOURCE_DETERMINISTIC,
    MessageHistoryCompactionOutcome,
)
from features.agent.runtime.context_compaction.rewrite import (
    rewrite_history_for_compaction,
)
from features.agent.runtime.context_compaction.summary import (
    build_summary_message,
    extract_context_summary,
    strip_context_summary_messages,
)
from features.agent.runtime.context_compaction.token_counting import (
    count_compaction_history_occupancy,
)
from features.agent.runtime.context_compaction.user_memory import (
    strip_user_message_memory_messages,
)
from features.agent.runtime.context_compaction.user_memory_integration import (
    apply_user_message_memory_to_compacted_history,
)

if TYPE_CHECKING:
    from core.openai.token_counter import PromptTokenCounter
    from core.openai.token_estimation_profile import TokenEstimationProfile
    from core.types.json import JSONDict
    from features.agent.runtime.context_compaction.user_memory import UserMessageMemory

__all__ = (
    "build_summary_message",
    "compact_message_history_if_needed",
    "compact_message_history_with_outcome_if_needed",
    "extract_context_summary",
)

LOGGER_NAME = "SoAI.features.agent.context_compaction_service"
OPERATION = "agent.runtime.context_compaction.summary"


async def compact_message_history_if_needed(
    *,
    message_history: list[JSONDict],
    base_request_payload: JSONDict,
    prompt_token_counter: PromptTokenCounter,
    max_prompt_tokens: int,
    maximum_prompt_tokens: int,
    summarize_messages: Callable[[list[JSONDict]], Awaitable[str]] | None,
    token_estimation_profile: TokenEstimationProfile | None = None,
) -> list[JSONDict]:
    outcome = await compact_message_history_with_outcome_if_needed(
        message_history=message_history,
        base_request_payload=base_request_payload,
        prompt_token_counter=prompt_token_counter,
        max_prompt_tokens=max_prompt_tokens,
        maximum_prompt_tokens=maximum_prompt_tokens,
        summarize_messages=summarize_messages,
        token_estimation_profile=token_estimation_profile,
    )
    return outcome.compacted_messages


async def compact_message_history_with_outcome_if_needed(
    *,
    message_history: list[JSONDict],
    base_request_payload: JSONDict,
    prompt_token_counter: PromptTokenCounter,
    max_prompt_tokens: int,
    maximum_prompt_tokens: int,
    summarize_messages: Callable[[list[JSONDict]], Awaitable[str]] | None,
    token_estimation_profile: TokenEstimationProfile | None = None,
) -> MessageHistoryCompactionOutcome:
    resolved_max = require_positive_int_strict(
        max_prompt_tokens,
        error_message="Compaction target prompt budget must be >= 1.",
    )
    resolved_maximum = require_positive_int_strict(
        maximum_prompt_tokens,
        error_message="Compaction maximum prompt budget must be >= 1.",
    )
    if resolved_max > resolved_maximum:
        raise ValidationError("Compaction target prompt budget cannot exceed its maximum.")
    initial_occupancy = await prompt_token_counter.run_blocking(
        partial(
            count_compaction_history_occupancy,
            prompt_token_counter=prompt_token_counter,
            base_request_payload=base_request_payload,
            message_history=message_history,
            token_estimation_profile=token_estimation_profile,
        ),
    )
    if not initial_occupancy.capped and int(initial_occupancy.prompt_tokens) <= resolved_max:
        return MessageHistoryCompactionOutcome(
            compacted_messages=message_history,
            summary_source=COMPACTION_SUMMARY_SOURCE_DETERMINISTIC,
            prompt_occupancy=initial_occupancy,
        )
    rewritten_history = rewrite_history_for_compaction(message_history)
    rewritten_occupancy = await prompt_token_counter.run_blocking(
        partial(
            count_compaction_history_occupancy,
            prompt_token_counter=prompt_token_counter,
            base_request_payload=base_request_payload,
            message_history=rewritten_history,
            token_estimation_profile=token_estimation_profile,
        ),
    )
    if not rewritten_occupancy.capped and int(rewritten_occupancy.prompt_tokens) <= resolved_max:
        return MessageHistoryCompactionOutcome(
            compacted_messages=rewritten_history,
            summary_source=COMPACTION_SUMMARY_SOURCE_DETERMINISTIC,
            prompt_occupancy=rewritten_occupancy,
        )
    existing_user_memory, rewritten_without_memory = strip_user_message_memory_messages(
        rewritten_history,
    )
    summary_text, history_without_summary = strip_context_summary_messages(rewritten_without_memory)
    pinned_prefix, before_anchor, anchor_message, after_anchor = split_compaction_buckets(
        history_without_summary,
    )
    if summarize_messages is not None:
        compaction_logger = get_logger(LOGGER_NAME)
        compaction_operation = OPERATION
        compaction_target_prompt_tokens = resolved_max
        llm_outcome = await try_build_llm_compaction_outcome(
            logger=compaction_logger,
            operation=compaction_operation,
            summarize_messages=summarize_messages,
            prompt_token_counter=prompt_token_counter,
            max_prompt_tokens=compaction_target_prompt_tokens,
            base_request_payload=base_request_payload,
            history_without_summary=history_without_summary,
            existing_user_memory=existing_user_memory,
            anchor_message=anchor_message,
            before_anchor=before_anchor,
            after_anchor=after_anchor,
            pinned_prefix=pinned_prefix,
            summary_text=summary_text,
            token_estimation_profile=token_estimation_profile,
        )
        if llm_outcome is not None:
            return llm_outcome

    return await prompt_token_counter.run_blocking(
        partial(
            _build_deterministic_compaction_outcome,
            history_without_summary=history_without_summary,
            summary_text=summary_text,
            existing_user_memory=existing_user_memory,
            prompt_token_counter=prompt_token_counter,
            base_request_payload=base_request_payload,
            resolved_max=resolved_max,
            resolved_maximum=resolved_maximum,
            token_estimation_profile=token_estimation_profile,
        ),
    )


def _build_deterministic_compaction_outcome(
    *,
    history_without_summary: list[JSONDict],
    summary_text: str | None,
    existing_user_memory: UserMessageMemory | None,
    prompt_token_counter: PromptTokenCounter,
    base_request_payload: JSONDict,
    resolved_max: int,
    resolved_maximum: int,
    token_estimation_profile: TokenEstimationProfile | None,
) -> MessageHistoryCompactionOutcome:
    reduction_outcome = reduce_history_deterministically(
        history_without_summary=history_without_summary,
        summary_text=summary_text,
        prompt_token_counter=prompt_token_counter,
        base_request_payload=base_request_payload,
        max_prompt_tokens=resolved_max,
        token_estimation_profile=token_estimation_profile,
    )
    memory_compacted_messages = apply_user_message_memory_to_compacted_history(
        candidate_history=rewrite_history_for_compaction(
            reduction_outcome.compacted_messages,
        ),
        original_history=history_without_summary,
        existing_memory=existing_user_memory,
        prompt_token_counter=prompt_token_counter,
        base_request_payload=base_request_payload,
        max_prompt_tokens=resolved_max,
        token_estimation_profile=token_estimation_profile,
    )
    final_compacted_messages, _changed = repair_openai_tool_message_sequence_for_internal_contracts(
        messages=memory_compacted_messages,
    )
    final_occupancy = require_compacted_history_within_budget(
        prompt_token_counter=prompt_token_counter,
        base_request_payload=base_request_payload,
        message_history=final_compacted_messages,
        target_prompt_tokens=resolved_max,
        maximum_prompt_tokens=resolved_maximum,
        protected_floor_reached=reduction_outcome.protected_floor_reached,
        token_estimation_profile=token_estimation_profile,
    )
    return MessageHistoryCompactionOutcome(
        compacted_messages=final_compacted_messages,
        summary_source=COMPACTION_SUMMARY_SOURCE_DETERMINISTIC,
        prompt_occupancy=final_occupancy,
    )
