"""SoAI - OpenAI Responses background persistence monitor [backend/features/api/routes/openai/responses/background_monitor_runner.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING

from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.exceptions import StateError
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.events.types_base import Event
from core.events.types_models_streaming import (
    InferenceResultEvent,
    StreamChunkEvent,
    StreamEndEvent,
)
from core.events.types_plugins import ErrorEvent
from core.events.types_tasks import TaskCompleteEvent, TaskProgressEvent
from core.logging.trace import get_logger
from core.openai.sse_frame_accumulator import OpenAISSEFrameAccumulator
from core.runtime.request_context import RequestContext
from core.tasks.task_cancellation import cancel
from features.api.routes.openai.responses.background_monitor_event_handlers import (
    handle_stream_chunk_event,
)
from features.api.routes.openai.responses.background_monitor_state import (
    BackgroundResponsesState,
)
from features.api.streaming.stream_dependencies import build_stream_dependencies
from features.api.streaming.stream_iteration import (
    StreamKeepalive,
    StreamTermination,
    iter_classified_stream_events,
)

if TYPE_CHECKING:
    from features.api.runtime.context import ApiContext

__all__ = ("monitor_background_responses_task",)

LOGGER_NAME = "SoAI.features.api.background_monitor_runner"
OPERATION = "openai.responses.background_monitor"


async def _cancel_background_response_task(
    *,
    api_context: ApiContext,
    context: RequestContext,
    state: BackgroundResponsesState,
    reason: str,
) -> None:
    await cancel(
        api_context.dependencies.task_registry,
        state.task_id,
        reason=reason,
        context=context,
    )


async def _reconcile_background_response_task(
    *,
    api_context: ApiContext,
    state: BackgroundResponsesState,
) -> None:
    await api_context.dependencies.database_openai_responses.reconcile_terminal_background_response(
        task_id=state.task_id,
    )


async def _wait_for_background_response_task_terminal(
    *,
    api_context: ApiContext,
    state: BackgroundResponsesState,
) -> None:
    task = await api_context.dependencies.task_registry.wait_for_completion(
        state.task_id,
        timeout=None,
    )
    if task is None or not task.status.is_terminal():
        raise StateError("Background Response task did not reach a terminal state.")


async def _background_response_task_is_terminal(
    *,
    api_context: ApiContext,
    state: BackgroundResponsesState,
) -> bool:
    task = await api_context.dependencies.task_registry.get(
        state.task_id,
        force_refresh=True,
    )
    if task is None:
        raise StateError("Background Response task disappeared before terminal settlement.")
    return task.status.is_terminal()


async def _cancel_and_reconcile_background_response_task(
    *,
    api_context: ApiContext,
    context: RequestContext,
    state: BackgroundResponsesState,
    reason: str,
) -> None:
    await _cancel_background_response_task(
        api_context=api_context,
        context=context,
        state=state,
        reason=reason,
    )
    await _reconcile_background_response_task(api_context=api_context, state=state)


async def _cancel_settle_and_reconcile_background_response_task(
    *,
    api_context: ApiContext,
    context: RequestContext,
    state: BackgroundResponsesState,
    reason: str,
) -> None:
    await _cancel_background_response_task(
        api_context=api_context,
        context=context,
        state=state,
        reason=reason,
    )
    await _wait_for_background_response_task_terminal(api_context=api_context, state=state)
    await _reconcile_background_response_task(api_context=api_context, state=state)


async def monitor_background_responses_task(
    *,
    api_context: ApiContext,
    context: RequestContext,
    reply_queue: asyncio.Queue[Event],
    state: BackgroundResponsesState,
) -> None:
    logger = get_logger(LOGGER_NAME)
    accumulator = OpenAISSEFrameAccumulator()
    stream_dependencies = build_stream_dependencies(api_context.dependencies)
    monitor_started_at = time.monotonic()
    max_duration_sec = api_context.dependencies.config.get_float(
        "API.OPENAI.RESPONSES.BACKGROUND_MONITOR_MAX_SEC",
    )
    try:
        provider_terminal_observed = False
        durable_terminal_observed = False
        cancellation_requested = False
        async for classified in iter_classified_stream_events(
            reply_queue,
            stream_dependencies,
            context,
            publish_cancel_command=False,
            close_on_timeout=False,
        ):
            if isinstance(classified, StreamTermination):
                if not durable_terminal_observed:
                    cancellation_requested = True
                    await _cancel_background_response_task(
                        api_context=api_context,
                        context=context,
                        state=state,
                        reason="Background response stream terminated.",
                    )
                break
            if isinstance(classified, StreamKeepalive):
                if cancellation_requested and await _background_response_task_is_terminal(
                    api_context=api_context,
                    state=state,
                ):
                    durable_terminal_observed = True
                    break
            else:
                event = classified.event
                if isinstance(event, StreamChunkEvent):
                    provider_terminal_observed = await handle_stream_chunk_event(
                        api_context,
                        state,
                        event=event,
                        accumulator=accumulator,
                        response_finalized=provider_terminal_observed,
                    )
                elif isinstance(event, InferenceResultEvent | StreamEndEvent):
                    accumulator.finalize()
                    durable_terminal_observed = True
                elif isinstance(event, TaskCompleteEvent):
                    if event.success:
                        accumulator.finalize()
                    durable_terminal_observed = True
                elif isinstance(event, ErrorEvent):
                    durable_terminal_observed = True
                elif not isinstance(event, TaskProgressEvent):
                    logger.debug(
                        "[%s] Background monitor ignoring event type: %s",
                        context.trace_id,
                        type(event).__name__,
                    )
            elapsed_sec = time.monotonic() - monitor_started_at
            if (
                not durable_terminal_observed
                and not cancellation_requested
                and 0.0 < max_duration_sec < elapsed_sec
            ):
                cancellation_requested = True
                await _cancel_background_response_task(
                    api_context=api_context,
                    context=context,
                    state=state,
                    reason="Background response monitor exceeded maximum duration.",
                )
        if not durable_terminal_observed:
            if not cancellation_requested:
                await _cancel_background_response_task(
                    api_context=api_context,
                    context=context,
                    state=state,
                    reason="Background response stream ended without durable task completion.",
                )
            await _wait_for_background_response_task_terminal(
                api_context=api_context,
                state=state,
            )
        await _reconcile_background_response_task(api_context=api_context, state=state)
    except asyncio.CancelledError:
        await uncancel_then_cleanup(
            _cancel_and_reconcile_background_response_task(
                api_context=api_context,
                context=context,
                state=state,
                reason="Background response monitor was cancelled.",
            )
        )
        raise
    except HANDLED_RUNTIME_EXCEPTIONS as exception:
        coerced = coerce_to_soai_error(
            exception,
            operation="openai.responses.background_monitor",
        )
        log_exception(
            logger,
            coerced,
            message="Background monitor failed.",
            trace_id=context.trace_id,
            operation=OPERATION,
            level="error",
        )
        await _cancel_settle_and_reconcile_background_response_task(
            api_context=api_context,
            context=context,
            state=state,
            reason="Background response monitor failed.",
        )
