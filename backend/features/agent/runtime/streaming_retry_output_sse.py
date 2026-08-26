"""SoAI - Agent streaming retry output SSE rendering [backend/features/agent/runtime/streaming_retry_output_sse.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.openai.sse_events import format_openai_sse_bytes
from core.runtime.soai_identifiers import create_prefixed_hex_id
from core.timing.epoch import epoch_seconds

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "build_retry_stop_sse_bytes",
    "build_retry_text_delta_sse_bytes",
    "resolve_retry_stream_id",
)


def resolve_retry_stream_id(stream_id: str | None) -> str:
    if stream_id and stream_id.strip():
        return stream_id
    return create_prefixed_hex_id(
        "chatcmpl",
        length=12,
        separator="-",
    )


def build_retry_text_delta_sse_bytes(
    *,
    stream_id: str,
    model: str | None,
    text_delta: str,
) -> bytes:
    normalized_text = text_delta
    payload: JSONDict = {
        "id": stream_id,
        "object": "chat.completion.chunk",
        "created": int(epoch_seconds()),
        "model": model or "unknown",
        "choices": [
            {
                "index": 0,
                "delta": {"content": normalized_text},
                "finish_reason": None,
            },
        ],
    }
    return format_openai_sse_bytes(payload)


def build_retry_stop_sse_bytes(
    *,
    stream_id: str,
    model: str | None,
) -> bytes:
    payload: JSONDict = {
        "id": stream_id,
        "object": "chat.completion.chunk",
        "created": int(epoch_seconds()),
        "model": model or "unknown",
        "choices": [
            {
                "index": 0,
                "delta": {},
                "finish_reason": "stop",
            },
        ],
    }
    return format_openai_sse_bytes(payload)
