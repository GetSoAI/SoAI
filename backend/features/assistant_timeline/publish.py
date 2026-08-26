"""SoAI - Shared assistant timeline event publishing [backend/features/assistant_timeline/publish.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.events.types_system import ChatStreamEvent
from core.timing.monotonic import monotonic_ms
from features.assistant_timeline.models import AssistantTimelineRuntime
from features.assistant_timeline.publish_persistence import (
    ensure_chat_stream_publish_lock,
    ensure_chat_stream_publish_operation_lock,
    flush_chat_stream_event_persistence,
    publish_chat_stream_event_locked_internal,
)
from features.assistant_timeline.usage_preview_tracking import (
    take_usage_preview_snapshot_for_emit,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from core.conversations.protocols_database_message_streaming import (
        DatabaseStreamingMessagesProtocol,
    )
    from core.events.protocols import EventBusProtocol
    from core.types.json import JSONDict

__all__ = (
    "build_chat_stream_event_locked",
    "ensure_chat_stream_publish_lock",
    "ensure_chat_stream_publish_operation_lock",
    "flush_chat_stream_event_persistence",
    "publish_chat_stream_event",
    "publish_chat_stream_event_locked",
    "publish_chat_stream_event_when",
    "run_chat_stream_event_operation_locked",
    "run_attach_guarded_publish_loop",
)


def build_chat_stream_event_locked(
    *,
    runtime: AssistantTimelineRuntime,
    event_type: str,
    payload: JSONDict,
) -> tuple[int, int, JSONDict, ChatStreamEvent]:
    next_payload = dict(payload)
    if "assistant_at_ms" not in next_payload:
        next_payload["assistant_at_ms"] = runtime.assistant_at_ms
    if "assistant_turn_at_ms" not in next_payload:
        next_payload["assistant_turn_at_ms"] = runtime.assistant_turn_at_ms
    if "model_variant_index" not in next_payload:
        next_payload["model_variant_index"] = runtime.model_variant_index
    candidate_sequence = runtime.next_sequence
    if runtime.assistant_revision != candidate_sequence:
        raise StateError("Chat stream runtime assistant_revision out of sync with next_sequence.")
    candidate_revision = runtime.assistant_revision + 1
    next_payload["assistant_revision"] = candidate_revision
    if (
        event_type not in {"completed", "cancelled", "error"}
        and "usage_preview" not in next_payload
    ):
        usage_preview_snapshot = take_usage_preview_snapshot_for_emit(
            runtime=runtime,
            now_ms=monotonic_ms(),
            force=False,
        )
        if usage_preview_snapshot is not None:
            next_payload["usage_preview"] = usage_preview_snapshot
    chat_stream_event = ChatStreamEvent(
        user_id=runtime.user_id,
        conv_id=runtime.conv_id,
        request_id=runtime.request_id,
        sequence=candidate_sequence,
        event_type=event_type,
        payload=next_payload,
    )
    return candidate_sequence, candidate_revision, next_payload, chat_stream_event


async def run_chat_stream_event_operation_locked(
    *,
    runtime: AssistantTimelineRuntime,
    event_type: str,
    payload: JSONDict,
    locked_operation: Callable[[int, int, JSONDict, ChatStreamEvent], Awaitable[None]],
) -> ChatStreamEvent:
    operation_lock = ensure_chat_stream_publish_operation_lock(runtime)
    async with operation_lock:
        sequence, assistant_revision, stamped_payload, chat_stream_event = (
            build_chat_stream_event_locked(
                runtime=runtime,
                event_type=event_type,
                payload=payload,
            )
        )
        await locked_operation(
            sequence,
            assistant_revision,
            stamped_payload,
            chat_stream_event,
        )
        return chat_stream_event


async def publish_chat_stream_event(
    event_bus: EventBusProtocol,
    runtime: AssistantTimelineRuntime,
    database_messages: DatabaseStreamingMessagesProtocol,
    *,
    event_type: str,
    payload: JSONDict,
    wait: bool = False,
) -> None:
    async def locked_operation(
        sequence: int,
        assistant_revision: int,
        stamped_payload: JSONDict,
        chat_stream_event: ChatStreamEvent,
    ) -> None:
        await publish_chat_stream_event_locked_internal(
            event_bus,
            runtime,
            database_messages,
            event_type=event_type,
            sequence=sequence,
            assistant_revision=assistant_revision,
            payload=stamped_payload,
            chat_stream_event=chat_stream_event,
            wait=wait,
        )

    await run_chat_stream_event_operation_locked(
        runtime=runtime,
        event_type=event_type,
        payload=payload,
        locked_operation=locked_operation,
    )


async def publish_chat_stream_event_locked(
    event_bus: EventBusProtocol,
    runtime: AssistantTimelineRuntime,
    database_messages: DatabaseStreamingMessagesProtocol,
    *,
    event_type: str,
    payload: JSONDict,
    wait: bool = False,
) -> None:
    publish_lock = ensure_chat_stream_publish_lock(runtime)
    if not publish_lock.locked():
        raise StateError(
            "publish_chat_stream_event_locked requires publish_lock to be held by the caller.",
        )

    async def locked_operation(
        sequence: int,
        assistant_revision: int,
        stamped_payload: JSONDict,
        chat_stream_event: ChatStreamEvent,
    ) -> None:
        await publish_chat_stream_event_locked_internal(
            event_bus,
            runtime,
            database_messages,
            event_type=event_type,
            sequence=sequence,
            assistant_revision=assistant_revision,
            payload=stamped_payload,
            chat_stream_event=chat_stream_event,
            wait=wait,
        )

    await run_chat_stream_event_operation_locked(
        runtime=runtime,
        event_type=event_type,
        payload=payload,
        locked_operation=locked_operation,
    )


async def publish_chat_stream_event_when(
    condition: bool,
    event_bus: EventBusProtocol,
    runtime: AssistantTimelineRuntime,
    database_messages: DatabaseStreamingMessagesProtocol,
    *,
    event_type: str,
    payload: JSONDict,
    wait: bool = False,
) -> bool:
    if not condition:
        return False
    await publish_chat_stream_event(
        event_bus,
        runtime,
        database_messages,
        event_type=event_type,
        payload=payload,
        wait=wait,
    )
    return True


async def run_attach_guarded_publish_loop(
    *,
    runtime: AssistantTimelineRuntime,
    interval_sec: float,
    locked_step: Callable[[], Awaitable[None]],
) -> None:
    while runtime.detach_event is not None and not runtime.detach_event.is_set():
        await asyncio.sleep(interval_sec)
        if runtime.detach_event is None or runtime.detach_event.is_set():
            return
        lock = ensure_chat_stream_publish_lock(runtime)
        async with lock:
            if runtime.detach_event is None or runtime.detach_event.is_set():
                return
            await locked_step()
