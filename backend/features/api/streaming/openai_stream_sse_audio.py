"""SoAI - OpenAI SSE audio stream encoding [backend/features/api/streaming/openai_stream_sse_audio.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import AsyncGenerator

from core.openai.audio_sse_events import (
    format_openai_audio_delta_sse,
    format_openai_audio_done_sse,
    format_openai_audio_error_sse,
)
from core.serialization.base64_values import encode_base64_ascii
from features.api.streaming.openai_stream_binary_request_stream import (
    BinaryStreamRuntimeFailure,
)

__all__ = ("stream_sse_audio_chunks",)


async def stream_sse_audio_chunks(
    stream_binary: AsyncGenerator[bytes],
    trace_id: str,
) -> AsyncGenerator[str]:
    try:
        async for chunk in stream_binary:
            encoded = encode_base64_ascii(chunk)
            yield format_openai_audio_delta_sse(encoded)
    except BinaryStreamRuntimeFailure as exception:
        yield format_openai_audio_error_sse(exception.message, exception.error_type, trace_id)
        return
    yield format_openai_audio_done_sse()
