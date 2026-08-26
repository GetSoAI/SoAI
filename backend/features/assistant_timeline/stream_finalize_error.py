"""SoAI - Assistant timeline error finalization [backend/features/assistant_timeline/stream_finalize_error.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.logging.trace import get_logger
from core.timing.monotonic import monotonic_ms
from features.assistant_timeline.loading_error_finalization import (
    finalize_and_publish_loading_error,
)
from features.assistant_timeline.publish import flush_chat_stream_event_persistence
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
from features.assistant_timeline.thinking_phase_tail_finalization import (
    finalize_thinking_tail_phase_for_context,
)

__all__ = ("finalize_chat_stream_error",)

LOGGER_NAME = "SoAI.features.assistant_timeline.stream_finalize_error"
OPERATION_ERROR = "webui_ws_chat_stream.finalize.error"


async def finalize_chat_stream_error(
    context: ChatStreamFinalizeContext,
    *,
    message: str,
    code: str,
    flush_deferred_visible_text: bool = True,
) -> bool:
    async def finalize_claimed() -> None:
        await _finalize_claimed_chat_stream_error(
            context=context,
            message=message,
            code=code,
            flush_deferred_visible_text=flush_deferred_visible_text,
        )

    return await run_chat_stream_terminal_finalization(
        context=context,
        operation=OPERATION_ERROR,
        logger=get_logger(LOGGER_NAME),
        failure_message="Failed to finalize chat stream error.",
        finalize_claimed=finalize_claimed,
    )


async def _finalize_claimed_chat_stream_error(
    *,
    context: ChatStreamFinalizeContext,
    message: str,
    code: str,
    flush_deferred_visible_text: bool,
) -> None:
    normalized_message = message.strip() if message.strip() else "Chat stream failed."
    normalized_code = code.strip() if code.strip() else "server_error"
    log_chat_stream_terminal_status(
        context=context,
        operation=OPERATION_ERROR,
        logger=get_logger(LOGGER_NAME),
        normalized_message=normalized_message,
        code=normalized_code,
        log_message="Chat stream finalized with error (non-critical).",
        level="debug",
    )
    context.stream_transcript.finalize()
    thinking_tail_duration_ms = await finalize_thinking_tail_phase_for_context(
        context=context,
        status="error",
    )
    await complete_terminal_activity_states(
        context=context,
        status="error",
        reason=normalized_message,
        error_type=normalized_code,
    )
    if flush_deferred_visible_text:
        await flush_pending_visible_text_deltas(
            runtime=context.runtime,
            stream_transcript=context.stream_transcript,
            database_messages=context.database_messages,
            event_bus=context.event_bus,
            pending_visible_text=None,
        )
    duration_ms = max(0, monotonic_ms() - context.runtime.started_at_monotonic_ms)
    await finalize_and_publish_loading_error(
        runtime=context.runtime,
        event_bus=context.event_bus,
        database_messages=context.database_messages,
        duration_ms=duration_ms,
        thinking_tail_duration_ms=thinking_tail_duration_ms,
        message=normalized_message,
        code=normalized_code,
    )
    await flush_chat_stream_event_persistence(
        context.runtime,
        context.database_messages,
        force=True,
    )
    await complete_chat_stream_terminal_finalization(context)
