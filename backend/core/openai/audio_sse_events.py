"""SoAI - OpenAI audio SSE event formatting [backend/core/openai/audio_sse_events.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.openai.sse_events import (
    format_openai_sse_data,
    format_openai_stream_error_chunk,
)

__all__ = (
    "format_openai_audio_delta_sse",
    "format_openai_audio_done_sse",
    "format_openai_audio_error_sse",
)


def format_openai_audio_delta_sse(encoded_audio: str) -> str:
    return format_openai_sse_data({"type": "speech.audio.delta", "audio": encoded_audio})


def format_openai_audio_done_sse() -> str:
    return format_openai_sse_data(
        {
            "type": "speech.audio.done",
            "usage": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
        },
    )


def format_openai_audio_error_sse(message: str, error_type: str, trace_id: str) -> str:
    return format_openai_stream_error_chunk(None, message, error_type, trace_id).decode("utf-8")
