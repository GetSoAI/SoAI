"""SoAI - Text delta extraction for OpenAI streaming SSE events [backend/core/openai/streaming_text_deltas.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.openai.sse_frame_payloads import parse_openai_sse_frame_payloads
from core.openai.stream_transcript.payload_segments import (
    build_choice_text_source,
    extract_reasoning_text_from_source,
    iter_choice_tool_call_sources,
    iter_text_segments_from_payload,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "extract_openai_streaming_all_output_deltas",
    "extract_openai_streaming_event_id",
    "extract_openai_streaming_event_object",
    "extract_openai_streaming_output_deltas",
    "extract_openai_streaming_text_deltas",
)


def _extract_tool_call_output_deltas(choice_item: JSONDict) -> tuple[str, ...]:
    deltas: list[str] = []
    for tool_call_source in iter_choice_tool_call_sources(choice_item):
        tool_calls_value = tool_call_source.get("tool_calls")
        if isinstance(tool_calls_value, list):
            for call_item in tool_calls_value:
                if not isinstance(call_item, dict):
                    continue
                function_value = call_item.get("function")
                if isinstance(function_value, dict):
                    name_value = function_value.get("name")
                    if isinstance(name_value, str) and name_value:
                        deltas.append(name_value)
                    arguments_value = function_value.get("arguments")
                    if isinstance(arguments_value, str) and arguments_value:
                        deltas.append(arguments_value)
                arguments_value = call_item.get("arguments")
                if isinstance(arguments_value, str) and arguments_value:
                    deltas.append(arguments_value)
    function_call_value = None
    delta_value = choice_item.get("delta")
    if isinstance(delta_value, dict):
        function_call_value = delta_value.get("function_call")
    if not isinstance(function_call_value, dict):
        message_value = choice_item.get("message")
        if isinstance(message_value, dict):
            function_call_value = message_value.get("function_call")
    if isinstance(function_call_value, dict):
        name_value = function_call_value.get("name")
        if isinstance(name_value, str) and name_value:
            deltas.append(name_value)
        arguments_value = function_call_value.get("arguments")
        if isinstance(arguments_value, str) and arguments_value:
            deltas.append(arguments_value)
    return tuple(deltas)


def extract_openai_streaming_event_id(sse_frame: str) -> str | None:
    if not sse_frame:
        return None
    for decoded_dict in parse_openai_sse_frame_payloads(sse_frame):
        candidate = decoded_dict.get("id")
        if isinstance(candidate, str) and candidate:
            return candidate
    return None


def extract_openai_streaming_event_object(sse_frame: str) -> str | None:
    if not sse_frame:
        return None
    for decoded_dict in parse_openai_sse_frame_payloads(sse_frame):
        candidate = decoded_dict.get("object")
        if isinstance(candidate, str) and candidate:
            return candidate
    return None


def extract_openai_streaming_text_deltas(sse_frame: str) -> tuple[str, ...]:
    if not sse_frame:
        return ()
    deltas: list[str] = []
    for decoded_dict in parse_openai_sse_frame_payloads(sse_frame):
        choices_value = decoded_dict.get("choices")
        choices = choices_value if isinstance(choices_value, list) else []
        for choice_item in choices:
            if not isinstance(choice_item, dict):
                continue
            text_source = build_choice_text_source(choice_item)
            if text_source is None or "content" not in text_source:
                continue
            for segment in iter_text_segments_from_payload(text_source.get("content")):
                if segment.channel == "visible" and segment.text:
                    deltas.append(segment.text)
    return tuple(deltas)


def extract_openai_streaming_output_deltas(
    sse_frame: str,
    *,
    include_tool_calls: bool = True,
) -> tuple[str, ...]:
    if not sse_frame:
        return ()
    deltas: list[str] = []
    for decoded_dict in parse_openai_sse_frame_payloads(sse_frame):
        choices_value = decoded_dict.get("choices")
        choices = choices_value if isinstance(choices_value, list) else []
        for choice_item in choices:
            if not isinstance(choice_item, dict):
                continue
            text_source = build_choice_text_source(choice_item)
            if text_source is not None and "content" in text_source:
                for segment in iter_text_segments_from_payload(text_source.get("content")):
                    if segment.channel == "visible" and segment.text:
                        deltas.append(segment.text)
            delta_value = choice_item.get("delta")
            if isinstance(delta_value, dict):
                refusal_value = delta_value.get("refusal")
                if isinstance(refusal_value, str) and refusal_value:
                    deltas.append(refusal_value)
            if include_tool_calls:
                deltas.extend(_extract_tool_call_output_deltas(choice_item))
    return tuple(deltas)


def extract_openai_streaming_all_output_deltas(
    sse_frame: str,
    *,
    include_tool_calls: bool = True,
) -> tuple[str, ...]:
    if not sse_frame:
        return ()
    deltas: list[str] = []
    for decoded_dict in parse_openai_sse_frame_payloads(sse_frame):
        choices_value = decoded_dict.get("choices")
        choices = choices_value if isinstance(choices_value, list) else []
        for choice_item in choices:
            if not isinstance(choice_item, dict):
                continue
            text_source = build_choice_text_source(choice_item)
            if text_source is not None:
                reasoning_text = extract_reasoning_text_from_source(text_source)
                if reasoning_text:
                    deltas.append(reasoning_text)
                if "content" in text_source:
                    for segment in iter_text_segments_from_payload(text_source.get("content")):
                        if segment.text:
                            deltas.append(segment.text)
            delta_value = choice_item.get("delta")
            if isinstance(delta_value, dict):
                refusal_value = delta_value.get("refusal")
                if isinstance(refusal_value, str) and refusal_value:
                    deltas.append(refusal_value)
            if include_tool_calls:
                deltas.extend(_extract_tool_call_output_deltas(choice_item))
    return tuple(deltas)
