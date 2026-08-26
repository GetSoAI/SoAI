"""SoAI - User message memory integration for context compaction [backend/features/agent/runtime/context_compaction/user_memory_integration.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.openai.chat_role_sets import OPENAI_PINNED_ROLES
from core.openai.request_fields import resolve_optional_model_name
from features.agent.runtime.context_compaction.budget import (
    truncate_message_content_to_fit_budget,
)
from features.agent.runtime.context_compaction.token_counting import (
    count_compaction_text_tokens,
    history_within_budget,
)
from features.agent.runtime.context_compaction.user_memory import (
    UserMessageMemory,
    build_user_message_memory_message,
    evict_one_low_priority_entry,
    merge_user_message_memory,
    remove_user_memory_entries_present_as_user_messages,
    render_user_message_memory_content,
    strip_user_message_memory_messages,
)
from features.agent.runtime.context_compaction.user_memory_selection import (
    USER_MEMORY_HEAD_COUNT,
    USER_MEMORY_MAX_HEAD_MESSAGE_TOKENS,
    USER_MEMORY_MAX_USER_MESSAGE_TOKENS,
    USER_MEMORY_TAIL_COUNT,
    collect_user_message_texts,
    select_head_user_messages,
    select_tail_user_messages,
    truncate_user_message_to_limit,
)

if TYPE_CHECKING:
    from core.openai.token_counter import PromptTokenCounter
    from core.openai.token_estimation_profile import TokenEstimationProfile
    from core.types.json import JSONDict

__all__ = ("apply_user_message_memory_to_compacted_history",)

_USER_MEMORY_MAX_MEMORY_TOKENS: int = (
    (USER_MEMORY_HEAD_COUNT * USER_MEMORY_MAX_HEAD_MESSAGE_TOKENS)
    + (USER_MEMORY_TAIL_COUNT * USER_MEMORY_MAX_USER_MESSAGE_TOKENS)
    + 2048
)
_USER_MEMORY_MAX_EXTRA_ENTRIES: int = 0


def _inject_user_memory_message(
    message_history: list[JSONDict],
    *,
    memory_message: JSONDict,
) -> list[JSONDict]:
    insert_at = 0
    while insert_at < len(message_history):
        role = message_history[insert_at].get("role")
        if role not in OPENAI_PINNED_ROLES:
            break
        insert_at += 1
    updated = list(message_history)
    updated.insert(insert_at, memory_message)
    return updated


def _truncate_context_summary_if_present(
    prompt_token_counter: PromptTokenCounter,
    *,
    base_request_payload: JSONDict,
    message_history: list[JSONDict],
    max_prompt_tokens: int,
    token_estimation_profile: TokenEstimationProfile | None,
) -> list[JSONDict]:
    summary_index: int | None = None
    for index, message in enumerate(message_history):
        content = message.get("content")
        if isinstance(content, str) and "<context_summary>" in content:
            summary_index = index
            break
    if summary_index is None:
        return message_history
    return truncate_message_content_to_fit_budget(
        prompt_token_counter=prompt_token_counter,
        base_request_payload=base_request_payload,
        message_history=message_history,
        message_index=summary_index,
        max_prompt_tokens=max_prompt_tokens,
        token_estimation_profile=token_estimation_profile,
    )


def apply_user_message_memory_to_compacted_history(
    *,
    candidate_history: list[JSONDict],
    original_history: list[JSONDict],
    existing_memory: UserMessageMemory | None,
    prompt_token_counter: PromptTokenCounter,
    base_request_payload: JSONDict,
    max_prompt_tokens: int,
    token_estimation_profile: TokenEstimationProfile | None = None,
) -> list[JSONDict]:
    _, stripped_candidate = strip_user_message_memory_messages(list(candidate_history))
    model_name = resolve_optional_model_name(base_request_payload)
    original_user_texts = collect_user_message_texts(original_history)
    candidate_user_texts = set(collect_user_message_texts(stripped_candidate))
    head = select_head_user_messages(
        prompt_token_counter,
        user_texts=original_user_texts,
        model_name=model_name,
        token_estimation_profile=token_estimation_profile,
    )
    tail = select_tail_user_messages(
        prompt_token_counter,
        user_texts=original_user_texts,
        model_name=model_name,
        token_estimation_profile=token_estimation_profile,
    )
    head_sources = {entry.source_text for entry in head}
    tail_sources = {entry.source_text for entry in tail}
    missing_head = [
        entry.memory_text for entry in head if entry.source_text not in candidate_user_texts
    ]
    missing_tail = [
        entry.memory_text
        for entry in tail
        if entry.source_text not in candidate_user_texts and entry.source_text not in head_sources
    ]
    extra_candidates: list[str] = []
    if _USER_MEMORY_MAX_EXTRA_ENTRIES > 0:
        for text in original_user_texts:
            if text in candidate_user_texts:
                continue
            if text in head_sources or text in tail_sources:
                continue
            truncated = truncate_user_message_to_limit(
                prompt_token_counter,
                text=text,
                model_name=model_name,
                max_message_tokens=USER_MEMORY_MAX_USER_MESSAGE_TOKENS,
                token_estimation_profile=token_estimation_profile,
            )
            if not truncated:
                continue
            extra_candidates.append(truncated)
            if len(extra_candidates) >= _USER_MEMORY_MAX_EXTRA_ENTRIES:
                break
    merged = merge_user_message_memory(
        existing_memory,
        head=missing_head,
        tail=missing_tail,
        extra=extra_candidates,
    )
    merged = remove_user_memory_entries_present_as_user_messages(
        merged,
        message_history=stripped_candidate,
    )
    if merged is None:
        return stripped_candidate
    while True:
        memory_text = render_user_message_memory_content(merged)
        if (
            count_compaction_text_tokens(
                prompt_token_counter,
                text=memory_text,
                model_name=model_name,
                token_estimation_profile=token_estimation_profile,
            )
            <= _USER_MEMORY_MAX_MEMORY_TOKENS
        ):
            break
        next_memory = evict_one_low_priority_entry(merged)
        if next_memory is None:
            merged = None
            break
        merged = next_memory
    if merged is None:
        return stripped_candidate
    memory_message = build_user_message_memory_message(merged)
    injected = _inject_user_memory_message(stripped_candidate, memory_message=memory_message)
    if history_within_budget(
        prompt_token_counter=prompt_token_counter,
        base_request_payload=base_request_payload,
        message_history=injected,
        max_prompt_tokens=max_prompt_tokens,
        token_estimation_profile=token_estimation_profile,
    ):
        return injected
    injected = _truncate_context_summary_if_present(
        prompt_token_counter,
        base_request_payload=base_request_payload,
        message_history=injected,
        max_prompt_tokens=max_prompt_tokens,
        token_estimation_profile=token_estimation_profile,
    )
    if history_within_budget(
        prompt_token_counter=prompt_token_counter,
        base_request_payload=base_request_payload,
        message_history=injected,
        max_prompt_tokens=max_prompt_tokens,
        token_estimation_profile=token_estimation_profile,
    ):
        return injected
    shrinking = merged
    while True:
        next_shrinking = evict_one_low_priority_entry(shrinking)
        if next_shrinking is None:
            return stripped_candidate
        shrinking = next_shrinking
        memory_message = build_user_message_memory_message(shrinking)
        injected = _inject_user_memory_message(stripped_candidate, memory_message=memory_message)
        injected = _truncate_context_summary_if_present(
            prompt_token_counter,
            base_request_payload=base_request_payload,
            message_history=injected,
            max_prompt_tokens=max_prompt_tokens,
            token_estimation_profile=token_estimation_profile,
        )
        if history_within_budget(
            prompt_token_counter=prompt_token_counter,
            base_request_payload=base_request_payload,
            message_history=injected,
            max_prompt_tokens=max_prompt_tokens,
            token_estimation_profile=token_estimation_profile,
        ):
            return injected
