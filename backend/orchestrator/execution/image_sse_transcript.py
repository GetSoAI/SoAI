"""SoAI - Streaming image SSE transcript for final payload persistence [backend/orchestrator/execution/image_sse_transcript.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.openai.sse_frame_accumulator import OpenAISSEFrameAccumulator
from core.openai.sse_frame_payloads import parse_openai_sse_frame_payloads

if TYPE_CHECKING:
    from core.streaming.stream_chunk import StreamChunk
    from core.types.json import JSONDict

__all__ = ("ImageSSETranscript",)


class ImageSSETranscript:
    def __init__(self) -> None:
        self._frame_accumulator = OpenAISSEFrameAccumulator()
        self._last_payload_with_data: JSONDict | None = None

    def feed(self, chunk: StreamChunk) -> None:
        for frame in self._frame_accumulator.feed(chunk):
            self._consume_frame(frame)

    def finalize(self) -> None:
        self._frame_accumulator.finalize()

    def build_result_payload(self) -> JSONDict | None:
        if self._last_payload_with_data is None:
            return None
        return dict(self._last_payload_with_data)

    def _consume_frame(self, frame: str) -> None:
        for payload in parse_openai_sse_frame_payloads(frame):
            data_value = payload.get("data")
            if isinstance(data_value, list):
                self._last_payload_with_data = payload
