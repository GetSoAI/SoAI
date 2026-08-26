"""SoAI - Agent OpenAI usage aggregation helpers [backend/features/agent/runtime/openai_usage.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.openai.sse_events import format_openai_sse_bytes
from core.openai.usage.serialization import extract_public_usage_payload
from core.runtime.soai_identifiers import create_prefixed_hex_id
from core.timing.epoch import epoch_seconds

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("build_usage_sse_bytes",)


def build_usage_sse_bytes(*, stream_id: str | None, model: str | None, usage: JSONDict) -> bytes:
    public_usage = extract_public_usage_payload(usage)
    if public_usage is None:
        raise ValueError("Agent usage SSE requires canonical public usage.")
    completion_id = stream_id or create_prefixed_hex_id(
        "chatcmpl",
        length=12,
        separator="-",
    )
    usage_chunk: JSONDict = {
        "id": completion_id,
        "object": "chat.completion.chunk",
        "created": int(epoch_seconds()),
        "model": model or "unknown",
        "choices": [],
        "usage": public_usage,
    }
    return format_openai_sse_bytes(usage_chunk)
