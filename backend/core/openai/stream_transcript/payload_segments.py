"""SoAI - OpenAI stream payload traversal [backend/core/openai/stream_transcript/payload_segments.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING

from core.openai.reasoning_text import REASONING_FIELD_NAMES, normalize_reasoning_text
from core.openai.stream_transcript.types import (
    StreamTextSegment,
    StreamTextSegmentLocation,
)
from core.openai.tool_call_stream_matching import (
    source_has_content,
    source_has_reasoning,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "build_choice_text_source",
    "extract_reasoning_text_from_source",
    "iter_choice_tool_call_sources",
    "iter_text_segment_locations_from_payload",
    "iter_text_segments_from_payload",
)


def extract_reasoning_text_from_source(source: JSONDict | None) -> str:
    if not isinstance(source, dict):
        return ""
    for key in REASONING_FIELD_NAMES:
        if key in source:
            return normalize_reasoning_text(source.get(key))
    return ""


def build_choice_text_source(choice: JSONDict) -> JSONDict | None:
    delta_value = choice.get("delta")
    delta = delta_value if isinstance(delta_value, dict) else None
    message_value = choice.get("message")
    message = message_value if isinstance(message_value, dict) else None
    source: JSONDict = {}
    reasoning_source: JSONDict | None = None
    if isinstance(delta, dict) and source_has_reasoning(delta):
        reasoning_source = delta
    elif isinstance(message, dict) and source_has_reasoning(message):
        reasoning_source = message
    if reasoning_source is not None:
        for key in REASONING_FIELD_NAMES:
            if key in reasoning_source:
                source[key] = reasoning_source.get(key)
                break
    if isinstance(delta, dict) and source_has_content(delta):
        source["content"] = delta.get("content")
    elif isinstance(message, dict) and source_has_content(message):
        source["content"] = message.get("content")
    else:
        text_value = choice.get("text")
        if isinstance(text_value, str) and text_value:
            source["content"] = text_value
    if not source:
        return None
    return source


def iter_choice_tool_call_sources(choice: JSONDict) -> Iterator[JSONDict]:
    delta_value = choice.get("delta")
    if isinstance(delta_value, dict) and "tool_calls" in delta_value:
        yield delta_value
    message_value = choice.get("message")
    if isinstance(message_value, dict) and "tool_calls" in message_value:
        yield message_value
    if "tool_calls" in choice:
        yield choice


def iter_text_segments_from_payload(payload: JSONValue | None) -> Iterator[StreamTextSegment]:
    for location in iter_text_segment_locations_from_payload(payload):
        yield location.segment


def iter_text_segment_locations_from_payload(
    payload: JSONValue | None,
    *,
    container: JSONDict | list[JSONValue] | None = None,
    key: str | int | None = None,
) -> Iterator[StreamTextSegmentLocation]:
    if payload is None:
        return
    if isinstance(payload, str):
        if payload:
            yield StreamTextSegmentLocation(
                segment=StreamTextSegment(channel="visible", text=payload),
                container=container,
                key=key,
            )
        return
    if isinstance(payload, list):
        for index, item in enumerate(payload):
            yield from iter_text_segment_locations_from_payload(
                item,
                container=payload,
                key=index,
            )
        return
    if not isinstance(payload, dict):
        return
    type_value = payload.get("type")
    type_key = type_value.strip().lower() if isinstance(type_value, str) else ""
    if type_key in {"thinking", "reasoning", "reasoning_text"}:
        reasoning_text = normalize_reasoning_text(payload)
        if reasoning_text:
            yield StreamTextSegmentLocation(
                segment=StreamTextSegment(channel="thinking", text=reasoning_text),
                container=None,
                key=None,
            )
        return
    if type_key and type_key not in {"text", "output_text", "input_text", "summary_text"}:
        return
    text_value = payload.get("text")
    if isinstance(text_value, str) and text_value:
        yield StreamTextSegmentLocation(
            segment=StreamTextSegment(channel="visible", text=text_value),
            container=payload,
            key="text",
        )
        return
    value_value = payload.get("value")
    if isinstance(value_value, str) and value_value:
        yield StreamTextSegmentLocation(
            segment=StreamTextSegment(channel="visible", text=value_value),
            container=payload,
            key="value",
        )
        return
    if "content" in payload:
        yield from iter_text_segment_locations_from_payload(
            payload.get("content"),
            container=payload,
            key="content",
        )
        return
    if "parts" in payload:
        yield from iter_text_segment_locations_from_payload(
            payload.get("parts"),
            container=payload,
            key="parts",
        )
