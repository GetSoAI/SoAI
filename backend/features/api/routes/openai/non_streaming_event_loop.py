"""SoAI - Shared non-streaming inference event loop runner [backend/features/api/routes/openai/non_streaming_event_loop.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.concurrency.task_groups import QueueEventWaiter
from core.errors.exceptions import StateError
from core.events.non_streaming_hard_deadline import (
    ProgressEventHandler,
    TerminalEventHandler,
    run_inactivity_timeout_event_loop,
)
from core.events.types_base import Event
from core.events.types_models_streaming import (
    InferenceResultEvent,
    StreamChunkEvent,
    StreamEndEvent,
)
from core.events.types_plugins import ErrorEvent
from core.events.types_tasks import TaskCompleteEvent, TaskProgressEvent
from core.runtime.protocols import RequestProtocol
from features.api.routes.openai.non_streaming_event_wait import (
    wait_for_non_streaming_event,
)
from features.api.runtime.errors import raise_service_unavailable
from features.api.streaming.types import StreamDependencies

if TYPE_CHECKING:
    type StreamChunkHandler = Callable[[StreamChunkEvent], Awaitable[None]]
    type UnknownEventHandler = Callable[[Event], Awaitable[None]]

__all__ = ("run_non_streaming_event_loop",)


async def run_non_streaming_event_loop[ResultT](
    *,
    request: RequestProtocol | None,
    stream_dependencies: StreamDependencies,
    reply_queue: asyncio.Queue[Event] | None = None,
    listener_queue: asyncio.Queue[Event | None] | None = None,
    task_id: str,
    timeout: float,
    on_inference_result: Callable[[InferenceResultEvent], Awaitable[ResultT]],
    on_stream_chunk: StreamChunkHandler,
    on_stream_end: Callable[[StreamEndEvent], Awaitable[ResultT]],
    on_task_complete: Callable[[TaskCompleteEvent], Awaitable[ResultT]],
    on_error_event: Callable[[ErrorEvent], Awaitable[ResultT]] | None = None,
    on_closed_queue: Callable[[], Awaitable[ResultT]] | None = None,
    on_unknown_event: UnknownEventHandler | None = None,
    timeout_message: str = (
        "Timed out waiting for non-streaming task result without new task events."
    ),
    timeout_operation: str = "api_openai.non_streaming_event_loop",
) -> ResultT:
    subscription = None
    if listener_queue is None:
        if request is None or reply_queue is None:
            raise StateError("Non-streaming event loop requires a request and reply queue.")
        subscription = await stream_dependencies.acquire_stream_subscription(
            reply_queue,
            task_id=task_id,
        )
        if subscription is None:
            raise_service_unavailable(request, "Task stream unavailable.")
        listener_queue = subscription.queue
    waiter: QueueEventWaiter[Event | None] = QueueEventWaiter(
        listener_queue,
        stream_dependencies.shutdown_event,
    )

    async def _handle_inference_result_event(event: Event | None) -> ResultT:
        if not isinstance(event, InferenceResultEvent):
            raise StateError("Expected InferenceResultEvent.")
        return await on_inference_result(event)

    async def _handle_stream_end_event(event: Event | None) -> ResultT:
        if not isinstance(event, StreamEndEvent):
            raise StateError("Expected StreamEndEvent.")
        return await on_stream_end(event)

    async def _handle_task_complete_event(event: Event | None) -> ResultT:
        if not isinstance(event, TaskCompleteEvent):
            raise StateError("Expected TaskCompleteEvent.")
        return await on_task_complete(event)

    async def _handle_stream_chunk_event(event: Event | None) -> None:
        if not isinstance(event, StreamChunkEvent):
            raise StateError("Expected StreamChunkEvent.")
        await on_stream_chunk(event)

    async def _handle_unknown_event(event: Event | None) -> None:
        if event is None or on_unknown_event is None:
            return
        await on_unknown_event(event)

    async def _handle_error_event(event: Event | None) -> ResultT:
        if not isinstance(event, ErrorEvent):
            raise StateError("Expected ErrorEvent.")
        if on_error_event is None:
            return await _handle_unknown_terminal_event(event)
        return await on_error_event(event)

    async def _handle_closed_queue(event: Event | None) -> ResultT:
        if event is not None:
            raise StateError("Expected closed non-streaming queue.")
        if on_closed_queue is None:
            if request is None:
                raise StateError("Non-streaming task stream closed before completion.")
            raise_service_unavailable(request, "Task stream closed before completion.")
        return await on_closed_queue()

    async def _handle_unknown_terminal_event(event: Event | None) -> ResultT:
        if event is not None:
            await _handle_unknown_event(event)
        raise StateError("Non-streaming task ended without a terminal result.")

    terminal_handlers: tuple[TerminalEventHandler[Event | None, ResultT], ...] = (
        TerminalEventHandler(
            matches=lambda event: event is None,
            handler=_handle_closed_queue,
        ),
        TerminalEventHandler(
            matches=lambda event: isinstance(event, ErrorEvent),
            handler=_handle_error_event,
        ),
        TerminalEventHandler(
            matches=lambda event: isinstance(event, InferenceResultEvent),
            handler=_handle_inference_result_event,
        ),
        TerminalEventHandler(
            matches=lambda event: isinstance(event, StreamEndEvent),
            handler=_handle_stream_end_event,
        ),
        TerminalEventHandler(
            matches=lambda event: isinstance(event, TaskCompleteEvent),
            handler=_handle_task_complete_event,
        ),
    )
    progress_handlers: tuple[ProgressEventHandler[Event | None], ...] = (
        ProgressEventHandler(
            matches=lambda event: isinstance(event, StreamChunkEvent),
            handler=_handle_stream_chunk_event,
        ),
        ProgressEventHandler(
            matches=lambda event: isinstance(event, TaskProgressEvent),
            handler=lambda _event: _noop_progress_handler(),
        ),
    )

    next_event: Callable[[float], Awaitable[Event | None]]
    if request is None:
        next_event = waiter.wait
    else:

        async def wait_for_request_event(remaining: float) -> Event | None:
            return await wait_for_non_streaming_event(
                request=request,
                stream_dependencies=stream_dependencies,
                waiter=waiter,
                timeout=remaining,
            )

        next_event = wait_for_request_event

    return await run_inactivity_timeout_event_loop(
        inactivity_timeout_seconds=timeout,
        next_event=next_event,
        terminal_handlers=terminal_handlers,
        progress_handlers=progress_handlers,
        unknown_event_handler=_handle_unknown_event,
        cleanup_callbacks=(
            lambda: uncancel_then_cleanup(waiter.cancel()),
            *(
                (lambda: uncancel_then_cleanup(subscription.close()),)
                if subscription is not None
                else ()
            ),
        ),
        timeout_message=timeout_message,
        timeout_operation=timeout_operation,
    )


async def _noop_progress_handler() -> None:
    return None
