"""SoAI - Deterministic context compaction reduction [backend/features/agent/runtime/context_compaction/deterministic_reduction.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.logging.trace import get_logger
from features.agent.runtime.context_compaction.budget import (
    truncate_message_content_to_fit_budget,
)
from features.agent.runtime.context_compaction.candidates import (
    count_materialized_history_tokens,
    materialize_compacted_history,
    merge_summary_with_messages,
    resolve_truncation_target_index,
)
from features.agent.runtime.context_compaction.history import (
    combine_compaction_buckets,
    count_tool_blocks,
    split_after_anchor_for_compaction,
    split_compaction_buckets,
    take_oldest_compaction_unit,
)
from features.agent.runtime.context_compaction.message_replacement import (
    replace_message_content_with_truncation_stub,
)
from features.agent.runtime.context_compaction.outcome import (
    DeterministicReductionOutcome,
)
from features.agent.runtime.context_compaction.rewrite import rewrite_tool_message
from features.agent.runtime.context_compaction.summary import (
    build_context_compaction_placeholder_message,
    strip_context_summary_messages,
)
from features.agent.runtime.context_compaction.token_counting import (
    history_within_budget,
)

if TYPE_CHECKING:
    from core.openai.token_counter import PromptTokenCounter
    from core.openai.token_estimation_profile import TokenEstimationProfile
    from core.types.json import JSONDict

__all__ = ("reduce_history_deterministically",)

LOGGER_NAME = "SoAI.features.agent.deterministic_reduction"
_COMPACTION_SAFETY_ITERATION_LIMIT: int = 500


def reduce_history_deterministically(
    *,
    history_without_summary: list[JSONDict],
    summary_text: str | None,
    prompt_token_counter: PromptTokenCounter,
    base_request_payload: JSONDict,
    max_prompt_tokens: int,
    token_estimation_profile: TokenEstimationProfile | None = None,
) -> DeterministicReductionOutcome:
    compacted_history = list(history_without_summary)
    preserved_after_anchor_tool_blocks = 2
    safety_iterations = 0
    protected_floor_reached = False
    while True:
        pinned_prefix, before_anchor, anchor_message, after_anchor = split_compaction_buckets(
            compacted_history,
        )
        if count_materialized_history_tokens(
            prompt_token_counter=prompt_token_counter,
            base_request_payload=base_request_payload,
            pinned_prefix=pinned_prefix,
            before_anchor=before_anchor,
            anchor_message=anchor_message,
            after_anchor=after_anchor,
            summary_text=summary_text,
            token_estimation_profile=token_estimation_profile,
        ) <= int(max_prompt_tokens):
            break
        safety_iterations += 1
        if safety_iterations > _COMPACTION_SAFETY_ITERATION_LIMIT:
            get_logger(LOGGER_NAME).warning(
                "Compaction safety iteration limit reached without fitting within budget (safety_iterations=%s, budget_tokens=%s).",
                safety_iterations,
                int(max_prompt_tokens),
            )
            break
        if before_anchor:
            oldest_unit, remaining_before_anchor = take_oldest_compaction_unit(before_anchor)
            summary_text = merge_summary_with_messages(summary_text, oldest_unit)
            compacted_history = combine_compaction_buckets(
                pinned_prefix,
                remaining_before_anchor,
                anchor_message,
                after_anchor,
            )
            continue
        compactable_after_anchor, preserved_after_anchor = split_after_anchor_for_compaction(
            after_anchor,
            preserve_tool_blocks=preserved_after_anchor_tool_blocks,
        )
        if compactable_after_anchor:
            oldest_unit, remaining_after_prefix = take_oldest_compaction_unit(
                compactable_after_anchor,
            )
            summary_text = merge_summary_with_messages(summary_text, oldest_unit)
            compacted_history = combine_compaction_buckets(
                pinned_prefix,
                before_anchor,
                anchor_message,
                remaining_after_prefix + preserved_after_anchor,
            )
            continue
        if preserved_after_anchor_tool_blocks > 0 and count_tool_blocks(after_anchor) >= 1:
            preserved_after_anchor_tool_blocks -= 1
            continue
        if not compacted_history:
            compacted_history = [build_context_compaction_placeholder_message()]
            break
        truncated_history = _truncate_materialized_history(
            prompt_token_counter=prompt_token_counter,
            base_request_payload=base_request_payload,
            max_prompt_tokens=max_prompt_tokens,
            token_estimation_profile=token_estimation_profile,
            pinned_prefix=pinned_prefix,
            before_anchor=before_anchor,
            anchor_message=anchor_message,
            after_anchor=after_anchor,
            summary_text=summary_text,
        )
        truncated_summary, truncated_history = strip_context_summary_messages(truncated_history)
        if truncated_history == compacted_history and truncated_summary == summary_text:
            protected_floor_reached = True
            break
        summary_text = truncated_summary
        compacted_history = truncated_history
    pinned_prefix, before_anchor, anchor_message, after_anchor = split_compaction_buckets(
        compacted_history,
    )
    return DeterministicReductionOutcome(
        compacted_messages=materialize_compacted_history(
            pinned_prefix=pinned_prefix,
            before_anchor=before_anchor,
            anchor_message=anchor_message,
            after_anchor=after_anchor,
            summary_text=summary_text,
        ),
        protected_floor_reached=protected_floor_reached,
    )


def _truncate_materialized_history(
    *,
    prompt_token_counter: PromptTokenCounter,
    base_request_payload: JSONDict,
    max_prompt_tokens: int,
    token_estimation_profile: TokenEstimationProfile | None,
    pinned_prefix: list[JSONDict],
    before_anchor: list[JSONDict],
    anchor_message: JSONDict | None,
    after_anchor: list[JSONDict],
    summary_text: str | None,
) -> list[JSONDict]:
    materialized_history = materialize_compacted_history(
        pinned_prefix=pinned_prefix,
        before_anchor=before_anchor,
        anchor_message=anchor_message,
        after_anchor=after_anchor,
        summary_text=summary_text,
    )
    target_index = resolve_truncation_target_index(materialized_history)
    if target_index is None:
        return materialized_history
    if materialized_history[target_index].get("role") == "tool":
        updated_history = list(materialized_history)
        updated_history[target_index] = rewrite_tool_message(materialized_history[target_index])
        return updated_history
    truncated_history = truncate_message_content_to_fit_budget(
        prompt_token_counter=prompt_token_counter,
        base_request_payload=base_request_payload,
        message_history=materialized_history,
        message_index=target_index,
        max_prompt_tokens=int(max_prompt_tokens),
        token_estimation_profile=token_estimation_profile,
    )
    if history_within_budget(
        prompt_token_counter=prompt_token_counter,
        base_request_payload=base_request_payload,
        message_history=truncated_history,
        max_prompt_tokens=int(max_prompt_tokens),
        token_estimation_profile=token_estimation_profile,
    ):
        return truncated_history
    return replace_message_content_with_truncation_stub(
        message_history=truncated_history,
        message_index=target_index,
    )
