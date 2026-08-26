"""SoAI - OpenAI SSE validation helpers [backend/core/openai/sse_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.config.byte_sizes import MIB_BYTES
from core.openai.payload_validation import decode_streaming_text_chunk
from core.openai.sse_block_decoder import (
    decode_openai_sse_block,
    is_valid_openai_decoded_block,
)

if TYPE_CHECKING:
    from core.streaming.stream_chunk import StreamChunk

__all__ = (
    "OPENAI_SSE_PENDING_BUFFER_LIMIT_BYTES",
    "validate_openai_sse_frame",
)

OPENAI_SSE_PENDING_BUFFER_LIMIT_BYTES = MIB_BYTES


def validate_openai_sse_frame(
    frame: StreamChunk,
    *,
    allow_responses_events: bool = False,
    allow_image_events: bool = False,
    allow_transcription_events: bool = False,
) -> bool:
    frame_text = decode_streaming_text_chunk(frame)
    if frame_text is None:
        return False
    decoded = decode_openai_sse_block(frame_text)
    return is_valid_openai_decoded_block(
        decoded,
        allow_responses_events=allow_responses_events,
        allow_image_events=allow_image_events,
        allow_transcription_events=allow_transcription_events,
    )
