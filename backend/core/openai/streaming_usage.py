"""SoAI - OpenAI streaming usage extraction [backend/core/openai/streaming_usage.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.openai.sse_events import format_openai_sse_bytes
from core.openai.sse_frame_payloads import parse_openai_sse_frame_payloads
from core.openai.sse_rewrite import rewrite_openai_sse_json_payload_frame
from core.openai.usage.serialization import extract_public_usage_payload
from core.runtime.soai_identifiers import create_prefixed_hex_id
from core.timing.epoch import epoch_seconds

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "OpenAIChunkUsageWithholding",
    "StreamingUsageCollection",
    "StreamingUsageCollector",
    "build_openai_usage_chunk_bytes",
    "parse_sse_frame_for_usage",
    "withhold_openai_chunk_usage",
)


@dataclass(frozen=True, slots=True)
class StreamingUsageCollection:
    usage_value: JSONDict | None


@dataclass(frozen=True, slots=True)
class OpenAIChunkUsageWithholding:
    public_frame_text: str | None
    provider_usage: JSONDict | None


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


def _carries_completion_chunk_usage(payload: JSONDict) -> bool:
    return isinstance(payload.get("choices"), list) and payload.get("usage") is not None


def _remove_completion_chunk_usage(payload: JSONDict) -> bool:
    if not _carries_completion_chunk_usage(payload):
        return False
    del payload["usage"]
    return True


def withhold_openai_chunk_usage(frame_text: str) -> OpenAIChunkUsageWithholding:
    if '"usage"' not in frame_text:
        return OpenAIChunkUsageWithholding(public_frame_text=frame_text, provider_usage=None)
    for payload in parse_openai_sse_frame_payloads(frame_text):
        if not _carries_completion_chunk_usage(payload):
            continue
        provider_usage = extract_public_usage_payload(payload.get("usage"))
        if not payload.get("choices"):
            return OpenAIChunkUsageWithholding(
                public_frame_text=None,
                provider_usage=provider_usage,
            )
        public_frame = rewrite_openai_sse_json_payload_frame(
            frame_text.encode("utf-8"),
            rewrite_payload=_remove_completion_chunk_usage,
        )
        return OpenAIChunkUsageWithholding(
            public_frame_text=public_frame.decode("utf-8"),
            provider_usage=provider_usage,
        )
    return OpenAIChunkUsageWithholding(public_frame_text=frame_text, provider_usage=None)


def build_openai_usage_chunk_bytes(
    *,
    public_usage: JSONDict,
    stream_id: str | None,
    object_type: str,
    model: str | None,
) -> bytes:
    completion_id = stream_id or create_prefixed_hex_id(
        "chatcmpl",
        length=12,
        separator="-",
    )
    usage_chunk: JSONDict = {
        "id": completion_id,
        "object": object_type,
        "created": int(epoch_seconds()),
        "model": model or "unknown",
        "choices": [],
        "usage": public_usage,
    }
    return format_openai_sse_bytes(usage_chunk)


class StreamingUsageCollector:
    def __init__(self) -> None:
        self._usage_value: JSONDict | None = None

    def consume_frame(self, frame: bytes | str) -> None:
        parsed_usage = parse_sse_frame_for_usage(frame)
        if parsed_usage is not None:
            self._usage_value = parsed_usage

    def finalize(self) -> StreamingUsageCollection:
        return StreamingUsageCollection(usage_value=self._usage_value)
