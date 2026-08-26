"""SoAI - Anthropic stream content block events [backend/features/api/routes/anthropic/stream_content.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Callable

from core.serialization.json import serialize_json_compact_stable_strict
from core.types.json import JSONDict

__all__ = (
    "SOAI_ANTHROPIC_THINKING_SIGNATURE",
    "anthropic_block_stop_event",
    "anthropic_content_events",
    "anthropic_remaining_blocks",
    "anthropic_text_delta_event",
    "anthropic_text_start_event",
    "anthropic_thinking_delta_event",
    "anthropic_thinking_signature_event",
    "anthropic_thinking_start_event",
    "anthropic_tool_delta_event",
    "anthropic_tool_start_event",
)

SOAI_ANTHROPIC_THINKING_SIGNATURE = "soai"


def anthropic_text_start_event(event: Callable[[str, JSONDict], bytes], index: int) -> bytes:
    return event(
        "content_block_start",
        {
            "type": "content_block_start",
            "index": index,
            "content_block": {"type": "text", "text": ""},
        },
    )


def anthropic_text_delta_event(
    event: Callable[[str, JSONDict], bytes], index: int, text: str
) -> bytes:
    return event(
        "content_block_delta",
        {
            "type": "content_block_delta",
            "index": index,
            "delta": {"type": "text_delta", "text": text},
        },
    )


def anthropic_thinking_start_event(event: Callable[[str, JSONDict], bytes], index: int) -> bytes:
    return event(
        "content_block_start",
        {
            "type": "content_block_start",
            "index": index,
            "content_block": {"type": "thinking", "thinking": "", "signature": ""},
        },
    )


def anthropic_thinking_delta_event(
    event: Callable[[str, JSONDict], bytes], index: int, thinking: str
) -> bytes:
    return event(
        "content_block_delta",
        {
            "type": "content_block_delta",
            "index": index,
            "delta": {"type": "thinking_delta", "thinking": thinking},
        },
    )


def anthropic_thinking_signature_event(
    event: Callable[[str, JSONDict], bytes], index: int
) -> bytes:
    return event(
        "content_block_delta",
        {
            "type": "content_block_delta",
            "index": index,
            "delta": {
                "type": "signature_delta",
                "signature": SOAI_ANTHROPIC_THINKING_SIGNATURE,
            },
        },
    )


def anthropic_tool_start_event(
    event: Callable[[str, JSONDict], bytes], index: int, call_id: str, name: str
) -> bytes:
    return event(
        "content_block_start",
        {
            "type": "content_block_start",
            "index": index,
            "content_block": {"type": "tool_use", "id": call_id, "name": name, "input": {}},
        },
    )


def anthropic_tool_delta_event(
    event: Callable[[str, JSONDict], bytes], index: int, fragment: str
) -> bytes:
    return event(
        "content_block_delta",
        {
            "type": "content_block_delta",
            "index": index,
            "delta": {"type": "input_json_delta", "partial_json": fragment},
        },
    )


def anthropic_block_stop_event(event: Callable[[str, JSONDict], bytes], index: int) -> bytes:
    return event("content_block_stop", {"type": "content_block_stop", "index": index})


def anthropic_content_events(
    event: Callable[[str, JSONDict], bytes],
    blocks: list[JSONDict],
    *,
    start_index: int = 0,
) -> list[bytes]:
    events: list[bytes] = []
    for index, block in enumerate(blocks, start=start_index):
        block_type = block.get("type")
        if block_type == "text":
            text = block.get("text")
            if not isinstance(text, str):
                continue
            events.append(anthropic_text_start_event(event, index))
            if text:
                events.append(anthropic_text_delta_event(event, index, text))
        elif block_type == "thinking":
            thinking = block.get("thinking")
            if not isinstance(thinking, str):
                continue
            events.append(anthropic_thinking_start_event(event, index))
            if thinking:
                events.append(anthropic_thinking_delta_event(event, index, thinking))
            events.append(anthropic_thinking_signature_event(event, index))
        elif block_type == "tool_use":
            call_id = block.get("id")
            name = block.get("name")
            if not isinstance(call_id, str) or not isinstance(name, str):
                continue
            events.append(anthropic_tool_start_event(event, index, call_id, name))
            events.append(
                anthropic_tool_delta_event(
                    event,
                    index,
                    serialize_json_compact_stable_strict(block.get("input")),
                )
            )
        else:
            continue
        events.append(anthropic_block_stop_event(event, index))
    return events


def anthropic_remaining_blocks(
    blocks: list[JSONDict],
    *,
    emitted_text_length: int,
    emitted_thinking_length: int,
    emitted_tool_ids: set[str],
) -> list[JSONDict]:
    remaining: list[JSONDict] = []
    unconsumed_text = emitted_text_length
    unconsumed_thinking = emitted_thinking_length
    for block in blocks:
        if block.get("type") == "tool_use" and block.get("id") in emitted_tool_ids:
            continue
        block_type = block.get("type")
        if block_type == "thinking" and unconsumed_thinking > 0:
            thinking = block.get("thinking")
            if not isinstance(thinking, str):
                remaining.append(block)
                continue
            consumed = min(len(thinking), unconsumed_thinking)
            unconsumed_thinking -= consumed
            if consumed < len(thinking):
                remaining.append(
                    {
                        "type": "thinking",
                        "thinking": thinking[consumed:],
                        "signature": block.get("signature"),
                    }
                )
            continue
        if block_type != "text" or unconsumed_text <= 0:
            remaining.append(block)
            continue
        text = block.get("text")
        if not isinstance(text, str):
            remaining.append(block)
            continue
        consumed = min(len(text), unconsumed_text)
        unconsumed_text -= consumed
        if consumed < len(text):
            remaining.append({"type": "text", "text": text[consumed:]})
    return remaining
