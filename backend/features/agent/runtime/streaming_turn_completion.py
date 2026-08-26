"""SoAI - Agent streaming turn completion emission [backend/features/agent/runtime/streaming_turn_completion.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from core.openai.sse_frames import sse_done_chunk
from core.openai.usage.serialization import build_internal_usage_payload
from features.agent.runtime.openai_payload import resolve_payload_model
from features.agent.runtime.openai_usage import build_usage_sse_bytes

if TYPE_CHECKING:
    from core.openai.usage.models import CanonicalUsage
    from core.types.json import JSONDict

__all__ = ("emit_streaming_turn_completion",)


async def emit_streaming_turn_completion(
    *,
    include_usage: bool,
    usage_aggregate: CanonicalUsage | None,
    stream_id: str | None,
    base_request_payload: JSONDict,
    on_bytes: Callable[[bytes], Awaitable[None] | None],
) -> None:
    if include_usage and usage_aggregate is not None:
        usage_bytes = build_usage_sse_bytes(
            stream_id=stream_id,
            model=resolve_payload_model(base_request_payload),
            usage=build_internal_usage_payload(usage_aggregate),
        )
        usage_awaitable = on_bytes(usage_bytes)
        if usage_awaitable is not None:
            await usage_awaitable
    done_awaitable = on_bytes(sse_done_chunk())
    if done_awaitable is not None:
        await done_awaitable
