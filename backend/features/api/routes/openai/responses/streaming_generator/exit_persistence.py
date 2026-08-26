"""SoAI - Responses streaming exit persistence handling [backend/features/api/routes/openai/responses/streaming_generator/exit_persistence.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from features.api.routes.openai.responses.streaming_generator.persistence import (
    build_failed_event_done_chunks,
)
from features.api.routes.openai.responses.streaming_generator.terminal_events import (
    persist_cancelled_response,
)

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from core.runtime.request_context import RequestContext
    from core.types.json import JSONDict
    from features.api.routes.openai.responses.streaming_generator.passthrough_persistence import (
        ResponsesPassthroughPersistence,
    )

__all__ = (
    "flush_response_stream_on_exit",
    "persist_cancellation_on_stream_exit",
    "persist_failure_after_stream_error",
)

OPERATION_OPENAI_RESPONSES_STREAMING_PERSISTENCE = "openai.responses.streaming.persistence"


def _stream_error_details(*, task_id: str, response_id: str) -> JSONDict:
    return {
        "task_id": str(task_id),
        "response_id": response_id,
    }


async def persist_cancellation_on_stream_exit(
    *,
    persistence: ResponsesPassthroughPersistence,
    logger: LoggerProtocol,
    context: RequestContext,
    task_id: str,
) -> None:
    try:
        await uncancel_then_cleanup(persist_cancelled_response(persistence=persistence))
    except RECOVERABLE_EXCEPTIONS as exception:
        coerced = coerce_to_soai_error(
            exception=exception,
            operation=OPERATION_OPENAI_RESPONSES_STREAMING_PERSISTENCE,
            trace_id=context.trace_id,
        )
        log_exception(
            logger,
            coerced,
            message="Failed to persist response cancellation on stream exit.",
            operation=OPERATION_OPENAI_RESPONSES_STREAMING_PERSISTENCE,
            trace_id=context.trace_id,
            details=_stream_error_details(
                task_id=task_id,
                response_id=persistence.recorded_response_id,
            ),
        )


async def persist_failure_after_stream_error(
    *,
    persistence: ResponsesPassthroughPersistence,
    logger: LoggerProtocol,
    context: RequestContext,
    task_id: str,
    done_chunk: bytes,
) -> tuple[bytes, bytes]:
    try:
        failed_chunk = await persistence.emit_failure(
            code="server_error",
            message="Failed to persist response events.",
        )
        await persistence.flush_if_needed(force=True)
        return failed_chunk, done_chunk
    except RECOVERABLE_EXCEPTIONS as exception:
        coerced = coerce_to_soai_error(
            exception,
            operation=OPERATION_OPENAI_RESPONSES_STREAMING_PERSISTENCE,
            trace_id=context.trace_id,
        )
        log_exception(
            logger,
            coerced,
            message="Failed to persist terminal response failure event.",
            operation=OPERATION_OPENAI_RESPONSES_STREAMING_PERSISTENCE,
            trace_id=context.trace_id,
            details=_stream_error_details(
                task_id=task_id,
                response_id=persistence.recorded_response_id,
            ),
        )
        return build_failed_event_done_chunks(
            response_id=persistence.recorded_response_id,
            message="Failed to persist response events.",
            code="server_error",
            model=persistence.storage_target.model,
            created_at=int(persistence.storage_target.created_at),
        )


async def flush_response_stream_on_exit(
    *,
    persistence: ResponsesPassthroughPersistence,
    logger: LoggerProtocol,
    context: RequestContext,
    task_id: str,
) -> None:
    try:
        await uncancel_then_cleanup(persistence.flush_if_needed(force=True))
    except RECOVERABLE_EXCEPTIONS as exception:
        coerced = coerce_to_soai_error(
            exception,
            operation=OPERATION_OPENAI_RESPONSES_STREAMING_PERSISTENCE,
            trace_id=context.trace_id,
        )
        log_exception(
            logger,
            coerced,
            message="Failed to flush response events on stream exit.",
            operation=OPERATION_OPENAI_RESPONSES_STREAMING_PERSISTENCE,
            trace_id=context.trace_id,
            details=_stream_error_details(
                task_id=task_id,
                response_id=persistence.recorded_response_id,
            ),
        )
