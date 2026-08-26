"""SoAI - Context compaction candidate assembly [backend/features/agent/runtime/context_compaction/candidates.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.openai.chat_role_sets import OPENAI_PINNED_ROLES
from core.openai.content_text_rendering import render_openai_content_text
from features.agent.runtime.context_compaction.digest import (
    digest_compaction_unit,
    merge_context_summary,
)
from features.agent.runtime.context_compaction.history import (
    combine_compaction_buckets,
    resolve_preserved_user_index,
)
from features.agent.runtime.context_compaction.rewrite import (
    rewrite_history_for_compaction,
)
from features.agent.runtime.context_compaction.summary import (
    build_summary_message,
    is_context_summary_message,
)
from features.agent.runtime.context_compaction.token_counting import (
    count_history_prompt_tokens,
)
from features.agent.runtime.tool_image_relay_messages import is_tool_image_relay_message

if TYPE_CHECKING:
    from core.openai.token_counter import PromptTokenCounter
    from core.openai.token_estimation_profile import TokenEstimationProfile
    from core.types.json import JSONDict

__all__ = (
    "count_materialized_history_tokens",
    "has_compactable_history",
    "materialize_compacted_history",
    "merge_summary_with_messages",
    "resolve_truncation_target_index",
)


def materialize_compacted_history(
    *,
    pinned_prefix: list[JSONDict],
    before_anchor: list[JSONDict],
    anchor_message: JSONDict | None,
    after_anchor: list[JSONDict],
    summary_text: str | None,
) -> list[JSONDict]:
    summary_message = build_summary_message(summary_text) if summary_text else None
    return combine_compaction_buckets(
        pinned_prefix,
        before_anchor,
        anchor_message,
        after_anchor,
        summary_message=summary_message,
    )


def merge_summary_with_messages(summary_text: str | None, messages: list[JSONDict]) -> str | None:
    return merge_context_summary(summary_text, digest_compaction_unit(messages))


def count_materialized_history_tokens(
    *,
    prompt_token_counter: PromptTokenCounter,
    base_request_payload: JSONDict,
    pinned_prefix: list[JSONDict],
    before_anchor: list[JSONDict],
    anchor_message: JSONDict | None,
    after_anchor: list[JSONDict],
    summary_text: str | None,
    token_estimation_profile: TokenEstimationProfile | None = None,
) -> int:
    return count_history_prompt_tokens(
        prompt_token_counter=prompt_token_counter,
        base_request_payload=base_request_payload,
        message_history=rewrite_history_for_compaction(
            materialize_compacted_history(
                pinned_prefix=pinned_prefix,
                before_anchor=before_anchor,
                anchor_message=anchor_message,
                after_anchor=after_anchor,
                summary_text=summary_text,
            ),
        ),
        token_estimation_profile=token_estimation_profile,
    )


def resolve_truncation_target_index(message_history: list[JSONDict]) -> int | None:
    summary_index: int | None = None
    tool_index: int | None = None
    assistant_index: int | None = None
    user_index: int | None = None
    summary_size = -1
    tool_size = -1
    assistant_size = -1
    user_size = -1
    preserved_user_index = resolve_preserved_user_index(message_history)
    for index, message in enumerate(message_history):
        size = len(render_openai_content_text(message.get("content")))
        if is_context_summary_message(message):
            if size > summary_size:
                summary_index = index
                summary_size = size
            continue
        role = message.get("role")
        if (isinstance(role, str) and role in OPENAI_PINNED_ROLES) or (
            index == preserved_user_index
        ):
            continue
        if is_tool_image_relay_message(message):
            continue
        if role == "tool":
            if size > tool_size:
                tool_index = index
                tool_size = size
            continue
        if role == "assistant":
            if size > assistant_size:
                assistant_index = index
                assistant_size = size
            continue
        if size > user_size:
            user_index = index
            user_size = size
    candidates: list[tuple[int, int]] = []
    if summary_index is not None:
        candidates.append((summary_size, summary_index))
    if tool_index is not None:
        candidates.append((tool_size, tool_index))
    if assistant_index is not None:
        candidates.append((assistant_size, assistant_index))
    if user_index is not None:
        candidates.append((user_size, user_index))
    if candidates:
        best_size = max(size for size, _index in candidates)
        for size, index in candidates:
            if size == best_size:
                return index
    return None


def has_compactable_history(message_history: list[JSONDict]) -> bool:
    return resolve_truncation_target_index(message_history) is not None
