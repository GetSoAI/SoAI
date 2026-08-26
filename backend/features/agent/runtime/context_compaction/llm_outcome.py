"""SoAI - LLM-assisted compaction outcome resolution [backend/features/agent/runtime/context_compaction/llm_outcome.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from functools import partial
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception
from core.errors.exceptions import ValidationError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.openai.tool_message_sequence_repair import (
    repair_openai_tool_message_sequence_for_internal_contracts,
)
from core.validation.strict_numbers import require_positive_int_strict
from features.agent.runtime.context_compaction.final_validation import (
    require_compacted_history_within_budget,
)
from features.agent.runtime.context_compaction.llm_candidate import (
    build_llm_compaction_candidate_history,
)
from features.agent.runtime.context_compaction.outcome import (
    COMPACTION_SUMMARY_SOURCE_LLM,
    MessageHistoryCompactionOutcome,
)
from features.agent.runtime.context_compaction.user_memory_integration import (
    apply_user_message_memory_to_compacted_history,
)

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from core.openai.token_counter import PromptTokenCounter
    from core.openai.token_estimation_profile import TokenEstimationProfile
    from core.types.json import JSONDict
    from features.agent.runtime.context_compaction.user_memory import UserMessageMemory

__all__ = ("try_build_llm_compaction_outcome",)


async def try_build_llm_compaction_outcome(
    *,
    logger: LoggerProtocol,
    operation: str,
    pinned_prefix: list[JSONDict],
    before_anchor: list[JSONDict],
    anchor_message: JSONDict | None,
    after_anchor: list[JSONDict],
    summary_text: str | None,
    summarize_messages: Callable[[list[JSONDict]], Awaitable[str]],
    prompt_token_counter: PromptTokenCounter,
    base_request_payload: JSONDict,
    max_prompt_tokens: int,
    history_without_summary: list[JSONDict],
    existing_user_memory: UserMessageMemory | None,
    token_estimation_profile: TokenEstimationProfile | None = None,
) -> MessageHistoryCompactionOutcome | None:
    resolved_max_prompt_tokens = require_positive_int_strict(
        max_prompt_tokens,
        error_message="Compaction target prompt budget must be >= 1.",
    )
    try:
        candidate_history = await build_llm_compaction_candidate_history(
            pinned_prefix=pinned_prefix,
            before_anchor=before_anchor,
            anchor_message=anchor_message,
            after_anchor=after_anchor,
            summary_text=summary_text,
            summarize_messages=summarize_messages,
            prompt_token_counter=prompt_token_counter,
            base_request_payload=base_request_payload,
            max_prompt_tokens=resolved_max_prompt_tokens,
            token_estimation_profile=token_estimation_profile,
        )
    except ValidationError as exception:
        log_exception(
            logger,
            exception,
            message=(
                "Context compaction summarization failed validation; "
                "continuing with deterministic compaction."
            ),
            operation=operation,
            level="warning",
        )
        return None
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message=(
                "Context compaction summarization failed; "
                "continuing with deterministic compaction."
            ),
            operation=operation,
            level="warning",
        )
        return None
    if candidate_history is None:
        return None
    try:
        outcome = await prompt_token_counter.run_blocking(
            partial(
                _validate_llm_compaction_candidate,
                candidate_history=candidate_history,
                original_history=history_without_summary,
                existing_user_memory=existing_user_memory,
                prompt_token_counter=prompt_token_counter,
                base_request_payload=base_request_payload,
                resolved_max_prompt_tokens=resolved_max_prompt_tokens,
                token_estimation_profile=token_estimation_profile,
            ),
        )
    except ValidationError as exception:
        log_exception(
            logger,
            exception,
            message=(
                "Context compaction candidate failed validation; "
                "continuing with deterministic compaction."
            ),
            operation=operation,
            level="warning",
        )
        return None
    return outcome


def _validate_llm_compaction_candidate(
    *,
    candidate_history: list[JSONDict],
    original_history: list[JSONDict],
    existing_user_memory: UserMessageMemory | None,
    prompt_token_counter: PromptTokenCounter,
    base_request_payload: JSONDict,
    resolved_max_prompt_tokens: int,
    token_estimation_profile: TokenEstimationProfile | None,
) -> MessageHistoryCompactionOutcome:
    memory_compacted_messages = apply_user_message_memory_to_compacted_history(
        candidate_history=candidate_history,
        original_history=original_history,
        existing_memory=existing_user_memory,
        prompt_token_counter=prompt_token_counter,
        base_request_payload=base_request_payload,
        max_prompt_tokens=resolved_max_prompt_tokens,
        token_estimation_profile=token_estimation_profile,
    )
    compacted_messages, _changed = repair_openai_tool_message_sequence_for_internal_contracts(
        messages=memory_compacted_messages,
    )
    prompt_occupancy = require_compacted_history_within_budget(
        prompt_token_counter=prompt_token_counter,
        base_request_payload=base_request_payload,
        message_history=compacted_messages,
        target_prompt_tokens=resolved_max_prompt_tokens,
        maximum_prompt_tokens=resolved_max_prompt_tokens,
        protected_floor_reached=False,
        token_estimation_profile=token_estimation_profile,
    )
    return MessageHistoryCompactionOutcome(
        compacted_messages=compacted_messages,
        summary_source=COMPACTION_SUMMARY_SOURCE_LLM,
        prompt_occupancy=prompt_occupancy,
    )
