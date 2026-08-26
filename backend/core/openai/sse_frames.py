"""SoAI - Shared OpenAI SSE frame constants [backend/core/openai/sse_frames.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

__all__ = (
    "OPENAI_SSE_DONE_MARKER_TEXT",
    "SSE_DONE_FRAME_TEXT",
    "SSE_KEEPALIVE_FRAME_TEXT",
    "is_openai_sse_done_payload_text",
    "sse_done_chunk",
    "sse_done_frame_trimmed",
    "sse_keepalive_chunk",
    "sse_keepalive_frame_trimmed",
)

SSE_KEEPALIVE_FRAME_TEXT: str = ":\n\n"
SSE_DONE_FRAME_TEXT: str = "data: [DONE]\n\n"
OPENAI_SSE_DONE_MARKER_TEXT: str = "[DONE]"


def is_openai_sse_done_payload_text(payload_text: str) -> bool:
    return payload_text.rstrip() == OPENAI_SSE_DONE_MARKER_TEXT


def sse_keepalive_chunk() -> bytes:
    return SSE_KEEPALIVE_FRAME_TEXT.encode("utf-8")


def sse_done_chunk() -> bytes:
    return SSE_DONE_FRAME_TEXT.encode("utf-8")


def sse_keepalive_frame_trimmed() -> str:
    return SSE_KEEPALIVE_FRAME_TEXT.strip()


def sse_done_frame_trimmed() -> str:
    return SSE_DONE_FRAME_TEXT.strip()
