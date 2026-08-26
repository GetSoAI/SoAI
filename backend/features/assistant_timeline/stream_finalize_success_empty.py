"""SoAI - Shared assistant timeline empty-success finalization [backend/features/assistant_timeline/stream_finalize_success_empty.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_handled_exception
from core.logging.trace import get_logger
from features.assistant_timeline.loading_error_finalization import (
    finalize_and_publish_loading_error,
)
from features.assistant_timeline.processing_activity import (
    complete_processing_activity_if_running,
)
from features.assistant_timeline.publish import flush_chat_stream_event_persistence
from features.assistant_timeline.stream_finalize_context import (
    ChatStreamFinalizeContext,
)
from features.assistant_timeline.stream_finalize_success_state import (
    ChatStreamSuccessSnapshot,
)
from features.assistant_timeline.stream_finalize_support import (
    flush_pending_visible_text_deltas,
)
from features.assistant_timeline.stream_terminal_lifecycle import (
    complete_chat_stream_terminal_finalization,
)
from features.assistant_timeline.wait_for_user_activity import (
    complete_wait_for_user_activity_if_running,
)

__all__ = ("finalize_empty_chat_stream_success",)

LOGGER_NAME = "SoAI.features.assistant_timeline.stream_finalize_success_empty"
OPERATION = "webui_ws_chat_stream.finalize.empty_response"
_EMPTY_RESPONSE_MESSAGE = "Chat stream completed successfully but produced no visible output."
_EMPTY_RESPONSE_CODE = "empty_response"


def _error_details(context: ChatStreamFinalizeContext) -> dict[str, int | str | None]:
    return {
        "conv_id": context.runtime.conv_id,
        "request_id": context.runtime.request_id,
        "assistant_at_ms": context.runtime.assistant_at_ms,
        "user_id": context.runtime.user_id,
        "model_id": context.runtime.model_id,
    }


async def finalize_empty_chat_stream_success(
    *,
    context: ChatStreamFinalizeContext,
    snapshot: ChatStreamSuccessSnapshot,
) -> None:
    await flush_pending_visible_text_deltas(
        runtime=context.runtime,
        stream_transcript=context.stream_transcript,
        database_messages=context.database_messages,
        event_bus=context.event_bus,
        pending_visible_text=snapshot.pending_visible_text,
    )
    logger = get_logger(LOGGER_NAME)
    error_to_log = coerce_to_soai_error(
        RuntimeError(_EMPTY_RESPONSE_MESSAGE),
        message=_EMPTY_RESPONSE_MESSAGE,
        code=_EMPTY_RESPONSE_CODE,
        operation=OPERATION,
        details=_error_details(context),
    )
    log_details = _error_details(context)
    log_details["code"] = _EMPTY_RESPONSE_CODE
    log_handled_exception(
        logger,
        error_to_log,
        message="Chat stream finalized as error due to empty visible output (non-critical).",
        operation=OPERATION,
        details=log_details,
        level="debug",
    )
    await complete_wait_for_user_activity_if_running(
        runtime=context.runtime,
        event_bus=context.event_bus,
        database_messages=context.database_messages,
        status="error",
        reason=_EMPTY_RESPONSE_MESSAGE,
    )
    await complete_processing_activity_if_running(
        runtime=context.runtime,
        event_bus=context.event_bus,
        database_messages=context.database_messages,
        status="error",
        reason=_EMPTY_RESPONSE_MESSAGE,
        error_type=_EMPTY_RESPONSE_CODE,
    )
    await finalize_and_publish_loading_error(
        runtime=context.runtime,
        event_bus=context.event_bus,
        database_messages=context.database_messages,
        duration_ms=snapshot.duration_ms,
        thinking_tail_duration_ms=snapshot.thinking_tail_duration_ms,
        message=_EMPTY_RESPONSE_MESSAGE,
        code=_EMPTY_RESPONSE_CODE,
    )
    await flush_chat_stream_event_persistence(
        context.runtime,
        context.database_messages,
        force=True,
    )
    await complete_chat_stream_terminal_finalization(context)
