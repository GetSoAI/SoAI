"""SoAI - Binary stream event preparation and iteration [backend/features/api/streaming/openai_stream_binary_request_stream.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import override

from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.errors.status_mapping import error_type_to_status_code
from core.events.types_base import Event
from core.events.types_models_streaming import (
    InferenceResultEvent,
    StreamChunkEvent,
    StreamEndEvent,
)
from core.events.types_plugins import ErrorEvent
from core.events.types_tasks import TaskCompleteEvent, TaskProgressEvent
from core.logging.trace import get_logger
from core.runtime.request_context import RequestContext
from core.tasks.enums import TaskStatus
from features.api.streaming.openai_stream_binary_support import normalize_binary_chunk
from features.api.streaming.stream_iteration import (
    StreamEvent,
    StreamKeepalive,
    StreamTermination,
    StreamTerminationReason,
    iter_classified_stream_events,
)
from features.api.streaming.types import StreamDependencies

__all__ = (
    "BinaryStreamPreparation",
    "BinaryStreamRuntimeFailure",
    "prepare_binary_stream_payload",
)

LOGGER_NAME = "SoAI.features.api.openai_stream_binary_request_stream"
OPERATION = "api_streaming.prepare_binary_stream_payload"


_EMPTY_BINARY_CHUNKS: tuple[bytes, ...] = ()


@dataclass(frozen=True, slots=True)
class BinaryStreamPreparation:
    stream: AsyncGenerator[bytes] | None
    status_code: int | None = None
    error_message: str | None = None
    error_type: str | None = None


class BinaryStreamRuntimeFailure(Exception):
    def __init__(self, message: str, error_type: str) -> None:
        super().__init__(message)
        self.message = message
        self.error_type = error_type

    @override
    def __str__(self) -> str:
        return self.message

    def __getnewargs_ex__(self) -> tuple[tuple[str, str], dict[str, str]]:
        return ((self.message, self.error_type), {})


def _build_binary_stream_error(
    status_code: int,
    message: str,
    error_type: str,
) -> BinaryStreamPreparation:
    return BinaryStreamPreparation(
        stream=None,
        status_code=status_code,
        error_message=message,
        error_type=error_type,
    )


def _resolve_termination_error(
    termination: StreamTermination,
) -> BinaryStreamPreparation:
    if termination.reason == StreamTerminationReason.TIMEOUT:
        return _build_binary_stream_error(504, "Stream timed out.", "timeout_error")
    if termination.reason == StreamTerminationReason.SHUTDOWN:
        return _build_binary_stream_error(503, "SoAI API Server is shutting down.", "server_error")
    return _build_binary_stream_error(500, termination.message or "Stream closed.", "server_error")


def _build_binary_contract_violation(
    *,
    event_name: str,
    trace_id: str | None,
) -> BinaryStreamPreparation:
    _log_binary_contract_violation(event_name=event_name, trace_id=trace_id)
    return _build_binary_stream_error(500, "Binary stream contract violation.", "server_error")


def _log_binary_contract_violation(*, event_name: str, trace_id: str | None) -> None:
    logger = get_logger(LOGGER_NAME)
    logger.error(
        "[%s] Binary stream received unsupported terminal event: %s",
        trace_id,
        event_name,
    )


def _raise_binary_contract_violation(*, event_name: str, trace_id: str | None) -> None:
    _log_binary_contract_violation(event_name=event_name, trace_id=trace_id)
    raise BinaryStreamRuntimeFailure("Binary stream contract violation.", "server_error")


async def _iter_empty_binary_stream() -> AsyncGenerator[bytes]:
    for chunk in _EMPTY_BINARY_CHUNKS:
        yield chunk


async def _iter_binary_stream_chunks(
    classified_iter: AsyncGenerator[StreamKeepalive | StreamTermination | StreamEvent[Event]],
    *,
    first_chunk: bytes,
    trace_id: str | None,
) -> AsyncGenerator[bytes]:
    logger = get_logger(LOGGER_NAME)
    try:
        yield first_chunk
        async for classified in classified_iter:
            if isinstance(classified, StreamKeepalive):
                continue
            if isinstance(classified, StreamTermination):
                message = classified.message or "Stream closed."
                error_type = classified.error_code or "server_error"
                logger.warning("[%s] Binary stream terminated: %s", trace_id, message)
                raise BinaryStreamRuntimeFailure(message, error_type)
            event = classified.event
            if isinstance(event, StreamChunkEvent):
                chunk_bytes = normalize_binary_chunk(event.chunk)
                if chunk_bytes is None:
                    message = f"Unsupported binary stream chunk type: {type(event.chunk).__name__}"
                    logger.warning("[%s] %s", trace_id, message)
                    raise BinaryStreamRuntimeFailure(message, "server_error")
                yield chunk_bytes
                continue
            if isinstance(event, StreamEndEvent):
                break
            if isinstance(event, InferenceResultEvent):
                _raise_binary_contract_violation(
                    event_name=type(event).__name__,
                    trace_id=trace_id,
                )
            if isinstance(event, ErrorEvent):
                message = event.message or "Binary stream failed."
                logger.warning("[%s] Binary stream error: %s", trace_id, message)
                raise BinaryStreamRuntimeFailure(message, event.error_type.value)
            if isinstance(event, TaskCompleteEvent):
                if not event.success:
                    cancelled = event.status == TaskStatus.CANCELLED.value
                    message = (
                        "Request cancelled."
                        if cancelled
                        else event.error_message or event.message or "Binary stream failed."
                    )
                    logger.warning("[%s] Binary stream task failed: %s", trace_id, message)
                    raise BinaryStreamRuntimeFailure(
                        message,
                        "cancelled" if cancelled else event.error_type or "server_error",
                    )
                break
            if isinstance(event, TaskProgressEvent):
                continue
            logger.debug(
                "[%s] Binary stream ignoring event type: %s",
                trace_id,
                type(event).__name__,
            )
    finally:
        await classified_iter.aclose()


async def prepare_binary_stream_payload(
    reply_queue: asyncio.Queue[Event],
    stream_dependencies: StreamDependencies,
    context: RequestContext,
    *,
    trace_id: str | None = None,
) -> BinaryStreamPreparation:
    logger = get_logger(LOGGER_NAME)
    classified_iter = iter_classified_stream_events(
        reply_queue,
        stream_dependencies,
        context,
        publish_cancel_command=True,
        close_on_timeout=True,
    )
    try:
        async for classified in classified_iter:
            if isinstance(classified, StreamKeepalive):
                continue
            if isinstance(classified, StreamTermination):
                await classified_iter.aclose()
                return _resolve_termination_error(classified)
            event = classified.event
            if isinstance(event, StreamChunkEvent):
                chunk_bytes = normalize_binary_chunk(event.chunk)
                if chunk_bytes is None:
                    message = f"Unsupported binary stream chunk type: {type(event.chunk).__name__}"
                    logger.warning("[%s] %s", trace_id, message)
                    await classified_iter.aclose()
                    return _build_binary_stream_error(500, message, "server_error")
                return BinaryStreamPreparation(
                    stream=_iter_binary_stream_chunks(
                        classified_iter,
                        first_chunk=chunk_bytes,
                        trace_id=trace_id,
                    ),
                )
            if isinstance(event, StreamEndEvent):
                await classified_iter.aclose()
                return BinaryStreamPreparation(stream=_iter_empty_binary_stream())
            if isinstance(event, InferenceResultEvent):
                await classified_iter.aclose()
                return _build_binary_contract_violation(
                    event_name=type(event).__name__,
                    trace_id=trace_id,
                )
            if isinstance(event, ErrorEvent):
                await classified_iter.aclose()
                return _build_binary_stream_error(
                    error_type_to_status_code(event.error_type),
                    event.message or "Binary stream failed.",
                    event.error_type.value,
                )
            if isinstance(event, TaskCompleteEvent):
                await classified_iter.aclose()
                if event.success:
                    return BinaryStreamPreparation(stream=_iter_empty_binary_stream())
                if event.status == TaskStatus.CANCELLED.value:
                    return _build_binary_stream_error(
                        499,
                        "Request cancelled.",
                        "cancelled",
                    )
                return _build_binary_stream_error(
                    event.error_code or 500,
                    event.error_message or event.message or "Binary stream failed.",
                    event.error_type or "server_error",
                )
            if isinstance(event, TaskProgressEvent):
                continue
            logger.debug(
                "[%s] Binary stream ignoring event type: %s",
                trace_id,
                type(event).__name__,
            )
        await classified_iter.aclose()
        return _build_binary_stream_error(500, "Stream closed.", "server_error")
    except RECOVERABLE_EXCEPTIONS as exception:
        await classified_iter.aclose()
        log_exception(
            logger,
            exception,
            message="Unhandled error while preparing binary stream payload.",
            trace_id=trace_id,
            operation=OPERATION,
        )
        return _build_binary_stream_error(500, "Internal server error.", "server_error")
