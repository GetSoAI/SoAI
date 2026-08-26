"""SoAI - Shared assistant timeline loading-error finalization [backend/features/assistant_timeline/loading_error_finalization.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.conversations.protocols_database_conversations import DatabaseMessagesProtocol
from core.timing.epoch import epoch_ms
from core.timing.monotonic import monotonic_ms
from features.assistant_timeline.loading_activity_payloads import (
    build_loading_activity_payload,
    sync_runtime_event_sequence_with_database,
)
from features.assistant_timeline.loading_terminal_finalization import (
    publish_loading_activity_event,
    publish_loading_terminal_events,
)
from features.assistant_timeline.models import AssistantTimelineRuntime
from features.assistant_timeline.terminal_event_publication import (
    TerminalAssistantMessageFinalization,
)

if TYPE_CHECKING:
    from core.events.protocols import EventBusProtocol
    from core.types.json import JSONDict

__all__ = (
    "finalize_and_publish_loading_error",
    "publish_initial_loading_activity",
)


async def publish_initial_loading_activity(
    *,
    runtime: AssistantTimelineRuntime,
    event_bus: EventBusProtocol,
    database_messages: DatabaseMessagesProtocol,
) -> None:
    runtime.loading_activity.started_at_monotonic_ms = int(monotonic_ms())
    runtime.loading_activity.started_at_epoch_ms = int(epoch_ms())
    runtime.loading_activity.duration_ms = 0
    await sync_runtime_event_sequence_with_database(
        runtime=runtime,
        database_messages=database_messages,
    )
    loading_running = build_loading_activity_payload(
        runtime=runtime,
        status="running",
        duration_ms=0,
        reason=None,
        error_type=None,
    )
    await publish_loading_activity_event(
        runtime=runtime,
        event_bus=event_bus,
        database_messages=database_messages,
        loading_activity=loading_running,
    )


async def finalize_and_publish_loading_error(
    *,
    runtime: AssistantTimelineRuntime,
    event_bus: EventBusProtocol,
    database_messages: DatabaseMessagesProtocol,
    duration_ms: int,
    thinking_tail_duration_ms: int,
    message: str,
    code: str,
) -> None:
    runtime.loading_activity.status = "error"
    runtime.loading_activity.duration_ms = duration_ms
    normalized_message = message.strip() if message.strip() else "Chat stream failed."
    normalized_code = code.strip() if code.strip() else "server_error"
    loading_error = build_loading_activity_payload(
        runtime=runtime,
        status="error",
        duration_ms=duration_ms,
        reason=normalized_message,
        error_type=normalized_code,
    )
    runtime.terminal_finalization_started = True
    await publish_loading_terminal_events(
        runtime=runtime,
        event_bus=event_bus,
        database_messages=database_messages,
        loading_activity=loading_error,
        terminal_event_type="error",
        terminal_payload=_build_error_event_payload(
            runtime=runtime,
            message=normalized_message,
            code=normalized_code,
        ),
        finalization=TerminalAssistantMessageFinalization(
            finish_reason="error",
            prompt_tokens=None,
            completion_tokens=None,
            total_tokens=None,
            usage_source=None,
            generation_latency_ms=duration_ms,
            thinking_tail_duration_ms=thinking_tail_duration_ms,
            terminal_reason=normalized_message,
            terminal_code=normalized_code,
        ),
    )


def _build_error_event_payload(
    *,
    runtime: AssistantTimelineRuntime,
    message: str,
    code: str,
) -> JSONDict:
    return {
        "assistant_at_ms": runtime.assistant_at_ms,
        "message": message,
        "code": code,
        "reference_id": runtime.request_id,
    }
