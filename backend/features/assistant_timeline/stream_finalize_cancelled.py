"""SoAI - Assistant timeline cancellation finalization [backend/features/assistant_timeline/stream_finalize_cancelled.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.logging.trace import get_logger
from core.timing.monotonic import monotonic_ms
from features.assistant_timeline.activity_status_sets import (
    TIMELINE_ACTIVITY_STATUS_CANCELLED,
    TIMELINE_ACTIVITY_STATUS_RUNNING,
)
from features.assistant_timeline.loading_activity_payloads import (
    build_loading_activity_payload,
)
from features.assistant_timeline.publish import publish_chat_stream_event
from features.assistant_timeline.stream_finalize_context import (
    ChatStreamFinalizeContext,
)
from features.assistant_timeline.stream_finalize_logging import (
    log_chat_stream_terminal_status,
)
from features.assistant_timeline.stream_finalize_support import (
    flush_pending_visible_text_deltas,
)
from features.assistant_timeline.stream_terminal_activity_cleanup import (
    complete_terminal_activity_states,
)
from features.assistant_timeline.stream_terminal_executor import (
    run_chat_stream_terminal_finalization,
)
from features.assistant_timeline.stream_terminal_lifecycle import (
    complete_chat_stream_terminal_finalization,
)
from features.assistant_timeline.terminal_event_publication import (
    build_cancelled_assistant_finalization,
    persist_and_publish_terminal_chat_stream_event,
)
from features.assistant_timeline.thinking_phase_tail_finalization import (
    finalize_thinking_tail_phase_for_context,
)

__all__ = ("finalize_chat_stream_cancelled",)

LOGGER_NAME = "SoAI.features.assistant_timeline.stream_finalize_cancelled"
OPERATION_CANCELLED = "webui_ws_chat_stream.finalize.cancelled"


async def finalize_chat_stream_cancelled(
    context: ChatStreamFinalizeContext,
    *,
    reason: str,
    code: str = "cancelled",
) -> bool:
    async def finalize_claimed() -> None:
        await _finalize_claimed_chat_stream_cancelled(context=context, reason=reason, code=code)

    return await run_chat_stream_terminal_finalization(
        context=context,
        operation=OPERATION_CANCELLED,
        logger=get_logger(LOGGER_NAME),
        failure_message="Failed to finalize chat stream cancellation.",
        terminal_outcome="cancelled",
        finalize_claimed=finalize_claimed,
    )


async def _finalize_claimed_chat_stream_cancelled(
    *,
    context: ChatStreamFinalizeContext,
    reason: str,
    code: str,
) -> None:
    normalized_reason = reason.strip() if reason.strip() else "Chat stream was cancelled."
    cancel_code = code.strip() if code.strip() else "cancelled"
    log_chat_stream_terminal_status(
        context=context,
        operation=OPERATION_CANCELLED,
        logger=get_logger(LOGGER_NAME),
        normalized_message=normalized_reason,
        code=cancel_code,
        log_message="Chat stream finalized as cancelled (non-critical).",
        level="debug",
    )
    context.stream_transcript.finalize()
    thinking_tail_duration_ms = await finalize_thinking_tail_phase_for_context(
        context=context,
        status=TIMELINE_ACTIVITY_STATUS_CANCELLED,
    )
    await complete_terminal_activity_states(
        context=context,
        status=TIMELINE_ACTIVITY_STATUS_CANCELLED,
        reason=normalized_reason,
        error_type=TIMELINE_ACTIVITY_STATUS_CANCELLED,
    )
    duration_ms = max(0, monotonic_ms() - context.runtime.started_at_monotonic_ms)
    await flush_pending_visible_text_deltas(
        runtime=context.runtime,
        stream_transcript=context.stream_transcript,
        database_messages=context.database_messages,
        event_bus=context.event_bus,
        pending_visible_text=None,
    )
    loading_was_running = (
        context.runtime.loading_activity.status == TIMELINE_ACTIVITY_STATUS_RUNNING
    )
    loading_cancelled = None
    if loading_was_running:
        context.runtime.loading_activity.status = TIMELINE_ACTIVITY_STATUS_CANCELLED
        context.runtime.loading_activity.duration_ms = duration_ms
        loading_cancelled = build_loading_activity_payload(
            runtime=context.runtime,
            status=TIMELINE_ACTIVITY_STATUS_CANCELLED,
            duration_ms=duration_ms,
            reason=normalized_reason,
            error_type=TIMELINE_ACTIVITY_STATUS_CANCELLED,
        )
    if loading_was_running and loading_cancelled is not None:
        await publish_chat_stream_event(
            event_bus=context.event_bus,
            runtime=context.runtime,
            database_messages=context.database_messages,
            event_type="loading_activity",
            payload={
                "assistant_at_ms": context.runtime.assistant_at_ms,
                "loading_activity": loading_cancelled,
            },
        )
    await persist_and_publish_terminal_chat_stream_event(
        event_bus=context.event_bus,
        runtime=context.runtime,
        database_messages=context.database_messages,
        event_type=TIMELINE_ACTIVITY_STATUS_CANCELLED,
        payload={
            "assistant_at_ms": context.runtime.assistant_at_ms,
            "reason": normalized_reason,
            "code": cancel_code,
        },
        finalization=build_cancelled_assistant_finalization(
            duration_ms=duration_ms,
            thinking_tail_duration_ms=thinking_tail_duration_ms,
            reason=normalized_reason,
            code=cancel_code,
        ),
    )
    await complete_chat_stream_terminal_finalization(context)
