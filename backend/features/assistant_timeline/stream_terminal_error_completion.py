"""SoAI - Claimed assistant timeline error completion [backend/features/assistant_timeline/stream_terminal_error_completion.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.timing.monotonic import monotonic_ms
from features.assistant_timeline.loading_error_finalization import (
    finalize_and_publish_loading_error,
)
from features.assistant_timeline.publish import flush_chat_stream_event_persistence
from features.assistant_timeline.stream_finalize_context import ChatStreamFinalizeContext
from features.assistant_timeline.stream_finalize_support import (
    flush_pending_visible_text_deltas,
)
from features.assistant_timeline.stream_terminal_activity_cleanup import (
    complete_terminal_activity_states,
)
from features.assistant_timeline.stream_terminal_lifecycle import (
    complete_chat_stream_terminal_finalization,
)
from features.assistant_timeline.thinking_phase_tail_finalization import (
    finalize_thinking_tail_phase_for_context,
)

__all__ = ("complete_claimed_chat_stream_error",)


async def complete_claimed_chat_stream_error(
    *,
    context: ChatStreamFinalizeContext,
    message: str,
    code: str,
    flush_deferred_visible_text: bool,
) -> None:
    preterminal_failure: Exception | None = None
    thinking_tail_duration_ms = 0
    try:
        context.stream_transcript.finalize()
        thinking_tail_duration_ms = await finalize_thinking_tail_phase_for_context(
            context=context,
            status="error",
        )
        await complete_terminal_activity_states(
            context=context,
            status="error",
            reason=message,
            error_type=code,
        )
        if flush_deferred_visible_text:
            await flush_pending_visible_text_deltas(
                runtime=context.runtime,
                stream_transcript=context.stream_transcript,
                database_messages=context.database_messages,
                event_bus=context.event_bus,
                pending_visible_text=None,
            )
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        preterminal_failure = exception
        context.runtime.loading_activity.status = "error"
    duration_ms = max(0, monotonic_ms() - context.runtime.started_at_monotonic_ms)
    await finalize_and_publish_loading_error(
        runtime=context.runtime,
        event_bus=context.event_bus,
        database_messages=context.database_messages,
        duration_ms=duration_ms,
        thinking_tail_duration_ms=thinking_tail_duration_ms,
        message=message,
        code=code,
        publish_loading_activity=preterminal_failure is None,
    )
    await flush_chat_stream_event_persistence(
        context.runtime,
        context.database_messages,
        force=True,
    )
    if preterminal_failure is not None:
        raise preterminal_failure
    await complete_chat_stream_terminal_finalization(context)
