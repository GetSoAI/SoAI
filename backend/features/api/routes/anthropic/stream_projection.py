"""SoAI - Anthropic Messages SSE projection [backend/features/api/routes/anthropic/stream_projection.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import aclosing
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError, ValidationError
from core.openai.openai_error_objects import (
    parse_openai_sse_error_frame_message_and_type,
)
from core.openai.stream_transcript.transcript import OpenAIStreamTranscript
from core.runtime.soai_identifiers import create_prefixed_hex_id
from core.serialization.json import serialize_json_compact_stable_strict
from core.streaming.sse_frames import format_sse_named_data_frame
from core.system_api.anthropic_error_types import resolve_anthropic_error_type
from core.validation.strict_numbers import coerce_optional_non_negative_int_strict
from features.api.routes.anthropic.response_projection import (
    AnthropicMessageProjectionSettings,
    build_anthropic_message,
)
from features.api.routes.anthropic.stream_content import (
    anthropic_block_stop_event,
    anthropic_content_events,
    anthropic_remaining_blocks,
    anthropic_text_delta_event,
    anthropic_text_start_event,
    anthropic_thinking_delta_event,
    anthropic_thinking_signature_event,
    anthropic_thinking_start_event,
)
from features.api.routes.anthropic.stream_heartbeat import (
    iter_anthropic_chunks_with_heartbeats,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("project_anthropic_stream",)


def _event(event_type: str, payload: JSONDict) -> bytes:
    return format_sse_named_data_frame(
        event_name=event_type,
        serialized_payload=serialize_json_compact_stable_strict(payload),
    ).encode("utf-8")


def _first_tool_anchor(transcript: OpenAIStreamTranscript) -> int | None:
    anchors: list[int] = []
    for tool_call in transcript.get_tool_calls():
        function = tool_call.get("function")
        call_id = tool_call.get("id")
        name = function.get("name") if isinstance(function, dict) else None
        if not isinstance(call_id, str) or not call_id or not isinstance(name, str) or not name:
            continue
        anchor = coerce_optional_non_negative_int_strict(tool_call.get("content_index_before"))
        if anchor is not None:
            anchors.append(anchor)
    return min(anchors) if anchors else None


def _project_stream_error(chunk: bytes) -> bytes | None:
    parsed_error = parse_openai_sse_error_frame_message_and_type(chunk)
    if parsed_error is None:
        return None
    message, error_type = parsed_error
    return _event(
        "error",
        {
            "type": "error",
            "error": {
                "type": resolve_anthropic_error_type(upstream_error_type=error_type),
                "message": message or error_type,
            },
        },
    )


async def project_anthropic_stream(
    upstream: AsyncGenerator[bytes],
    *,
    transcript: OpenAIStreamTranscript,
    settings: AnthropicMessageProjectionSettings,
) -> AsyncGenerator[bytes]:
    message_id = create_prefixed_hex_id("msg")
    heartbeat_stream = iter_anthropic_chunks_with_heartbeats(upstream)
    async with aclosing(upstream), aclosing(heartbeat_stream) as owned_stream:
        yield _event(
            "message_start",
            {
                "type": "message_start",
                "message": {
                    "id": message_id,
                    "type": "message",
                    "role": "assistant",
                    "model": settings.model,
                    "content": [],
                    "stop_reason": None,
                    "stop_sequence": None,
                    "usage": {
                        "input_tokens": settings.prompt_tokens,
                        "output_tokens": 0,
                        "cache_creation_input_tokens": 0,
                        "cache_read_input_tokens": 0,
                    },
                },
            },
        )
        content_index = 0
        emitted_text_length = 0
        emitted_thinking_length = 0
        text_open = False
        thinking_open = False
        tool_barrier = False
        emit_visible_text = settings.structured_output_schema is None
        observed_tool_anchors: dict[str, int] = {}
        async for chunk in owned_stream:
            if chunk is None:
                yield _event("ping", {"type": "ping"})
                continue
            error_event = _project_stream_error(chunk)
            if error_event is not None:
                yield error_event
                return
            transcript.feed(chunk)
            for tool_call in transcript.get_tool_calls():
                call_id = tool_call.get("id")
                anchor = coerce_optional_non_negative_int_strict(
                    tool_call.get("content_index_before")
                )
                if (
                    isinstance(call_id, str)
                    and call_id
                    and anchor is not None
                    and call_id not in observed_tool_anchors
                ):
                    observed_tool_anchors[call_id] = anchor
            thinking_deltas = transcript.drain_thinking_text_deltas()
            if settings.include_thinking:
                for delta in thinking_deltas:
                    if text_open:
                        yield anthropic_block_stop_event(_event, content_index)
                        content_index += 1
                        text_open = False
                    if not thinking_open:
                        yield anthropic_thinking_start_event(_event, content_index)
                        thinking_open = True
                    yield anthropic_thinking_delta_event(_event, content_index, delta)
                    emitted_thinking_length += len(delta)
            tool_anchor = _first_tool_anchor(transcript)
            if tool_anchor is not None and not tool_barrier:
                visible_text = transcript.get_visible_text()
                prefix_end = min(len(visible_text), tool_anchor)
                prefix = visible_text[emitted_text_length:prefix_end]
                if emit_visible_text and prefix:
                    if thinking_open:
                        yield anthropic_thinking_signature_event(_event, content_index)
                        yield anthropic_block_stop_event(_event, content_index)
                        content_index += 1
                        thinking_open = False
                    if not text_open:
                        yield anthropic_text_start_event(_event, content_index)
                        text_open = True
                    yield anthropic_text_delta_event(_event, content_index, prefix)
                    emitted_text_length += len(prefix)
                transcript.drain_visible_text_deltas()
                if thinking_open:
                    yield anthropic_thinking_signature_event(_event, content_index)
                    yield anthropic_block_stop_event(_event, content_index)
                    content_index += 1
                    thinking_open = False
                if text_open:
                    yield anthropic_block_stop_event(_event, content_index)
                    content_index += 1
                    text_open = False
                tool_barrier = True
            deltas = transcript.drain_visible_text_deltas()
            if emit_visible_text and not tool_barrier:
                for delta in deltas:
                    if thinking_open:
                        yield anthropic_thinking_signature_event(_event, content_index)
                        yield anthropic_block_stop_event(_event, content_index)
                        content_index += 1
                        thinking_open = False
                    if not text_open:
                        yield anthropic_text_start_event(_event, content_index)
                        text_open = True
                    yield anthropic_text_delta_event(_event, content_index, delta)
                    emitted_text_length += len(delta)
    transcript.finalize()
    try:
        message = build_anthropic_message(
            transcript,
            settings,
            tool_content_anchors=observed_tool_anchors,
        )
    except (StateError, ValidationError):
        yield _event(
            "error",
            {
                "type": "error",
                "error": {
                    "type": "api_error",
                    "message": "The upstream response could not be projected safely.",
                },
            },
        )
        return
    content_value = message.get("content")
    content_blocks = (
        [block for block in content_value if isinstance(block, dict)]
        if isinstance(content_value, list)
        else []
    )
    final_tool_anchor = _first_tool_anchor(transcript)
    if final_tool_anchor is not None and not tool_barrier:
        tool_barrier = True
    thinking_deltas = transcript.drain_thinking_text_deltas()
    if settings.include_thinking:
        for delta in thinking_deltas:
            if text_open:
                yield anthropic_block_stop_event(_event, content_index)
                content_index += 1
                text_open = False
            if not thinking_open:
                yield anthropic_thinking_start_event(_event, content_index)
                thinking_open = True
            yield anthropic_thinking_delta_event(_event, content_index, delta)
            emitted_thinking_length += len(delta)
    if emit_visible_text and not tool_barrier:
        for delta in transcript.drain_visible_text_deltas():
            if thinking_open:
                yield anthropic_thinking_signature_event(_event, content_index)
                yield anthropic_block_stop_event(_event, content_index)
                content_index += 1
                thinking_open = False
            if not text_open:
                yield anthropic_text_start_event(_event, content_index)
                text_open = True
            yield anthropic_text_delta_event(_event, content_index, delta)
            emitted_text_length += len(delta)
    if thinking_open:
        yield anthropic_thinking_signature_event(_event, content_index)
        yield anthropic_block_stop_event(_event, content_index)
        content_index += 1
    if text_open:
        yield anthropic_block_stop_event(_event, content_index)
        content_index += 1
    remaining_blocks = anthropic_remaining_blocks(
        content_blocks,
        emitted_text_length=emitted_text_length if emit_visible_text else 0,
        emitted_thinking_length=emitted_thinking_length,
        emitted_tool_ids=set(),
    )
    for event in anthropic_content_events(
        _event,
        remaining_blocks,
        start_index=content_index,
    ):
        yield event
    usage = message.get("usage")
    output_tokens = usage.get("output_tokens", 0) if isinstance(usage, dict) else 0
    yield _event(
        "message_delta",
        {
            "type": "message_delta",
            "delta": {
                "stop_reason": message.get("stop_reason"),
                "stop_sequence": message.get("stop_sequence"),
            },
            "usage": usage if isinstance(usage, dict) else {"output_tokens": output_tokens},
        },
    )
    yield _event("message_stop", {"type": "message_stop"})
