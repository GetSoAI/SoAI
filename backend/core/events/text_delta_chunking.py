"""SoAI - Text delta chunking for realtime events [backend/core/events/text_delta_chunking.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.validation.integers import is_strict_int

__all__ = ("split_text_delta",)

DEFAULT_EVENT_TEXT_DELTA_MAX_CHARS: int = 16_000


def split_text_delta(
    delta: str | None,
    *,
    max_chunk_chars: int = DEFAULT_EVENT_TEXT_DELTA_MAX_CHARS,
) -> tuple[str, ...]:
    if delta is None or not delta:
        return ()
    if not is_strict_int(max_chunk_chars):
        raise ValueError("max_chunk_chars must be an integer.")
    if max_chunk_chars <= 0:
        raise ValueError("max_chunk_chars must be a positive integer.")
    if len(delta) <= max_chunk_chars:
        return (delta,)
    chunks: list[str] = []
    start = 0
    while start < len(delta):
        end = min(len(delta), start + max_chunk_chars)
        chunks.append(delta[start:end])
        start = end
    return tuple(chunks)
