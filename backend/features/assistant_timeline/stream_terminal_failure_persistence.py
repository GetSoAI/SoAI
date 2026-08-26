"""SoAI - Assistant timeline durable terminal failure persistence [backend/features/assistant_timeline/stream_terminal_failure_persistence.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.conversations.streaming_message_errors import (
    StreamingAssistantMessageAlreadyFinalizedError,
)
from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.exceptions import SoAIError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.timing.monotonic import monotonic_ms
from features.assistant_timeline.message_write_versions import (
    record_assistant_timeline_message_write,
)
from features.assistant_timeline.publish import (
    ensure_chat_stream_publish_lock,
    publish_chat_stream_event,
)
from features.assistant_timeline.stream_terminal_lifecycle import (
    detach_chat_stream_terminal_finalization,
)

if TYPE_CHECKING:
    from features.assistant_timeline.stream_finalize_context import (
        ChatStreamFinalizeContext,
    )

__all__ = (
    "mark_chat_stream_terminal_failure_detached",
    "persist_chat_stream_terminal_failure_state",
)

LOGGER_NAME = "SoAI.features.assistant_timeline.stream_terminal_failure_persistence"
OPERATION_TERMINAL_FAILURE_DETACH_PUBLISH = "webui_ws_chat_stream.terminal_failure.detach_publish"
OPERATION_TERMINAL_FAILURE_FINALIZE_CONFLICT = (
    "webui_ws_chat_stream.terminal_failure.finalize_conflict"
)
TERMINAL_FAILURE_EVENT_MESSAGE = "Chat stream failed."
TERMINAL_FAILURE_EVENT_CODE = "server_error"

_TERMINAL_FAILURE_PUBLISH_EXCEPTIONS: tuple[type[Exception], ...] = (
    SoAIError,
    *RECOVERABLE_EXCEPTIONS,
)


async def _publish_terminal_failure_event_once(
    *,
    context: ChatStreamFinalizeContext,
) -> None:
    if context.runtime.terminal_event_published:
        return
    try:
        await publish_chat_stream_event(
            context.event_bus,
            context.runtime,
            context.database_messages,
            event_type="error",
            payload={
                "assistant_at_ms": context.runtime.assistant_at_ms,
                "message": TERMINAL_FAILURE_EVENT_MESSAGE,
                "code": TERMINAL_FAILURE_EVENT_CODE,
                "reference_id": context.runtime.request_id,
            },
        )
    except _TERMINAL_FAILURE_PUBLISH_EXCEPTIONS as exception:
        log_exception(
            get_logger(LOGGER_NAME),
            exception,
            message="Failed to publish terminal error event during chat stream failure detach.",
            operation=OPERATION_TERMINAL_FAILURE_DETACH_PUBLISH,
            level="error",
            details={
                "conv_id": context.runtime.conv_id,
                "request_id": context.runtime.request_id,
            },
        )
        return
    context.runtime.terminal_event_published = True


async def mark_chat_stream_terminal_failure_detached(
    *,
    context: ChatStreamFinalizeContext,
) -> None:
    await _publish_terminal_failure_event_once(context=context)
    await detach_chat_stream_terminal_finalization(
        context,
        terminal_finalization_started=False,
        terminal_event_emitted=True,
        terminal_persistence_completed=True,
    )


async def persist_chat_stream_terminal_failure_state(
    *,
    context: ChatStreamFinalizeContext,
    terminal_reason: str,
) -> None:
    lock = ensure_chat_stream_publish_lock(context.runtime)
    async with lock:
        if context.runtime.terminal_persistence_completed:
            return
        if context.runtime.assistant_placeholder_persisted:
            duration_ms = max(0, monotonic_ms() - context.runtime.started_at_monotonic_ms)
            try:
                await context.runtime.require_mutation_allowed()
                write_result = await context.database_messages.finalize_streaming_assistant_message(
                    context.runtime.conv_id,
                    context.runtime.user_id,
                    created_at_ms=context.runtime.assistant_at_ms,
                    request_id=context.runtime.request_id,
                    finish_reason="error",
                    prompt_tokens=None,
                    completion_tokens=None,
                    total_tokens=None,
                    usage_source=None,
                    generation_latency_ms=duration_ms,
                    thinking_tail_duration_ms=None,
                    terminal_reason=terminal_reason,
                    input_finalization=context.runtime.input_finalization,
                    input_terminal_code=TERMINAL_FAILURE_EVENT_CODE,
                )
            except StreamingAssistantMessageAlreadyFinalizedError as exception:
                log_handled_exception(
                    get_logger(LOGGER_NAME),
                    exception,
                    message=(
                        "Streaming assistant message was already finalized while persisting "
                        "terminal failure (non-critical)."
                    ),
                    operation=OPERATION_TERMINAL_FAILURE_FINALIZE_CONFLICT,
                    level="debug",
                    details={
                        "conv_id": context.runtime.conv_id,
                        "request_id": context.runtime.request_id,
                    },
                )
            else:
                record_assistant_timeline_message_write(context.runtime, write_result)
                if context.runtime.input_finalization is not None:
                    context.runtime.input_terminal_state = "failed"
                    context.runtime.input_terminal_code = TERMINAL_FAILURE_EVENT_CODE
    await mark_chat_stream_terminal_failure_detached(context=context)
