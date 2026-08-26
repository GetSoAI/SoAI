"""SoAI - Task-backed reply queue stream iteration [backend/features/api/streaming/reply_queue_stream.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator

from starlette.requests import ClientDisconnect

from core.concurrency.cancellation_cleanup import (
    shielded_cleanup,
    uncancel_then_cleanup,
)
from core.concurrency.task_groups import QueueEventWaiter
from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.exceptions import SoAITimeoutError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.types_base import Event
from core.logging.trace import get_logger
from core.runtime.protocols import RequestContextProtocol
from core.tasks.cancellation import publish_cancel
from core.tasks.task_cancellation import cancel
from features.api.streaming.reply_queue_task_state import (
    reply_queue_inactivity_timeout_is_suspended,
    resolve_reply_queue_terminal_event,
    resolve_reply_queue_timeout_limit,
)
from features.api.streaming.subscriptions import (
    StreamClosedSentinel,
    StreamKeepAliveSentinel,
    StreamShutdownSentinel,
    StreamTimeoutSentinel,
    resolve_task_id_from_sources,
)
from features.api.streaming.types import StreamDependencies

__all__ = ("iter_reply_queue_events",)

LOGGER_NAME = "SoAI.features.api.reply_queue_stream"
OPERATION_API_STREAMING_ITER_REPLY_QUEUE_EVENTS_NOTIFY_CANCEL = (
    "api_streaming.iter_reply_queue_events.notify_cancel"
)


async def iter_reply_queue_events(
    reply_queue: asyncio.Queue[Event],
    stream_dependencies: StreamDependencies,
    context: RequestContextProtocol | None,
    *,
    publish_cancel_command: bool,
    close_on_timeout: bool,
) -> AsyncGenerator[
    Event
    | type[StreamTimeoutSentinel]
    | type[StreamKeepAliveSentinel]
    | type[StreamClosedSentinel]
    | type[StreamShutdownSentinel]
]:
    logger = get_logger(LOGGER_NAME)
    trace_id = context.trace_id if context else "no-context"
    inactivity_timeout = stream_dependencies.config.get_float(
        "SERVER.HTTP.STREAMING.STREAM_INACTIVITY_TIMEOUT_SEC",
    )
    cancel_on_client_disconnect = stream_dependencies.config.get_bool(
        "MODELS.ROUTING.CANCEL_ON_CLIENT_DISCONNECT",
    )
    ping_interval = min(30.0, max(0.1, inactivity_timeout))
    resolved_bus = stream_dependencies.event_bus
    task_registry = stream_dependencies.task_registry
    cancellation_coordinator = stream_dependencies.cancellation_coordinator
    cancellation_history = stream_dependencies.cancellation_history

    async def notify_cancel(reason: str) -> None:
        if not publish_cancel_command:
            return
        task_id: str | None = None
        if context is not None:
            try:
                task_id = context.task_id
            except AttributeError:
                task_id = None
            if isinstance(task_id, str) and task_id:
                try:
                    task = await task_registry.get(task_id, force_refresh=True)
                except RECOVERABLE_EXCEPTIONS as exception:
                    log_handled_exception(
                        logger,
                        exception,
                        message="Failed to fetch task during cancel notification (non-critical).",
                        trace_id=trace_id,
                        operation=OPERATION_API_STREAMING_ITER_REPLY_QUEUE_EVENTS_NOTIFY_CANCEL,
                        level="debug",
                    )
                    task = None
                if task is not None and task.status.is_terminal():
                    return
        if isinstance(task_id, str) and task_id:
            try:
                await cancel(task_registry, task_id, reason=reason, context=context)
            except RECOVERABLE_EXCEPTIONS as cancel_error:
                log_exception(
                    logger,
                    cancel_error,
                    message="Failed to cancel task via registry.",
                    trace_id=trace_id,
                    operation=OPERATION_API_STREAMING_ITER_REPLY_QUEUE_EVENTS_NOTIFY_CANCEL,
                    level="warning",
                )
            return
        try:
            await publish_cancel(
                resolved_bus,
                cancellation_coordinator,
                cancellation_history,
                context,
                reason,
            )
        except RECOVERABLE_EXCEPTIONS as cancel_error:
            log_exception(
                logger,
                cancel_error,
                message="Failed to publish cancel command.",
                trace_id=trace_id,
                operation=OPERATION_API_STREAMING_ITER_REPLY_QUEUE_EVENTS_NOTIFY_CANCEL,
                level="warning",
            )

    channel_task_id = resolve_task_id_from_sources(
        context,
        reply_queue,
        task_registry=task_registry,
    )

    subscription = await stream_dependencies.acquire_stream_subscription(
        reply_queue,
        task_id=channel_task_id,
    )
    listener_queue = subscription.queue
    waiter = QueueEventWaiter(listener_queue, stream_dependencies.shutdown_event)
    idle_for = 0.0
    try:
        while True:
            try:
                event = await waiter.wait(timeout=ping_interval)
            except (SoAITimeoutError, TimeoutError):
                if close_on_timeout:
                    idle_for += ping_interval
                    if idle_for >= inactivity_timeout:
                        terminal_event = await resolve_reply_queue_terminal_event(
                            task_registry=task_registry,
                            context=context,
                            reply_queue=reply_queue,
                            logger=logger,
                            trace_id=trace_id,
                        )
                        if terminal_event is not None:
                            yield terminal_event
                            break
                        if await reply_queue_inactivity_timeout_is_suspended(
                            task_registry=task_registry,
                            task_id=channel_task_id,
                            logger=logger,
                            trace_id=trace_id,
                        ):
                            idle_for = 0.0
                            yield StreamKeepAliveSentinel
                            continue
                        timeout_limit = await resolve_reply_queue_timeout_limit(
                            task_registry=task_registry,
                            config=stream_dependencies.config,
                            task_id=channel_task_id,
                            inactivity_timeout=inactivity_timeout,
                            logger=logger,
                            trace_id=trace_id,
                        )
                        if idle_for < timeout_limit:
                            yield StreamKeepAliveSentinel
                            continue
                        yield StreamTimeoutSentinel
                        break
                yield StreamKeepAliveSentinel
                continue
            if event is None:
                if stream_dependencies.shutdown_event.is_set():
                    yield StreamShutdownSentinel
                else:
                    terminal_event = await resolve_reply_queue_terminal_event(
                        task_registry=task_registry,
                        context=context,
                        reply_queue=reply_queue,
                        logger=logger,
                        trace_id=trace_id,
                    )
                    if terminal_event is not None:
                        yield terminal_event
                    else:
                        yield StreamClosedSentinel
                break
            idle_for = 0.0
            yield event
    except asyncio.CancelledError:
        if cancel_on_client_disconnect:
            await shielded_cleanup(notify_cancel("Client disconnected."))
        raise
    except ClientDisconnect:
        if cancel_on_client_disconnect:
            await notify_cancel("Client disconnected.")
    finally:
        await uncancel_then_cleanup(waiter.cancel())
        await uncancel_then_cleanup(subscription.close())
        logger.trace("[%s] Reply queue stream iterator finished.", trace_id)
