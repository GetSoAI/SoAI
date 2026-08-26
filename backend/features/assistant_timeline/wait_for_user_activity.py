"""SoAI - Shared assistant timeline wait-for-user activity ticker [backend/features/assistant_timeline/wait_for_user_activity.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import TYPE_CHECKING

from core.activity_payloads import build_activity_payload
from core.concurrency.ephemeral_tasks import create_ephemeral_task
from core.conversations.protocols_database_message_streaming import (
    DatabaseStreamingMessagesProtocol,
)
from core.elicitation_task_scanning import (
    resolve_pending_conversation_elicitation_interaction_type,
)
from core.errors.exceptions import ValidationError
from core.tasks.type_catalog import TASK_TYPE_MCP_ELICITATION
from core.timing.constants import STANDARD_DELAY_SEC
from core.timing.epoch import epoch_ms
from core.timing.monotonic import monotonic_ms
from features.assistant_timeline.activity_status_sets import (
    TIMELINE_ACTIVITY_STATUS_COMPLETED,
    TIMELINE_ACTIVITY_TERMINAL_STATUSES,
)
from features.assistant_timeline.activity_timing import (
    ensure_activity_start_times,
    resolve_activity_running_duration_ms,
)
from features.assistant_timeline.models import AssistantTimelineRuntime
from features.assistant_timeline.processing_activity import note_visible_activity_locked
from features.assistant_timeline.publish import (
    ensure_chat_stream_publish_lock,
    publish_chat_stream_event_locked,
)

if TYPE_CHECKING:
    from core.events.protocols import EventBusProtocol
    from core.tasks.protocols_query import TaskRegistryQueryView
    from core.types.json import JSONDict

__all__ = (
    "complete_wait_for_user_activity_if_running",
    "complete_wait_for_user_activity_if_running_locked",
    "start_wait_for_user_activity_ticker",
)


def build_wait_for_user_activity_payload(
    *,
    runtime: AssistantTimelineRuntime,
    status: str,
    duration_ms: int,
    now_epoch_ms: int,
    now_monotonic_ms: int,
    reason: str | None,
) -> JSONDict:
    started_at_epoch_ms, _started_at_monotonic_ms = ensure_activity_start_times(
        runtime.wait_for_user_activity,
        default_started_at_epoch_ms=int(now_epoch_ms),
        default_started_at_monotonic_ms=int(now_monotonic_ms),
    )
    return build_activity_payload(
        status=status,
        started_at_ms=started_at_epoch_ms,
        duration_ms=duration_ms,
        reason=reason,
        error_type=None,
    )


async def complete_wait_for_user_activity_if_running_locked(
    *,
    runtime: AssistantTimelineRuntime,
    event_bus: EventBusProtocol,
    database_messages: DatabaseStreamingMessagesProtocol,
    status: str,
    reason: str | None = None,
) -> bool:
    if runtime.wait_for_user_activity.status != "running":
        return False
    if status not in TIMELINE_ACTIVITY_TERMINAL_STATUSES:
        raise ValidationError(
            "Wait-for-user completion status must be completed, cancelled, or error.",
        )
    now_monotonic_ms = int(monotonic_ms())
    now_epoch_ms = int(epoch_ms())
    _, _started_at_monotonic_ms = ensure_activity_start_times(
        runtime.wait_for_user_activity,
        default_started_at_epoch_ms=int(now_epoch_ms),
        default_started_at_monotonic_ms=int(now_monotonic_ms),
    )
    duration_ms = resolve_activity_running_duration_ms(
        runtime.wait_for_user_activity,
        now_monotonic_ms=now_monotonic_ms,
    )
    runtime.wait_for_user_activity.status = status
    runtime.wait_for_user_activity.duration_ms = duration_ms
    payload = build_wait_for_user_activity_payload(
        runtime=runtime,
        status=status,
        duration_ms=duration_ms,
        now_epoch_ms=now_epoch_ms,
        now_monotonic_ms=now_monotonic_ms,
        reason=reason,
    )
    await publish_chat_stream_event_locked(
        event_bus,
        runtime,
        database_messages,
        event_type="wait_for_user_activity",
        payload={
            "assistant_at_ms": runtime.assistant_at_ms,
            "wait_for_user_activity": payload,
        },
    )
    return True


async def complete_wait_for_user_activity_if_running(
    *,
    runtime: AssistantTimelineRuntime,
    event_bus: EventBusProtocol,
    database_messages: DatabaseStreamingMessagesProtocol,
    status: str,
    reason: str | None = None,
) -> bool:
    lock = ensure_chat_stream_publish_lock(runtime)
    async with lock:
        return await complete_wait_for_user_activity_if_running_locked(
            runtime=runtime,
            event_bus=event_bus,
            database_messages=database_messages,
            status=status,
            reason=reason,
        )


def start_wait_for_user_activity_ticker(
    *,
    runtime: AssistantTimelineRuntime,
    event_bus: EventBusProtocol,
    database_messages: DatabaseStreamingMessagesProtocol,
    task_registry_queries: TaskRegistryQueryView,
    track_background_task: Callable[[asyncio.Task[None]], None],
) -> asyncio.Task[None]:
    async def wait_for_user_ticker() -> None:
        while runtime.detach_event is not None and not runtime.detach_event.is_set():
            await asyncio.sleep(STANDARD_DELAY_SEC)
            if runtime.detach_event is None or runtime.detach_event.is_set():
                return
            user_id = int(runtime.user_id)
            conv_id = str(runtime.conv_id or "").strip()
            active_interaction: str | None = None
            if user_id > 0 and conv_id:
                tasks = await task_registry_queries.query_active_by_user(
                    user_id,
                    task_type=TASK_TYPE_MCP_ELICITATION,
                    limit=500,
                )
                active_interaction = resolve_pending_conversation_elicitation_interaction_type(
                    tasks,
                    conv_id=conv_id,
                )
            lock = ensure_chat_stream_publish_lock(runtime)
            async with lock:
                if runtime.detach_event is None or runtime.detach_event.is_set():
                    return
                now_monotonic_ms = int(monotonic_ms())
                now_epoch_ms = int(epoch_ms())
                if active_interaction is None:
                    if runtime.wait_for_user_activity.status == "running":
                        await complete_wait_for_user_activity_if_running_locked(
                            runtime=runtime,
                            event_bus=event_bus,
                            database_messages=database_messages,
                            status=TIMELINE_ACTIVITY_STATUS_COMPLETED,
                            reason=None,
                        )
                    continue
                note_visible_activity_locked(runtime, now_ms=now_monotonic_ms)
                if runtime.wait_for_user_activity.status != "running":
                    runtime.wait_for_user_activity.status = "running"
                    runtime.wait_for_user_activity.started_at_monotonic_ms = now_monotonic_ms
                    runtime.wait_for_user_activity.started_at_epoch_ms = now_epoch_ms
                    runtime.wait_for_user_activity.duration_ms = 0
                    payload = build_wait_for_user_activity_payload(
                        runtime=runtime,
                        status="running",
                        duration_ms=0,
                        now_epoch_ms=now_epoch_ms,
                        now_monotonic_ms=now_monotonic_ms,
                        reason=None,
                    )
                    await publish_chat_stream_event_locked(
                        event_bus,
                        runtime,
                        database_messages,
                        event_type="wait_for_user_activity",
                        payload={
                            "assistant_at_ms": runtime.assistant_at_ms,
                            "wait_for_user_activity": payload,
                        },
                    )

    task = create_ephemeral_task(
        wait_for_user_ticker(),
        name=f"ws-chat-wait-user-{runtime.conv_id}",
    )
    track_background_task(task)
    return task
