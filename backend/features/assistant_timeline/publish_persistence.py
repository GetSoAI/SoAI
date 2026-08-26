"""SoAI - Shared assistant timeline publish persistence helpers [backend/features/assistant_timeline/publish_persistence.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.events.completion_waiting import (
    EventPublicationReceipt,
    await_publication_receipt,
)
from core.timing.epoch import epoch_ms
from core.timing.monotonic import monotonic_ms
from features.assistant_timeline.message_write_versions import (
    record_assistant_timeline_message_write,
)
from features.assistant_timeline.models import (
    AssistantTimelineRuntime,
    PendingAssistantMessageEvent,
)
from features.assistant_timeline.tool_payload_state import (
    record_latest_tool_payload_locked,
)

if TYPE_CHECKING:
    from core.conversations.protocols_database_message_streaming import (
        DatabaseStreamingMessagesProtocol,
    )
    from core.events.protocols import EventBusProtocol
    from core.events.types_system import ChatStreamEvent
    from core.types.json import JSONDict

__all__ = (
    "ensure_chat_stream_publish_lock",
    "ensure_chat_stream_publish_operation_lock",
    "flush_assistant_event_buffer_locked",
    "flush_chat_stream_event_persistence",
    "publish_chat_stream_event_locked_internal",
    "should_flush_assistant_event_buffer",
)

ASSISTANT_EVENT_PERSIST_FLUSH_INTERVAL_MS: int = 750
ASSISTANT_EVENT_PERSIST_MAX_EVENTS_PER_FLUSH: int = 256


def ensure_chat_stream_publish_lock(runtime: AssistantTimelineRuntime) -> asyncio.Lock:
    if runtime.publish_lock is None:
        runtime.publish_lock = asyncio.Lock()
    return runtime.publish_lock


def ensure_chat_stream_publish_operation_lock(runtime: AssistantTimelineRuntime) -> asyncio.Lock:
    if runtime.publish_operation_lock is None:
        runtime.publish_operation_lock = asyncio.Lock()
    return runtime.publish_operation_lock


def should_flush_assistant_event_buffer(
    runtime: AssistantTimelineRuntime,
    *,
    now_ms: int,
    force: bool,
) -> bool:
    if not runtime.assistant_event_buffer:
        return False
    if not runtime.assistant_placeholder_persisted:
        return False
    if force:
        return True
    if len(runtime.assistant_event_buffer) >= ASSISTANT_EVENT_PERSIST_MAX_EVENTS_PER_FLUSH:
        return True
    elapsed_ms = now_ms - runtime.assistant_event_last_flush_monotonic_ms
    return elapsed_ms >= ASSISTANT_EVENT_PERSIST_FLUSH_INTERVAL_MS


async def flush_assistant_event_buffer_locked(
    runtime: AssistantTimelineRuntime,
    database_messages: DatabaseStreamingMessagesProtocol,
    *,
    now_ms: int,
    force: bool,
) -> bool:
    if not should_flush_assistant_event_buffer(runtime, now_ms=now_ms, force=force):
        return False
    batch = runtime.assistant_event_buffer[:ASSISTANT_EVENT_PERSIST_MAX_EVENTS_PER_FLUSH]
    events = [
        (
            entry.sequence,
            entry.assistant_revision,
            entry.event_type,
            entry.payload,
            entry.created_at,
        )
        for entry in batch
    ]
    await runtime.require_mutation_allowed()
    write_result = await database_messages.append_streaming_assistant_events_batch(
        runtime.conv_id,
        runtime.user_id,
        assistant_at_ms=runtime.assistant_at_ms,
        events=events,
    )
    record_assistant_timeline_message_write(runtime, write_result)
    del runtime.assistant_event_buffer[: len(batch)]
    runtime.assistant_event_last_flush_monotonic_ms = now_ms
    return True


async def flush_chat_stream_event_persistence(
    runtime: AssistantTimelineRuntime,
    database_messages: DatabaseStreamingMessagesProtocol,
    *,
    force: bool = False,
) -> bool:
    operation_lock = ensure_chat_stream_publish_operation_lock(runtime)
    async with operation_lock:
        did_flush = False
        now_ms = monotonic_ms()
        if not should_flush_assistant_event_buffer(runtime, now_ms=now_ms, force=force):
            return False
        while runtime.assistant_event_buffer:
            did_flush = True
            now_ms = monotonic_ms()
            await flush_assistant_event_buffer_locked(
                runtime,
                database_messages,
                now_ms=now_ms,
                force=True,
            )
        return did_flush


async def publish_chat_stream_event_locked_internal(
    event_bus: EventBusProtocol,
    runtime: AssistantTimelineRuntime,
    database_messages: DatabaseStreamingMessagesProtocol,
    *,
    event_type: str,
    sequence: int,
    assistant_revision: int,
    payload: JSONDict,
    chat_stream_event: ChatStreamEvent,
    wait: bool,
) -> None:
    tool_payload = payload.get("tool")
    if event_type.startswith("tool_call_") and isinstance(tool_payload, dict):
        record_latest_tool_payload_locked(runtime, tool_payload)
    runtime.assistant_event_buffer.append(
        PendingAssistantMessageEvent(
            sequence=sequence,
            assistant_revision=assistant_revision,
            event_type=event_type,
            payload=dict(payload),
            created_at=epoch_ms(),
        ),
    )
    runtime.next_sequence = sequence + 1
    runtime.assistant_revision = assistant_revision
    if wait:
        receipt = EventPublicationReceipt.create(
            event_type=type(chat_stream_event).__name__,
            operation="webui.chat_stream.publish",
        )
        await event_bus.publish(chat_stream_event, wait_for_completion=receipt.completion_signal)
        await await_publication_receipt(receipt)
    else:
        await event_bus.publish(chat_stream_event)
    await flush_assistant_event_buffer_locked(
        runtime,
        database_messages,
        now_ms=monotonic_ms(),
        force=False,
    )
