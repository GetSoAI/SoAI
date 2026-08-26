"""SoAI - User message selection and truncation for context compaction [backend/features/agent/runtime/context_compaction/user_memory_selection.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.openai.content_text_rendering import render_openai_content_text
from features.agent.runtime.context_compaction.token_counting import (
    count_compaction_text_tokens,
)
from features.agent.runtime.tool_image_relay_messages import (
    is_tool_image_relay_message,
)

if TYPE_CHECKING:
    from core.openai.token_counter import PromptTokenCounter
    from core.openai.token_estimation_profile import TokenEstimationProfile
    from core.types.json import JSONDict

__all__ = (
    "USER_MEMORY_HEAD_COUNT",
    "USER_MEMORY_MAX_HEAD_MESSAGE_TOKENS",
    "USER_MEMORY_MAX_USER_MESSAGE_TOKENS",
    "USER_MEMORY_TAIL_COUNT",
    "SelectedUserMessage",
    "collect_user_message_texts",
    "select_head_user_messages",
    "select_tail_user_messages",
    "truncate_user_message_to_limit",
)

USER_MEMORY_HEAD_COUNT: int = 6
USER_MEMORY_TAIL_COUNT: int = 9
USER_MEMORY_MAX_HEAD_MESSAGE_TOKENS: int = 512
USER_MEMORY_MAX_USER_MESSAGE_TOKENS: int = 256
_USER_MEMORY_TRUNCATION_SUFFIX: str = " […]"


@dataclass(frozen=True, slots=True)
class SelectedUserMessage:
    source_text: str
    memory_text: str


def truncate_user_message_to_limit(
    prompt_token_counter: PromptTokenCounter,
    *,
    text: str,
    model_name: str | None,
    max_message_tokens: int,
    token_estimation_profile: TokenEstimationProfile | None = None,
) -> str:
    normalized = str(text or "").strip()
    if not normalized:
        return ""
    if count_compaction_text_tokens(
        prompt_token_counter,
        text=normalized,
        model_name=model_name,
        token_estimation_profile=token_estimation_profile,
    ) <= int(max_message_tokens):
        return normalized
    low = 0
    high = len(normalized) - 1
    best_content = _USER_MEMORY_TRUNCATION_SUFFIX
    while low <= high:
        mid = (low + high) // 2
        candidate = f"{normalized[:mid]}{_USER_MEMORY_TRUNCATION_SUFFIX}"
        if count_compaction_text_tokens(
            prompt_token_counter,
            text=candidate,
            model_name=model_name,
            token_estimation_profile=token_estimation_profile,
        ) <= int(max_message_tokens):
            best_content = candidate
            low = mid + 1
            continue
        high = mid - 1
    return best_content


def collect_user_message_texts(message_history: list[JSONDict]) -> list[str]:
    texts: list[str] = []
    for message in message_history:
        if message.get("role") != "user" or is_tool_image_relay_message(message):
            continue
        text = render_openai_content_text(message.get("content")).strip()
        if text:
            texts.append(text)
    return texts


def _build_selected_user_message(
    prompt_token_counter: PromptTokenCounter,
    *,
    text: str,
    model_name: str | None,
    max_message_tokens: int,
    token_estimation_profile: TokenEstimationProfile | None = None,
) -> SelectedUserMessage | None:
    normalized = str(text or "").strip()
    if not normalized:
        return None
    memory_text = truncate_user_message_to_limit(
        prompt_token_counter,
        text=normalized,
        model_name=model_name,
        max_message_tokens=max_message_tokens,
        token_estimation_profile=token_estimation_profile,
    )
    if not memory_text:
        return None
    return SelectedUserMessage(source_text=normalized, memory_text=memory_text)


def select_head_user_messages(
    prompt_token_counter: PromptTokenCounter,
    *,
    user_texts: list[str],
    model_name: str | None,
    token_estimation_profile: TokenEstimationProfile | None = None,
) -> list[SelectedUserMessage]:
    selected: list[SelectedUserMessage] = []
    for text in user_texts:
        if len(selected) >= USER_MEMORY_HEAD_COUNT:
            break
        selected_message = _build_selected_user_message(
            prompt_token_counter,
            text=text,
            model_name=model_name,
            max_message_tokens=USER_MEMORY_MAX_HEAD_MESSAGE_TOKENS,
            token_estimation_profile=token_estimation_profile,
        )
        if selected_message is not None:
            selected.append(selected_message)
    return selected


def select_tail_user_messages(
    prompt_token_counter: PromptTokenCounter,
    *,
    user_texts: list[str],
    model_name: str | None,
    token_estimation_profile: TokenEstimationProfile | None = None,
) -> list[SelectedUserMessage]:
    selected: list[SelectedUserMessage] = []
    for text in reversed(user_texts):
        if len(selected) >= USER_MEMORY_TAIL_COUNT:
            break
        selected_message = _build_selected_user_message(
            prompt_token_counter,
            text=text,
            model_name=model_name,
            max_message_tokens=USER_MEMORY_MAX_USER_MESSAGE_TOKENS,
            token_estimation_profile=token_estimation_profile,
        )
        if selected_message is not None:
            selected.append(selected_message)
    selected.reverse()
    return selected
