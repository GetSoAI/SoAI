"""SoAI - Shared assistant timeline success finalization [backend/features/assistant_timeline/stream_finalize_success.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.logging.trace import get_logger
from features.assistant_timeline.activity_status_sets import (
    TIMELINE_ACTIVITY_STATUS_COMPLETED,
)
from features.assistant_timeline.stream_finalize_context import (
    ChatStreamFinalizeContext,
)
from features.assistant_timeline.stream_finalize_success_completion import (
    finalize_visible_chat_stream_success,
)
from features.assistant_timeline.stream_finalize_success_empty import (
    finalize_empty_chat_stream_success,
)
from features.assistant_timeline.stream_finalize_success_state import (
    collect_chat_stream_success_snapshot,
)
from features.assistant_timeline.stream_terminal_executor import (
    run_chat_stream_terminal_finalization,
)
from features.assistant_timeline.thinking_phase_tail_finalization import (
    finalize_thinking_tail_phase_for_context,
)

__all__ = ("finalize_chat_stream_success",)

LOGGER_NAME = "SoAI.features.assistant_timeline.stream_finalize_success"
OPERATION_SUCCESS = "webui_ws_chat_stream.finalize.success"


async def finalize_chat_stream_success(
    context: ChatStreamFinalizeContext,
    *,
    flush_pending_tool_events_before_terminal_synthesis: bool = False,
) -> bool:
    async def finalize_claimed() -> None:
        context.stream_transcript.finalize()
        thinking_tail_duration_ms = await finalize_thinking_tail_phase_for_context(
            context=context,
            status=TIMELINE_ACTIVITY_STATUS_COMPLETED,
        )
        snapshot = collect_chat_stream_success_snapshot(
            context=context,
            thinking_tail_duration_ms=thinking_tail_duration_ms,
        )
        if (
            not snapshot.has_visible_text
            and not snapshot.has_visible_thinking_phase
            and not snapshot.has_visible_tool_calls
            and not snapshot.has_visible_images
        ):
            await finalize_empty_chat_stream_success(
                context=context,
                snapshot=snapshot,
            )
            return
        await finalize_visible_chat_stream_success(
            context=context,
            snapshot=snapshot,
            flush_pending_tool_events_before_terminal_synthesis=flush_pending_tool_events_before_terminal_synthesis,
        )

    return await run_chat_stream_terminal_finalization(
        context=context,
        operation=OPERATION_SUCCESS,
        logger=get_logger(LOGGER_NAME),
        failure_message="Failed to finalize chat stream success.",
        finalize_claimed=finalize_claimed,
    )
