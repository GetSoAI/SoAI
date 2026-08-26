"""SoAI - WebSocket chat stream start conflict resolution [backend/features/api/routes/system/events/chat_stream/start_conflict_resolution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from asyncio import Event, sleep
from collections.abc import MutableMapping
from typing import TYPE_CHECKING

from core.concurrency.deadlines import deadline_after
from features.api.routes.system.events.chat_stream.cancel import (
    schedule_ws_chat_stream_cancel,
)
from features.api.routes.system.events.chat_stream.command_errors import (
    enqueue_chat_stream_start_error,
)
from features.api.runtime.chat_stream_registry import (
    chat_stream_registry_slot_accepts_runtime,
)
from features.assistant_timeline.models import AssistantTimelineRuntime

if TYPE_CHECKING:
    from core.runtime.protocols import RequestProtocol
    from features.api.runtime.context import ApiContext
    from features.api.runtime.internal_protocols import ChatStreamRegistryProtocol
    from features.api.streaming.websocket import WebsocketConnection

__all__ = (
    "cancel_and_release_connection_chat_stream_slot",
    "ensure_connection_chat_stream_start_allowed",
    "try_register_chat_stream_with_retry",
    "wait_for_chat_stream_registry_slot",
)

_CHAT_STREAM_CONFLICT_POLL_SLEEP_S = 0.05


def cancel_and_release_connection_chat_stream_slot(
    *,
    request: RequestProtocol,
    api_context: ApiContext,
    chat_streams: MutableMapping[str, AssistantTimelineRuntime],
    conv_id: str,
    reason: str,
) -> None:
    normalized_conv_id = conv_id.strip() if isinstance(conv_id, str) else ""
    if not normalized_conv_id:
        return
    runtime = chat_streams.get(normalized_conv_id)
    if runtime is None:
        return
    if not runtime.cancellation_requested:
        runtime.cancellation_requested = True
        runtime.cancellation_reason = reason
    detach_event = runtime.detach_event
    if detach_event is None:
        detach_event = Event()
        runtime.detach_event = detach_event
    detach_event.set()
    if chat_streams.get(normalized_conv_id) is runtime:
        del chat_streams[normalized_conv_id]
    _ = schedule_ws_chat_stream_cancel(
        api_context=api_context,
        context=request.state.context,
        runtime=runtime,
        reason=reason,
    )


async def ensure_connection_chat_stream_start_allowed(
    *,
    request: RequestProtocol,
    api_context: ApiContext,
    connection: WebsocketConnection,
    chat_streams: MutableMapping[str, AssistantTimelineRuntime],
    conv_id: str,
    request_id: str,
) -> bool:
    normalized_conv_id = conv_id.strip() if isinstance(conv_id, str) else ""
    if not normalized_conv_id:
        await enqueue_chat_stream_start_error(
            connection,
            conv_id,
            request_id,
            "invalid_request_error",
            "Chat stream start requires a valid conv_id.",
        )
        return False
    existing_connection_runtime = chat_streams.get(normalized_conv_id)
    if (
        existing_connection_runtime is not None
        and existing_connection_runtime.request_id == request_id
    ):
        return False
    if existing_connection_runtime is None:
        return True
    cancel_and_release_connection_chat_stream_slot(
        request=request,
        api_context=api_context,
        chat_streams=chat_streams,
        conv_id=normalized_conv_id,
        reason="Superseded by a new chat stream start request.",
    )
    return True


async def wait_for_chat_stream_registry_slot(
    registry: ChatStreamRegistryProtocol,
    *,
    user_id: int,
    conv_id: str,
    timeout_ms: int,
) -> bool:
    deadline = deadline_after(float(timeout_ms) / 1000.0)
    while not deadline.expired():
        existing = await registry.get(user_id=user_id, conv_id=conv_id)
        if chat_stream_registry_slot_accepts_runtime(existing):
            return True
        await sleep(_CHAT_STREAM_CONFLICT_POLL_SLEEP_S)
    return False


async def try_register_chat_stream_with_retry(
    registry: ChatStreamRegistryProtocol,
    runtime: AssistantTimelineRuntime,
    *,
    timeout_ms: int,
) -> bool:
    registered = await registry.try_register(runtime)
    if registered:
        return True
    slot_available = await wait_for_chat_stream_registry_slot(
        registry,
        user_id=int(runtime.user_id),
        conv_id=runtime.conv_id,
        timeout_ms=timeout_ms,
    )
    if not slot_available:
        return False
    return await registry.try_register(runtime)
