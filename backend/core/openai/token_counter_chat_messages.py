"""SoAI - Chat message token counting for prompt budget evaluation [backend/core/openai/token_counter_chat_messages.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from typing import TYPE_CHECKING

from tiktoken.core import Encoding

from core.openai.token_counter_parts import count_content_segment, count_tool_calls
from core.openai.token_counter_types import (
    MESSAGE_NAME_OVERHEAD_TOKENS,
    MESSAGE_OVERHEAD_TOKENS,
    REPLY_PRIMING_TOKENS,
)

if TYPE_CHECKING:
    from core.openai.protocols import PromptTokenCountStateProtocol
    from core.types.json import JSONValue

__all__ = ("count_chat_messages_tokens",)


def _count_message_content(
    *,
    content: JSONValue,
    max_total_characters: int,
    encoding: Encoding,
    state: PromptTokenCountStateProtocol,
    count_texts: Callable[[Iterable[str], Encoding, PromptTokenCountStateProtocol], int],
    is_exhausted: Callable[[PromptTokenCountStateProtocol], bool],
) -> int:
    if isinstance(content, str):
        return count_texts([content], encoding, state)
    if isinstance(content, list):
        total_tokens = 0
        for segment in content:
            if is_exhausted(state):
                break
            total_tokens += count_content_segment(
                segment,
                max_total_characters=max_total_characters,
                encoding=encoding,
                state=state,
                count_texts=count_texts,
                is_exhausted=is_exhausted,
            )
        return total_tokens
    if isinstance(content, dict):
        return count_content_segment(
            content,
            max_total_characters=max_total_characters,
            encoding=encoding,
            state=state,
            count_texts=count_texts,
            is_exhausted=is_exhausted,
        )
    if content is None:
        return 0
    return count_texts([str(content)], encoding, state)


def count_chat_messages_tokens(
    *,
    messages: Sequence[JSONValue],
    max_total_characters: int,
    encoding: Encoding,
    state: PromptTokenCountStateProtocol,
    count_texts: Callable[[Iterable[str], Encoding, PromptTokenCountStateProtocol], int],
    is_exhausted: Callable[[PromptTokenCountStateProtocol], bool],
) -> int:
    total_tokens = 0
    for message in messages:
        if not isinstance(message, dict):
            continue
        if is_exhausted(state):
            break
        total_tokens += MESSAGE_OVERHEAD_TOKENS
        total_tokens += count_texts([str(message.get("role") or "")], encoding, state)
        name_value = message.get("name")
        if isinstance(name_value, str) and name_value:
            total_tokens += MESSAGE_NAME_OVERHEAD_TOKENS
            total_tokens += count_texts([name_value], encoding, state)
        tool_call_id = message.get("tool_call_id")
        if isinstance(tool_call_id, str) and tool_call_id:
            total_tokens += count_texts([tool_call_id], encoding, state)
        content_value = message.get("content")
        total_tokens += _count_message_content(
            content=content_value,
            max_total_characters=max_total_characters,
            encoding=encoding,
            state=state,
            count_texts=count_texts,
            is_exhausted=is_exhausted,
        )
        total_tokens += count_tool_calls(
            message.get("tool_calls"),
            encoding=encoding,
            state=state,
            count_texts=count_texts,
            is_exhausted=is_exhausted,
        )
    return total_tokens + REPLY_PRIMING_TOKENS
