"""SoAI - LLM-assisted candidate history builder for compaction [backend/features/agent/runtime/context_compaction/llm_candidate.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from functools import partial
from typing import TYPE_CHECKING

from features.agent.runtime.context_compaction.candidates import (
    materialize_compacted_history,
)
from features.agent.runtime.context_compaction.digest import merge_context_summary
from features.agent.runtime.context_compaction.history import (
    count_tool_blocks,
    split_after_anchor_for_compaction,
)
from features.agent.runtime.context_compaction.rewrite import (
    rewrite_history_for_compaction,
)
from features.agent.runtime.context_compaction.token_counting import (
    history_within_budget,
)
from features.agent.runtime.request_messages import strip_internal_message_metadata
from features.agent.session.compaction_limits import (
    AGENT_COMPACTION_PRESERVE_BEFORE_ANCHOR_HEAD_MESSAGES,
    AGENT_COMPACTION_PRESERVE_BEFORE_ANCHOR_TAIL_MESSAGES,
)

if TYPE_CHECKING:
    from core.openai.token_counter import PromptTokenCounter
    from core.openai.token_estimation_profile import TokenEstimationProfile
    from core.types.json import JSONDict

__all__ = ("build_llm_compaction_candidate_history",)

_PRESERVED_AFTER_ANCHOR_TOOL_BLOCK_COUNTS: tuple[int, ...] = (2, 1, 0)


def _split_before_anchor_for_llm_compaction(
    before_anchor: list[JSONDict],
) -> tuple[list[JSONDict], list[JSONDict]]:
    if len(before_anchor) <= 1:
        return list(before_anchor), []
    head_limit = max(0, int(AGENT_COMPACTION_PRESERVE_BEFORE_ANCHOR_HEAD_MESSAGES))
    tail_limit = max(0, int(AGENT_COMPACTION_PRESERVE_BEFORE_ANCHOR_TAIL_MESSAGES))
    max_preserved = max(0, len(before_anchor) - 1)
    tail_count = min(tail_limit, max_preserved)
    head_capacity = max(0, max_preserved - tail_count)
    head_count = min(head_limit, head_capacity)
    tail_start = max(head_count, len(before_anchor) - tail_count)
    preserved_head = list(before_anchor[:head_count])
    preserved_tail = list(before_anchor[tail_start:])
    compactable = list(before_anchor[head_count:tail_start])
    return preserved_head + preserved_tail, compactable


async def _build_llm_summary_text(
    *,
    summary_text: str | None,
    compactable_messages: list[JSONDict],
    summarize_messages: Callable[[list[JSONDict]], Awaitable[str]],
) -> str | None:
    if not compactable_messages:
        return None
    summary = await summarize_messages(strip_internal_message_metadata(compactable_messages))
    if not str(summary or "").strip():
        return None
    return merge_context_summary(summary_text, str(summary).splitlines())


def _build_candidate_history(
    *,
    pinned_prefix: list[JSONDict],
    before_anchor: list[JSONDict],
    anchor_message: JSONDict | None,
    after_anchor: list[JSONDict],
    merged_summary: str,
) -> list[JSONDict]:
    return rewrite_history_for_compaction(
        materialize_compacted_history(
            pinned_prefix=pinned_prefix,
            before_anchor=before_anchor,
            anchor_message=anchor_message,
            after_anchor=after_anchor,
            summary_text=merged_summary,
        ),
    )


async def build_llm_compaction_candidate_history(
    *,
    pinned_prefix: list[JSONDict],
    before_anchor: list[JSONDict],
    anchor_message: JSONDict | None,
    after_anchor: list[JSONDict],
    summary_text: str | None,
    summarize_messages: Callable[[list[JSONDict]], Awaitable[str]],
    prompt_token_counter: PromptTokenCounter,
    base_request_payload: JSONDict,
    max_prompt_tokens: int,
    token_estimation_profile: TokenEstimationProfile | None = None,
) -> list[JSONDict] | None:
    preserved_before, compactable_before = _split_before_anchor_for_llm_compaction(before_anchor)
    preserve_attempts = (
        _PRESERVED_AFTER_ANCHOR_TOOL_BLOCK_COUNTS if count_tool_blocks(after_anchor) > 0 else (0,)
    )
    for preserve_tool_blocks in preserve_attempts:
        compactable_after, preserved_after = split_after_anchor_for_compaction(
            after_anchor,
            preserve_tool_blocks=preserve_tool_blocks,
        )
        compactable_messages = compactable_before + compactable_after
        merged_summary = await _build_llm_summary_text(
            summary_text=summary_text,
            compactable_messages=compactable_messages,
            summarize_messages=summarize_messages,
        )
        if merged_summary is None:
            continue
        candidate_history = _build_candidate_history(
            pinned_prefix=pinned_prefix,
            before_anchor=preserved_before,
            anchor_message=anchor_message,
            after_anchor=preserved_after,
            merged_summary=merged_summary,
        )
        if await prompt_token_counter.run_blocking(
            partial(
                history_within_budget,
                prompt_token_counter=prompt_token_counter,
                base_request_payload=base_request_payload,
                message_history=candidate_history,
                max_prompt_tokens=max_prompt_tokens,
                token_estimation_profile=token_estimation_profile,
            ),
        ):
            return candidate_history
    return None
