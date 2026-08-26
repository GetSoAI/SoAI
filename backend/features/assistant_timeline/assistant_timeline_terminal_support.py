"""SoAI - Assistant timeline terminal-state waiting and publication [backend/features/assistant_timeline/assistant_timeline_terminal_support.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from core.concurrency.deadlines import deadline_after
from features.assistant_timeline.conversation_events import (
    publish_chat_stream_message_events,
)

if TYPE_CHECKING:
    from core.tasks.task import Task
    from features.assistant_timeline.assistant_timeline_session import (
        AssistantTimelineSession,
    )

__all__ = (
    "publish_assistant_timeline_message_events",
    "wait_for_task_terminal_state",
)

TASK_TERMINAL_WAIT_TIMEOUT_MS = 2500
TASK_TERMINAL_WAIT_POLL_SLEEP_S = 0.05


async def wait_for_task_terminal_state(
    *,
    task_id: str,
    task_lookup: Callable[[str], Awaitable[Task | None]],
    timeout_ms: int = TASK_TERMINAL_WAIT_TIMEOUT_MS,
) -> Task | None:
    deadline = deadline_after(float(max(0, int(timeout_ms))) / 1000.0)
    while not deadline.expired():
        refreshed_task = await task_lookup(task_id)
        if refreshed_task is None or refreshed_task.status.is_terminal():
            return refreshed_task
        await asyncio.sleep(TASK_TERMINAL_WAIT_POLL_SLEEP_S)
    return await task_lookup(task_id)


async def publish_assistant_timeline_message_events(session: AssistantTimelineSession) -> None:
    await publish_chat_stream_message_events(
        session.event_bus,
        session.runtime,
    )
