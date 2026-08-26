"""SoAI - OpenAI SSE meaningful-progress detection [backend/core/openai/sse_progress.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.openai.sse_block_decoder import decode_openai_sse_block
from core.openai.sse_frame_accumulator import OpenAISSEFrameAccumulator

__all__ = ("OpenAISSEProgressDetector",)


class OpenAISSEProgressDetector:
    def __init__(self) -> None:
        self._frame_accumulator = OpenAISSEFrameAccumulator()

    def consume(self, chunk: bytes) -> bool:
        frames = self._frame_accumulator.feed(chunk)
        return any(decode_openai_sse_block(frame).data_events for frame in frames)
