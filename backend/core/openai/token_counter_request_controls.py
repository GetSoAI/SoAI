"""SoAI - Token counting for request-level controls [backend/core/openai/token_counter_request_controls.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import TYPE_CHECKING

from tiktoken.core import Encoding

from core.serialization.json import serialize_json_compact_stable_default_str

if TYPE_CHECKING:
    from core.openai.protocols import PromptTokenCountStateProtocol
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "count_request_level_controls",
    "count_request_level_value",
)


def count_request_level_controls(
    *,
    request_payload: JSONDict,
    encoding: Encoding,
    state: PromptTokenCountStateProtocol,
    count_texts: Callable[[Iterable[str], Encoding, PromptTokenCountStateProtocol], int],
    is_exhausted: Callable[[PromptTokenCountStateProtocol], bool],
    max_field_characters: int,
) -> int:
    total_tokens = 0
    for field_name in ("tools", "tool_choice"):
        if is_exhausted(state):
            break
        field_value = request_payload.get(field_name)
        total_tokens += count_request_level_value(
            field_value,
            encoding,
            state,
            count_texts,
            is_exhausted,
            max_field_characters=max_field_characters,
        )
    return total_tokens


def _count_serialized_value_in_chunks(
    *,
    serialized_value: str,
    encoding: Encoding,
    state: PromptTokenCountStateProtocol,
    count_texts: Callable[[Iterable[str], Encoding, PromptTokenCountStateProtocol], int],
    is_exhausted: Callable[[PromptTokenCountStateProtocol], bool],
    max_field_characters: int,
) -> int:
    if not serialized_value:
        return 0
    chunk_size = max(1, int(max_field_characters))
    total_tokens = 0
    start = 0
    length = len(serialized_value)
    while start < length:
        if is_exhausted(state):
            break
        end = min(length, start + chunk_size)
        total_tokens += count_texts([serialized_value[start:end]], encoding, state)
        start = end
    return total_tokens


def count_request_level_value(
    value: JSONValue,
    encoding: Encoding,
    state: PromptTokenCountStateProtocol,
    count_texts: Callable[[Iterable[str], Encoding, PromptTokenCountStateProtocol], int],
    is_exhausted: Callable[[PromptTokenCountStateProtocol], bool],
    *,
    max_field_characters: int,
) -> int:
    if value is None:
        return 0
    if isinstance(value, str):
        return count_texts([value], encoding, state)
    if isinstance(value, dict | list | int | float | bool):
        serialized = serialize_json_compact_stable_default_str(value, ensure_ascii=False)
        return _count_serialized_value_in_chunks(
            serialized_value=serialized,
            encoding=encoding,
            state=state,
            count_texts=count_texts,
            is_exhausted=is_exhausted,
            max_field_characters=max_field_characters,
        )
    return count_texts([str(value)], encoding, state)
