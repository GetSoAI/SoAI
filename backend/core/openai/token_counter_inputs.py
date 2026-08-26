"""SoAI - Token counter input payload handling [backend/core/openai/token_counter_inputs.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Callable, Iterable

from tiktoken.core import Encoding

from core.openai.protocols import PromptTokenCountStateProtocol
from core.types.json import JSONDict, JSONValue
from core.validation.integers import is_strict_int

__all__ = ("count_input_tokens",)


def _count_responses_content_parts(
    *,
    content_value: JSONValue,
    encoding: Encoding,
    state: PromptTokenCountStateProtocol,
    count_texts: Callable[[Iterable[str], Encoding, PromptTokenCountStateProtocol], int],
    is_counting_exhausted: Callable[[PromptTokenCountStateProtocol], bool],
) -> int:
    if content_value is None:
        return 0
    if isinstance(content_value, str) and content_value:
        return count_texts([content_value], encoding, state)
    if not isinstance(content_value, list):
        return 0
    total_tokens = 0
    for part in content_value:
        if is_counting_exhausted(state):
            break
        if isinstance(part, str) and part:
            total_tokens += count_texts([part], encoding, state)
            continue
        if isinstance(part, dict):
            text_value = part.get("text")
            if isinstance(text_value, str) and text_value:
                total_tokens += count_texts([text_value], encoding, state)
                continue
            transcript_value = part.get("transcript")
            if isinstance(transcript_value, str) and transcript_value:
                total_tokens += count_texts([transcript_value], encoding, state)
                continue
            continue
        if part is None:
            continue
        total_tokens += count_texts([str(part)], encoding, state)
    return total_tokens


def _count_responses_input_item_tokens(
    *,
    item: JSONDict,
    encoding: Encoding,
    state: PromptTokenCountStateProtocol,
    count_texts: Callable[[Iterable[str], Encoding, PromptTokenCountStateProtocol], int],
    is_counting_exhausted: Callable[[PromptTokenCountStateProtocol], bool],
) -> int:
    total_tokens = 0
    total_tokens += _count_responses_content_parts(
        content_value=item.get("content"),
        encoding=encoding,
        state=state,
        count_texts=count_texts,
        is_counting_exhausted=is_counting_exhausted,
    )
    for field_name in ("arguments", "output", "input"):
        if is_counting_exhausted(state):
            break
        value = item.get(field_name)
        if isinstance(value, str) and value:
            total_tokens += count_texts([value], encoding, state)
    return total_tokens


def count_input_tokens(
    *,
    input_value: JSONValue,
    encoding: Encoding,
    state: PromptTokenCountStateProtocol,
    count_texts: Callable[[Iterable[str], Encoding, PromptTokenCountStateProtocol], int],
    count_chat_messages: Callable[[list[JSONValue], Encoding, PromptTokenCountStateProtocol], int],
    is_counting_exhausted: Callable[[PromptTokenCountStateProtocol], bool],
) -> int | None:
    if isinstance(input_value, str):
        return count_texts([input_value], encoding, state)
    if isinstance(input_value, dict):
        if isinstance(input_value.get("type"), str):
            return _count_responses_input_item_tokens(
                item=input_value,
                encoding=encoding,
                state=state,
                count_texts=count_texts,
                is_counting_exhausted=is_counting_exhausted,
            )
        return count_chat_messages([input_value], encoding, state)
    if not isinstance(input_value, list):
        return None
    if all(is_strict_int(item) for item in input_value):
        return len(input_value)
    total_tokens = 0
    has_responses_items = any(
        isinstance(item, dict) and isinstance(item.get("type"), str) for item in input_value
    )
    for item in input_value:
        if is_counting_exhausted(state):
            break
        if isinstance(item, str) and item:
            total_tokens += count_texts([item], encoding, state)
            continue
        if isinstance(item, dict):
            if has_responses_items and isinstance(item.get("type"), str):
                total_tokens += _count_responses_input_item_tokens(
                    item=item,
                    encoding=encoding,
                    state=state,
                    count_texts=count_texts,
                    is_counting_exhausted=is_counting_exhausted,
                )
            else:
                total_tokens += count_chat_messages([item], encoding, state)
            continue
        if isinstance(item, list) and all(is_strict_int(token) for token in item):
            total_tokens += len(item)
            continue
        if item is None:
            continue
        total_tokens += count_texts([str(item)], encoding, state)
    return total_tokens
