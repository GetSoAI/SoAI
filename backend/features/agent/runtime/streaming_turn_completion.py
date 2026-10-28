"""SoAI - Agent streaming turn completion emission [backend/features/agent/runtime/streaming_turn_completion.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from core.agent.status_values import (
    AGENT_TURN_STATUS_COMPLETED,
    AGENT_TURN_STATUS_MAX_ITERATIONS,
)
from core.openai.sse_frames import sse_done_chunk
from core.openai.streaming_usage import build_openai_usage_chunk_bytes
from core.openai.usage.serialization import (
    build_internal_usage_payload,
    extract_public_usage_payload,
)
from features.agent.runtime.openai_payload import resolve_payload_model

if TYPE_CHECKING:
    from core.openai.streaming_usage import OpenAIPublicUsageProjection
    from core.openai.usage.models import CanonicalUsage
    from core.streaming.protocols import StreamGeneratorStateProtocol
    from core.types.json import JSONDict

__all__ = ("bind_public_usage_projection", "emit_streaming_turn_completion")

CANONICAL_USAGE_REQUIRED_MESSAGE = "Agent usage SSE requires canonical public usage."


def bind_public_usage_projection(
    on_bytes: Callable[[bytes], Awaitable[None] | None],
    public_usage_projection: OpenAIPublicUsageProjection | None,
) -> Callable[[bytes], Awaitable[None] | None]:
    if public_usage_projection is None:
        return on_bytes

    def deliver_projected_bytes(chunk: bytes) -> Awaitable[None] | None:
        return on_bytes(public_usage_projection.project_frame(chunk))

    return deliver_projected_bytes


def _build_requested_usage_bytes(
    *,
    include_usage: bool,
    internal_usage: JSONDict | None,
    stream_id: str | None,
    model: str | None,
) -> bytes | None:
    if not include_usage or internal_usage is None:
        return None
    public_usage = extract_public_usage_payload(internal_usage)
    if public_usage is None:
        raise ValueError(CANONICAL_USAGE_REQUIRED_MESSAGE)
    return build_openai_usage_chunk_bytes(
        public_usage=public_usage,
        stream_id=stream_id,
        object_type="chat.completion.chunk",
        model=model,
    )


def _commit_public_usage_bytes(
    public_usage_projection: OpenAIPublicUsageProjection,
    *,
    turn_status: str,
    internal_usage: JSONDict | None,
    stream_id: str | None,
    model: str | None,
) -> bytes | None:
    if not public_usage_projection.include_usage or turn_status not in (
        AGENT_TURN_STATUS_COMPLETED,
        AGENT_TURN_STATUS_MAX_ITERATIONS,
    ):
        return None
    usage_bytes = public_usage_projection.commit_terminal_usage_frame(
        internal_usage,
        stream_id_hint=stream_id,
        model_hint=model,
    )
    if usage_bytes is None:
        raise ValueError(CANONICAL_USAGE_REQUIRED_MESSAGE)
    return usage_bytes


async def _deliver(on_bytes: Callable[[bytes], Awaitable[None] | None], chunk: bytes) -> None:
    awaitable = on_bytes(chunk)
    if awaitable is not None:
        await awaitable


async def emit_streaming_turn_completion(
    *,
    include_usage: bool,
    usage_aggregate: CanonicalUsage | None,
    stream_id: str | None,
    base_request_payload: JSONDict,
    turn_status: str,
    on_bytes: Callable[[bytes], Awaitable[None] | None],
    public_usage_projection: OpenAIPublicUsageProjection | None = None,
    stream_result_state: StreamGeneratorStateProtocol | None = None,
) -> None:
    internal_usage = (
        build_internal_usage_payload(usage_aggregate) if usage_aggregate is not None else None
    )
    if stream_result_state is not None:
        stream_result_state.usage = internal_usage
    model = resolve_payload_model(base_request_payload)
    usage_bytes = (
        _build_requested_usage_bytes(
            include_usage=include_usage,
            internal_usage=internal_usage,
            stream_id=stream_id,
            model=model,
        )
        if public_usage_projection is None
        else _commit_public_usage_bytes(
            public_usage_projection,
            turn_status=turn_status,
            internal_usage=internal_usage,
            stream_id=stream_id,
            model=model,
        )
    )
    if usage_bytes is not None:
        await _deliver(on_bytes, usage_bytes)
    await _deliver(on_bytes, sse_done_chunk())
