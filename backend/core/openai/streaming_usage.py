"""SoAI - OpenAI streaming usage extraction [backend/core/openai/streaming_usage.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.openai.sse_frame_payloads import parse_openai_sse_frame_payloads

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "StreamingUsageCollection",
    "StreamingUsageCollector",
    "parse_sse_frame_for_usage",
)


@dataclass(frozen=True, slots=True)
class StreamingUsageCollection:
    usage_value: JSONDict | None


def parse_sse_frame_for_usage(frame: bytes | str) -> JSONDict | None:
    usage_value: JSONDict | None = None
    for payload in parse_openai_sse_frame_payloads(frame):
        response = payload.get("response")
        payload_usage = (
            response.get("usage") if isinstance(response, dict) else payload.get("usage")
        )
        if isinstance(payload_usage, dict):
            usage_value = dict(payload_usage)
    return usage_value


class StreamingUsageCollector:
    def __init__(self) -> None:
        self._usage_value: JSONDict | None = None

    def consume_frame(self, frame: bytes | str) -> None:
        parsed_usage = parse_sse_frame_for_usage(frame)
        if parsed_usage is not None:
            self._usage_value = parsed_usage

    def finalize(self) -> StreamingUsageCollection:
        return StreamingUsageCollection(usage_value=self._usage_value)
