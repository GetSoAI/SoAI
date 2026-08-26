"""SoAI - Assistant timeline terminal lifecycle state [backend/features/assistant_timeline/stream_terminal_lifecycle.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.timing.monotonic import monotonic_ms
from features.assistant_timeline.publish import ensure_chat_stream_publish_lock
from features.assistant_timeline.status_preview_state import clear_status_preview_state

if TYPE_CHECKING:
    from features.assistant_timeline.stream_finalize_context import (
        ChatStreamFinalizeContext,
    )

__all__ = (
    "begin_chat_stream_terminal_finalization",
    "complete_chat_stream_terminal_finalization",
    "detach_chat_stream_terminal_finalization",
    "fail_chat_stream_terminal_finalization",
)


async def begin_chat_stream_terminal_finalization(
    context: ChatStreamFinalizeContext,
) -> bool:
    lock = ensure_chat_stream_publish_lock(context.runtime)
    async with lock:
        if context.runtime.terminal_event_emitted:
            return False
        if context.runtime.terminal_finalization_started:
            return False
        context.runtime.terminal_finalization_started = True
        context.runtime.terminal_persistence_completed = False
        clear_status_preview_state(runtime=context.runtime, now_ms=monotonic_ms())
        detach_event = context.runtime.detach_event
    if detach_event is not None:
        detach_event.set()
    return True


async def complete_chat_stream_terminal_finalization(
    context: ChatStreamFinalizeContext,
) -> None:
    await detach_chat_stream_terminal_finalization(
        context,
        terminal_finalization_started=True,
        terminal_event_emitted=True,
        terminal_persistence_completed=True,
    )


async def detach_chat_stream_terminal_finalization(
    context: ChatStreamFinalizeContext,
    *,
    terminal_finalization_started: bool,
    terminal_event_emitted: bool,
    terminal_persistence_completed: bool,
) -> None:
    lock = ensure_chat_stream_publish_lock(context.runtime)
    async with lock:
        context.runtime.terminal_finalization_started = terminal_finalization_started
        context.runtime.terminal_event_emitted = terminal_event_emitted
        context.runtime.terminal_persistence_completed = terminal_persistence_completed
        detach_event = context.runtime.detach_event
    if detach_event is not None:
        detach_event.set()


async def fail_chat_stream_terminal_finalization(
    context: ChatStreamFinalizeContext,
) -> None:
    lock = ensure_chat_stream_publish_lock(context.runtime)
    async with lock:
        if not context.runtime.terminal_event_emitted:
            context.runtime.terminal_finalization_started = False
            context.runtime.terminal_persistence_completed = False
