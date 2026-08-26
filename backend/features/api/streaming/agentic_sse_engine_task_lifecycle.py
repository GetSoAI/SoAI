"""SoAI - Agentic SSE engine task lifecycle ownership [backend/features/api/streaming/agentic_sse_engine_task_lifecycle.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import TYPE_CHECKING

from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.exceptions import SoAIError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.errors.unexpected_exceptions import UNEXPECTED_RUNTIME_EXCEPTIONS

if TYPE_CHECKING:
    from core.logging.protocols import TraceLogger

__all__ = (
    "attach_engine_task_completion_signal",
    "settle_engine_task_after_stream_exit",
)

_OPERATION_CANCEL_ENGINE = "api_openai.agentic_stream.cancel_engine"
_OPERATION_DETACHED_ENGINE_OBSERVER = "api_openai.agentic_stream.detached_engine_observer"
_ENGINE_TASK_EXCEPTIONS: tuple[type[Exception], ...] = (
    *RECOVERABLE_EXCEPTIONS,
    SoAIError,
    *UNEXPECTED_RUNTIME_EXCEPTIONS,
)


def attach_engine_task_completion_signal(
    engine_task: asyncio.Task[None],
    stream_stop_event: asyncio.Event,
) -> None:
    def notify_stream_stop(_task: asyncio.Task[None]) -> None:
        stream_stop_event.set()

    engine_task.add_done_callback(notify_stream_stop)


def _log_engine_task_exception(
    *,
    logger: TraceLogger,
    trace_id: str,
    operation: str,
    exception: Exception,
    recoverable_message: str,
    unexpected_message: str,
) -> None:
    if isinstance(exception, RECOVERABLE_EXCEPTIONS):
        log_handled_exception(
            logger,
            coerce_to_soai_error(exception, operation=operation),
            message=recoverable_message,
            trace_id=trace_id,
            operation=operation,
            level="debug",
        )
        return
    if isinstance(exception, SoAIError):
        log_handled_exception(
            logger,
            exception,
            message=recoverable_message,
            trace_id=trace_id,
            operation=operation,
            level="debug",
        )
        return
    if isinstance(exception, UNEXPECTED_RUNTIME_EXCEPTIONS):
        coerced = coerce_to_soai_error(exception, operation=operation)
        log_exception(
            logger,
            coerced,
            message=unexpected_message,
            trace_id=trace_id,
            operation=operation,
            level="warning",
        )
        return


async def _await_engine_task_result(
    *,
    engine_task: asyncio.Task[None],
    logger: TraceLogger,
    trace_id: str,
    cancelled_message: str,
    recoverable_message: str,
    unexpected_message: str,
) -> None:
    try:
        await engine_task
    except asyncio.CancelledError:
        logger.debug(cancelled_message)
    except _ENGINE_TASK_EXCEPTIONS as exception:
        _log_engine_task_exception(
            logger=logger,
            trace_id=trace_id,
            operation=_OPERATION_CANCEL_ENGINE,
            exception=exception,
            recoverable_message=recoverable_message,
            unexpected_message=unexpected_message,
        )


def _build_detached_engine_result_observer(
    *,
    logger: TraceLogger,
    trace_id: str,
) -> Callable[[asyncio.Task[None]], None]:
    def observe_detached_engine_result(detached_task: asyncio.Task[None]) -> None:
        try:
            detached_task.result()
        except asyncio.CancelledError:
            logger.debug("Detached agentic stream engine task was cancelled.")
        except _ENGINE_TASK_EXCEPTIONS as exception:
            _log_engine_task_exception(
                logger=logger,
                trace_id=trace_id,
                operation=_OPERATION_DETACHED_ENGINE_OBSERVER,
                exception=exception,
                recoverable_message=(
                    "Detached agentic stream engine task raised after stream detachment "
                    "(non-critical)."
                ),
                unexpected_message=(
                    "Detached agentic stream engine task raised unexpectedly after stream "
                    "detachment."
                ),
            )

    return observe_detached_engine_result


async def settle_engine_task_after_stream_exit(
    *,
    engine_task: asyncio.Task[None],
    detach_event: asyncio.Event,
    stream_stop_event: asyncio.Event,
    cancel_engine_on_detach: bool,
    stream_completed: bool,
    logger: TraceLogger,
    trace_id: str,
) -> None:
    detached_result_observer = _build_detached_engine_result_observer(
        logger=logger,
        trace_id=trace_id,
    )
    detach_event.set()
    stream_stop_event.set()
    if cancel_engine_on_detach and not engine_task.done():
        engine_task.cancel()
        await _await_engine_task_result(
            engine_task=engine_task,
            logger=logger,
            trace_id=trace_id,
            cancelled_message="Agentic stream engine task cancelled during stream detach.",
            recoverable_message="Engine task raised while handling stream detach (non-critical).",
            unexpected_message="Engine task raised unexpectedly while handling stream detach.",
        )
        return
    if stream_completed:
        await _await_engine_task_result(
            engine_task=engine_task,
            logger=logger,
            trace_id=trace_id,
            cancelled_message="Agentic stream engine task cancelled after stream completion.",
            recoverable_message="Engine task raised after stream completion (non-critical).",
            unexpected_message="Engine task raised unexpectedly after stream completion.",
        )
        return
    if engine_task.done():
        detached_result_observer(engine_task)
        return
    engine_task.add_done_callback(detached_result_observer)
