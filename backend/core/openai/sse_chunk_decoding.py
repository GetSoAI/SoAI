"""SoAI - SSE chunk decoding helpers for OpenAI-compatible streams [backend/core/openai/sse_chunk_decoding.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.openai.sse_frames import sse_keepalive_frame_trimmed

__all__ = ("decode_sse_chunk_bytes",)


def decode_sse_chunk_bytes(chunk: bytes | bytearray | memoryview) -> str | None:
    if not isinstance(chunk, bytes | bytearray | memoryview):
        return None
    try:
        decoded = bytes(chunk).decode("utf-8")
    except UnicodeDecodeError:
        return None
    trimmed = decoded.strip()
    if not trimmed or trimmed == sse_keepalive_frame_trimmed():
        return None
    return decoded
