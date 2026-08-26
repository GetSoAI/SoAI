"""SoAI - Assistant timeline terminal activity cleanup [backend/features/assistant_timeline/stream_terminal_activity_cleanup.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from features.assistant_timeline.processing_activity import (
    complete_processing_activity_if_running,
)
from features.assistant_timeline.stream_finalize_context import (
    ChatStreamFinalizeContext,
)
from features.assistant_timeline.stream_finalize_support import (
    finalize_terminal_tool_events,
)
from features.assistant_timeline.wait_for_user_activity import (
    complete_wait_for_user_activity_if_running,
)

__all__ = ("complete_terminal_activity_states",)


async def complete_terminal_activity_states(
    *,
    context: ChatStreamFinalizeContext,
    status: str,
    reason: str,
    error_type: str,
) -> None:
    await complete_wait_for_user_activity_if_running(
        runtime=context.runtime,
        event_bus=context.event_bus,
        database_messages=context.database_messages,
        status=status,
        reason=reason,
    )
    await complete_processing_activity_if_running(
        runtime=context.runtime,
        event_bus=context.event_bus,
        database_messages=context.database_messages,
        status=status,
        reason=reason,
        error_type=error_type,
    )
    await finalize_terminal_tool_events(
        runtime=context.runtime,
        event_bus=context.event_bus,
        database_messages=context.database_messages,
        database_tool_calls=context.database_tool_calls,
        task_registry=context.task_registry,
        status=status,
        message=reason,
    )
