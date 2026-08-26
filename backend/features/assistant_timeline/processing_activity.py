"""SoAI - Shared processing activity ticker [backend/features/assistant_timeline/processing_activity.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import TYPE_CHECKING

from core.concurrency.ephemeral_tasks import create_ephemeral_task
from core.conversations.protocols_database_message_streaming import (
    DatabaseStreamingMessagesProtocol,
)
from core.errors.exceptions import ValidationError
from core.timing.constants import STANDARD_DELAY_SEC
from core.timing.epoch import epoch_ms
from core.timing.monotonic import monotonic_ms
from core.validation.integers import coerce_non_negative_int_or_zero
from features.assistant_timeline.activity_status_sets import (
    TIMELINE_ACTIVITY_EMITTED_STATUSES,
    TIMELINE_ACTIVITY_STATUS_COMPLETED,
    TIMELINE_ACTIVITY_STATUS_RUNNING,
    TIMELINE_ACTIVITY_TERMINAL_STATUSES,
    TIMELINE_ACTIVITY_VALID_STATUSES,
)
from features.assistant_timeline.activity_timing import (
    resolve_activity_running_duration_ms,
)
from features.assistant_timeline.models import AssistantTimelineRuntime
from features.assistant_timeline.processing_activity_support import (
    PROCESSING_IDLE_THRESHOLD_MS,
    build_processing_activity_payload,
    ensure_processing_activity_start_times,
    has_running_activity_before_processing,
    note_visible_activity_locked,
)
from features.assistant_timeline.publish import (
    ensure_chat_stream_publish_lock,
    publish_chat_stream_event_locked,
)

if TYPE_CHECKING:
    from core.events.protocols import EventBusProtocol
    from core.types.json import JSONDict

__all__ = (
    "complete_processing_activity_if_running",
    "complete_processing_activity_if_running_locked",
    "note_visible_activity",
    "note_visible_activity_locked",
    "resolve_processing_activity_payload",
    "start_processing_activity_ticker",
)


async def note_visible_activity(*, runtime: AssistantTimelineRuntime) -> int:
    lock = ensure_chat_stream_publish_lock(runtime)
    async with lock:
        return note_visible_activity_locked(runtime)


def resolve_processing_activity_payload(
    *,
    runtime: AssistantTimelineRuntime,
    now_ms: int | None = None,
    reason: str | None = None,
    error_type: str | None = None,
) -> JSONDict | None:
    status = runtime.processing_activity.status
    if status not in TIMELINE_ACTIVITY_EMITTED_STATUSES:
        return None
    resolved_now_monotonic_ms = (
        coerce_non_negative_int_or_zero(now_ms) if now_ms is not None else monotonic_ms()
    )
    resolved_now_epoch_ms = int(epoch_ms())
    duration_ms = runtime.processing_activity.duration_ms
    if status == TIMELINE_ACTIVITY_STATUS_RUNNING:
        _, _started_at_monotonic_ms = ensure_processing_activity_start_times(
            runtime,
            now_epoch_ms=resolved_now_epoch_ms,
            now_monotonic_ms=int(resolved_now_monotonic_ms),
        )
        duration_ms = resolve_activity_running_duration_ms(
            runtime.processing_activity,
            now_monotonic_ms=int(resolved_now_monotonic_ms),
        )
    return build_processing_activity_payload(
        runtime=runtime,
        status=status,
        duration_ms=duration_ms,
        now_epoch_ms=resolved_now_epoch_ms,
        now_monotonic_ms=int(resolved_now_monotonic_ms),
        reason=reason,
        error_type=error_type,
    )


async def complete_processing_activity_if_running_locked(
    *,
    runtime: AssistantTimelineRuntime,
    event_bus: EventBusProtocol,
    database_messages: DatabaseStreamingMessagesProtocol,
    status: str = TIMELINE_ACTIVITY_STATUS_COMPLETED,
    reason: str | None = None,
    error_type: str | None = None,
) -> bool:
    if runtime.processing_activity.status != TIMELINE_ACTIVITY_STATUS_RUNNING:
        return False
    if status not in TIMELINE_ACTIVITY_TERMINAL_STATUSES:
        raise ValidationError(
            "Processing completion status must be completed, cancelled, or error.",
        )
    now_monotonic_ms = monotonic_ms()
    now_epoch_ms = epoch_ms()
    _, _started_at_monotonic_ms = ensure_processing_activity_start_times(
        runtime,
        now_epoch_ms=int(now_epoch_ms),
        now_monotonic_ms=int(now_monotonic_ms),
    )
    duration_ms = resolve_activity_running_duration_ms(
        runtime.processing_activity,
        now_monotonic_ms=int(now_monotonic_ms),
    )
    runtime.processing_activity.status = status
    runtime.processing_activity.duration_ms = duration_ms
    payload = build_processing_activity_payload(
        runtime=runtime,
        status=status,
        duration_ms=duration_ms,
        now_epoch_ms=int(now_epoch_ms),
        now_monotonic_ms=int(now_monotonic_ms),
        reason=reason,
        error_type=error_type,
    )
    await publish_chat_stream_event_locked(
        event_bus,
        runtime,
        database_messages,
        event_type="processing_activity",
        payload={
            "assistant_at_ms": runtime.assistant_at_ms,
            "processing_activity": payload,
        },
    )
    return True


async def complete_processing_activity_if_running(
    *,
    runtime: AssistantTimelineRuntime,
    event_bus: EventBusProtocol,
    database_messages: DatabaseStreamingMessagesProtocol,
    status: str = TIMELINE_ACTIVITY_STATUS_COMPLETED,
    reason: str | None = None,
    error_type: str | None = None,
) -> bool:
    lock = ensure_chat_stream_publish_lock(runtime)
    async with lock:
        return await complete_processing_activity_if_running_locked(
            runtime=runtime,
            event_bus=event_bus,
            database_messages=database_messages,
            status=status,
            reason=reason,
            error_type=error_type,
        )


def start_processing_activity_ticker(
    *,
    runtime: AssistantTimelineRuntime,
    event_bus: EventBusProtocol,
    database_messages: DatabaseStreamingMessagesProtocol,
    track_background_task: Callable[[asyncio.Task[None]], None],
) -> asyncio.Task[None]:
    async def processing_ticker() -> None:
        while runtime.detach_event is not None and not runtime.detach_event.is_set():
            await asyncio.sleep(STANDARD_DELAY_SEC)
            if runtime.detach_event is None or runtime.detach_event.is_set():
                return
            lock = ensure_chat_stream_publish_lock(runtime)
            async with lock:
                if runtime.detach_event is None or runtime.detach_event.is_set():
                    return
                if has_running_activity_before_processing(runtime):
                    continue
                now_monotonic_ms = monotonic_ms()
                now_epoch_ms = epoch_ms()
                status = runtime.processing_activity.status
                if status == TIMELINE_ACTIVITY_STATUS_RUNNING:
                    continue
                if status not in TIMELINE_ACTIVITY_VALID_STATUSES:
                    continue
                idle_duration_ms = max(
                    0,
                    now_monotonic_ms - runtime.last_visible_activity_monotonic_ms,
                )
                if idle_duration_ms < PROCESSING_IDLE_THRESHOLD_MS:
                    continue
                runtime.processing_activity.status = TIMELINE_ACTIVITY_STATUS_RUNNING
                runtime.processing_activity.started_at_monotonic_ms = int(now_monotonic_ms)
                runtime.processing_activity.started_at_epoch_ms = None
                ensure_processing_activity_start_times(
                    runtime,
                    now_epoch_ms=int(now_epoch_ms),
                    now_monotonic_ms=int(now_monotonic_ms),
                )
                runtime.processing_activity.duration_ms = 0
                running_payload = build_processing_activity_payload(
                    runtime=runtime,
                    status=TIMELINE_ACTIVITY_STATUS_RUNNING,
                    duration_ms=0,
                    now_epoch_ms=int(now_epoch_ms),
                    now_monotonic_ms=int(now_monotonic_ms),
                )
                await publish_chat_stream_event_locked(
                    event_bus,
                    runtime,
                    database_messages,
                    event_type="processing_activity",
                    payload={
                        "assistant_at_ms": runtime.assistant_at_ms,
                        "processing_activity": running_payload,
                    },
                )

    task = create_ephemeral_task(processing_ticker(), name=f"ws-chat-processing-{runtime.conv_id}")
    track_background_task(task)
    return task
