"""SoAI - Assistant timeline text delta persistence and publication [backend/features/assistant_timeline/assistant_text.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.timing.monotonic import monotonic_ms
from features.assistant_timeline.activity_status_sets import (
    TIMELINE_ACTIVITY_STATUS_COMPLETED,
)
from features.assistant_timeline.assistant_text_buffers import (
    append_assistant_visible_delta,
    append_pending_delta,
    drain_pending_delta,
    should_flush_assistant_content,
    should_flush_delta_event,
)
from features.assistant_timeline.message_write_versions import (
    record_assistant_timeline_message_write,
)
from features.assistant_timeline.models import AssistantTimelineRuntime
from features.assistant_timeline.processing_activity import (
    complete_processing_activity_if_running_locked,
    note_visible_activity_locked,
)
from features.assistant_timeline.publish import (
    ensure_chat_stream_publish_lock,
    flush_chat_stream_event_persistence,
    publish_chat_stream_event_locked,
)
from features.assistant_timeline.status_preview_state import (
    clear_status_preview_state,
)

if TYPE_CHECKING:
    from core.conversations.protocols_database_message_streaming import (
        DatabaseStreamingMessagesProtocol,
    )
    from core.events.protocols import EventBusProtocol

__all__ = (
    "flush_assistant_visible_chronology",
    "flush_assistant_visible_chronology_locked",
    "flush_pending_assistant_text_and_finalize_processing_locked",
    "flush_pending_assistant_text_delta",
    "flush_pending_assistant_text_delta_locked",
    "flush_streaming_assistant_content_if_due",
    "flush_streaming_assistant_content_if_due_locked",
    "persist_and_publish_assistant_text_delta",
    "persist_and_publish_assistant_text_delta_locked",
)


async def flush_streaming_assistant_content_if_due(
    *,
    runtime: AssistantTimelineRuntime,
    database_messages: DatabaseStreamingMessagesProtocol,
    force: bool = False,
) -> bool:
    lock = ensure_chat_stream_publish_lock(runtime)
    async with lock:
        return await flush_streaming_assistant_content_if_due_locked(
            runtime=runtime,
            database_messages=database_messages,
            force=force,
        )


async def flush_streaming_assistant_content_if_due_locked(
    *,
    runtime: AssistantTimelineRuntime,
    database_messages: DatabaseStreamingMessagesProtocol,
    force: bool = False,
) -> bool:
    now_ms = monotonic_ms()
    if not should_flush_assistant_content(runtime, now_ms=now_ms, force=force):
        return False
    await runtime.require_mutation_allowed()
    write_result = await database_messages.update_streaming_assistant_content(
        runtime.conv_id,
        runtime.user_id,
        created_at_ms=runtime.assistant_at_ms,
        content_text=runtime.assistant_visible_text,
    )
    record_assistant_timeline_message_write(runtime, write_result)
    runtime.assistant_persisted_chars = runtime.assistant_visible_chars
    runtime.assistant_last_persist_monotonic_ms = now_ms
    return True


async def persist_and_publish_assistant_text_delta(
    *,
    runtime: AssistantTimelineRuntime,
    delta_text: str,
    database_messages: DatabaseStreamingMessagesProtocol,
    event_bus: EventBusProtocol,
    force_publish: bool = False,
    allow_terminal_finalization: bool = False,
) -> None:
    lock = ensure_chat_stream_publish_lock(runtime)
    async with lock:
        await persist_and_publish_assistant_text_delta_locked(
            runtime=runtime,
            delta_text=delta_text,
            database_messages=database_messages,
            event_bus=event_bus,
            force_publish=force_publish,
            allow_terminal_finalization=allow_terminal_finalization,
        )


async def persist_and_publish_assistant_text_delta_locked(
    *,
    runtime: AssistantTimelineRuntime,
    delta_text: str,
    database_messages: DatabaseStreamingMessagesProtocol,
    event_bus: EventBusProtocol,
    force_publish: bool = False,
    allow_terminal_finalization: bool = False,
) -> None:
    if not delta_text:
        return
    if runtime.terminal_finalization_started and not allow_terminal_finalization:
        return
    append_assistant_visible_delta(runtime, delta_text)
    append_pending_delta(runtime, delta_text)
    now_ms = monotonic_ms()
    if should_flush_delta_event(runtime, now_ms=now_ms, force_publish=force_publish):
        await flush_pending_assistant_text_delta_locked(
            runtime=runtime,
            database_messages=database_messages,
            event_bus=event_bus,
            force_publish=force_publish,
        )
    await flush_streaming_assistant_content_if_due_locked(
        runtime=runtime,
        database_messages=database_messages,
        force=False,
    )


async def flush_pending_assistant_text_delta_locked(
    *,
    runtime: AssistantTimelineRuntime,
    database_messages: DatabaseStreamingMessagesProtocol,
    event_bus: EventBusProtocol,
    force_publish: bool = False,
) -> bool:
    now_ms = monotonic_ms()
    if not should_flush_delta_event(runtime, now_ms=now_ms, force_publish=force_publish):
        return False
    drained = drain_pending_delta(runtime)
    if not drained:
        return False
    clear_status_preview_state(runtime=runtime, now_ms=now_ms)
    await complete_processing_activity_if_running_locked(
        runtime=runtime,
        event_bus=event_bus,
        database_messages=database_messages,
        status=TIMELINE_ACTIVITY_STATUS_COMPLETED,
    )
    runtime.assistant_visible_output_started = True
    note_visible_activity_locked(runtime, now_ms=now_ms)
    await publish_chat_stream_event_locked(
        event_bus,
        runtime,
        database_messages,
        event_type="assistant_text_delta",
        payload={
            "assistant_at_ms": runtime.assistant_at_ms,
            "delta": drained,
        },
    )
    runtime.assistant_delta_emitted = True
    runtime.assistant_delta_last_emit_ms = now_ms
    return True


async def flush_assistant_visible_chronology(
    *,
    runtime: AssistantTimelineRuntime,
    database_messages: DatabaseStreamingMessagesProtocol,
    event_bus: EventBusProtocol,
) -> int:
    lock = ensure_chat_stream_publish_lock(runtime)
    async with lock:
        return await flush_assistant_visible_chronology_locked(
            runtime=runtime,
            database_messages=database_messages,
            event_bus=event_bus,
        )


async def flush_assistant_visible_chronology_locked(
    *,
    runtime: AssistantTimelineRuntime,
    database_messages: DatabaseStreamingMessagesProtocol,
    event_bus: EventBusProtocol,
) -> int:
    await flush_pending_assistant_text_delta_locked(
        runtime=runtime,
        database_messages=database_messages,
        event_bus=event_bus,
        force_publish=True,
    )
    await flush_chat_stream_event_persistence(
        runtime,
        database_messages,
        force=True,
    )
    await flush_streaming_assistant_content_if_due_locked(
        runtime=runtime,
        database_messages=database_messages,
        force=True,
    )
    return runtime.assistant_visible_chars


async def flush_pending_assistant_text_and_finalize_processing_locked(
    *,
    runtime: AssistantTimelineRuntime,
    database_messages: DatabaseStreamingMessagesProtocol,
    event_bus: EventBusProtocol,
    status: str,
) -> int | None:
    flushed = await flush_pending_assistant_text_delta_locked(
        runtime=runtime,
        database_messages=database_messages,
        event_bus=event_bus,
        force_publish=True,
    )
    await complete_processing_activity_if_running_locked(
        runtime=runtime,
        event_bus=event_bus,
        database_messages=database_messages,
        status=status,
    )
    note_visible_activity_locked(runtime, now_ms=monotonic_ms())
    if not flushed:
        return None
    return runtime.assistant_visible_chars


async def flush_pending_assistant_text_delta(
    *,
    runtime: AssistantTimelineRuntime,
    database_messages: DatabaseStreamingMessagesProtocol,
    event_bus: EventBusProtocol,
) -> bool:
    lock = ensure_chat_stream_publish_lock(runtime)
    async with lock:
        result = await flush_pending_assistant_text_delta_locked(
            runtime=runtime,
            database_messages=database_messages,
            event_bus=event_bus,
            force_publish=True,
        )
    return result
