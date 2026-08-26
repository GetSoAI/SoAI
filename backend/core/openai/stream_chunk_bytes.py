"""SoAI - OpenAI stream chunk byte coercion [backend/core/openai/stream_chunk_bytes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError

if TYPE_CHECKING:
    from core.streaming.stream_chunk import StreamChunk

__all__ = ("coerce_stream_chunk_to_bytes",)


def coerce_stream_chunk_to_bytes(chunk: StreamChunk) -> bytes:
    if isinstance(chunk, bytes):
        return chunk
    if isinstance(chunk, bytearray):
        return bytes(chunk)
    if isinstance(chunk, memoryview):
        return chunk.tobytes()
    if isinstance(chunk, str):
        return chunk.encode("utf-8", errors="strict")
    raise ValidationError(f"Invalid stream chunk type: {type(chunk).__name__}")
