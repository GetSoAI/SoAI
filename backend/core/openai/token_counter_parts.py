"""SoAI - Token counter message and tool-call parts [backend/core/openai/token_counter_parts.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Callable, Iterable

from tiktoken.core import Encoding

from core.openai.protocols import PromptTokenCountStateProtocol
from core.types.json import JSONValue
from core.validation.integers import is_strict_int

__all__ = (
    "count_content_segment",
    "count_image_reference",
    "count_tool_calls",
)

_DATA_URI_MARKER = ";base64,"


def count_image_reference(
    image_value: JSONValue,
    *,
    max_total_characters: int,
    encoding: Encoding,
    state: PromptTokenCountStateProtocol,
    count_texts: Callable[[Iterable[str], Encoding, PromptTokenCountStateProtocol], int],
) -> int:
    if isinstance(image_value, str) and image_value:
        if image_value.startswith("data:"):
            return _count_data_uri(
                image_value,
                max_total_characters=max_total_characters,
                encoding=encoding,
                state=state,
                count_texts=count_texts,
            )
        return count_texts([image_value], encoding, state)
    if not isinstance(image_value, dict):
        return 0
    url_value = image_value.get("url")
    if isinstance(url_value, str) and url_value:
        if url_value.startswith("data:"):
            return _count_data_uri(
                url_value,
                max_total_characters=max_total_characters,
                encoding=encoding,
                state=state,
                count_texts=count_texts,
            )
        return count_texts([url_value], encoding, state)
    return 0


def _count_data_uri(
    value: str,
    *,
    max_total_characters: int,
    encoding: Encoding,
    state: PromptTokenCountStateProtocol,
    count_texts: Callable[[Iterable[str], Encoding, PromptTokenCountStateProtocol], int],
) -> int:
    marker_index = value.find(_DATA_URI_MARKER)
    if marker_index < 0:
        return count_texts([value], encoding, state)
    payload_offset = min(
        marker_index + len(_DATA_URI_MARKER),
        max_total_characters + marker_index + len(_DATA_URI_MARKER),
    )
    return count_texts([value[:payload_offset]], encoding, state)


def count_content_segment(
    segment: JSONValue,
    *,
    max_total_characters: int,
    encoding: Encoding,
    state: PromptTokenCountStateProtocol,
    count_texts: Callable[[Iterable[str], Encoding, PromptTokenCountStateProtocol], int],
    is_exhausted: Callable[[PromptTokenCountStateProtocol], bool],
) -> int:
    if isinstance(segment, str):
        return count_texts([segment], encoding, state)
    if not isinstance(segment, dict):
        return 0
    segment_type = str(segment.get("type") or "").strip().lower()
    if segment_type in {"text", "input_text", "output_text", "summary_text", "reasoning_text"}:
        text_value = segment.get("text")
        if isinstance(text_value, str) and text_value:
            return count_texts([text_value], encoding, state)
        value_value = segment.get("value")
        if isinstance(value_value, str) and value_value:
            return count_texts([value_value], encoding, state)
        return 0
    if segment_type == "refusal":
        refusal_value = segment.get("refusal")
        if isinstance(refusal_value, str) and refusal_value:
            return count_texts([refusal_value], encoding, state)
        return 0
    if segment_type in {"image_url", "image", "input_image", "computer_screenshot"}:
        image_value = segment.get("image_url") or segment.get("image")
        return count_image_reference(
            image_value,
            max_total_characters=max_total_characters,
            encoding=encoding,
            state=state,
            count_texts=count_texts,
        )
    if segment_type in {"input_audio", "audio"}:
        audio_payload = segment.get("input_audio") or segment.get("audio") or segment
        if isinstance(audio_payload, dict):
            data_value = audio_payload.get("data")
            if isinstance(data_value, str) and data_value:
                return count_texts([data_value[:256]], encoding, state)
        return 0
    if segment_type in {"input_file", "file"}:
        return 0
    if is_exhausted(state):
        return 0
    return count_texts(
        [
            value
            for key, value in segment.items()
            if key != "type" and isinstance(value, str) and value
        ],
        encoding,
        state,
    )


def count_tool_calls(
    tool_calls: JSONValue,
    *,
    encoding: Encoding,
    state: PromptTokenCountStateProtocol,
    count_texts: Callable[[Iterable[str], Encoding, PromptTokenCountStateProtocol], int],
    is_exhausted: Callable[[PromptTokenCountStateProtocol], bool],
) -> int:
    if not isinstance(tool_calls, list):
        return 0
    if all(is_strict_int(item) for item in tool_calls):
        return len(tool_calls)
    total_tokens = 0
    for tool_call in tool_calls:
        if is_exhausted(state):
            break
        if not isinstance(tool_call, dict):
            continue
        total_tokens += count_texts([str(tool_call.get("id") or "")], encoding, state)
        total_tokens += count_texts([str(tool_call.get("type") or "")], encoding, state)
        function_payload = tool_call.get("function")
        if isinstance(function_payload, dict):
            function_name = function_payload.get("name")
            if isinstance(function_name, str) and function_name:
                total_tokens += count_texts([function_name], encoding, state)
            arguments_value = function_payload.get("arguments")
            if isinstance(arguments_value, str) and arguments_value:
                total_tokens += count_texts([arguments_value], encoding, state)
    return total_tokens
