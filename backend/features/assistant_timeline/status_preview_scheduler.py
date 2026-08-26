"""SoAI - Assistant timeline live status preview scheduler [backend/features/assistant_timeline/status_preview_scheduler.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from core.concurrency.ephemeral_tasks import create_ephemeral_task
from core.concurrency.task_groups import cancel_and_await
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import SoAIError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.timing.monotonic import monotonic_ms
from features.assistant_timeline.models import (
    AssistantTimelineRuntime,
    StatusPreviewRequest,
    StatusPreviewResult,
)
from features.assistant_timeline.publish import ensure_chat_stream_publish_lock
from features.assistant_timeline.status_preview_publication import (
    publish_status_preview_result,
)
from features.assistant_timeline.status_preview_state import (
    build_status_preview_request,
    resolve_status_preview_next_due_ms,
    resolve_status_preview_trigger,
)

if TYPE_CHECKING:
    from core.events.protocols import EventBusProtocol

__all__ = (
    "start_status_preview_scheduler",
    "wake_status_preview_scheduler",
)

SLEEP_ZERO_SECONDS = 0.0
LOGGER_NAME = "SoAI.features.assistant_timeline.status_preview_scheduler"
OPERATION_PREVIEW_REQUEST = "assistant_timeline.status_preview.request"
STATUS_PREVIEW_FAILURE_EXCEPTIONS: tuple[type[Exception], ...] = (
    SoAIError,
    *RECOVERABLE_EXCEPTIONS,
)


def wake_status_preview_scheduler(runtime: AssistantTimelineRuntime) -> None:
    wake_event = runtime.status_preview_wake_event
    if wake_event is None:
        wake_event = asyncio.Event()
        runtime.status_preview_wake_event = wake_event
    wake_event.set()


def start_status_preview_scheduler(
    *,
    runtime: AssistantTimelineRuntime,
    event_bus: EventBusProtocol,
    track_background_task: Callable[[asyncio.Task[None]], None],
    preview_executor: (
        Callable[[StatusPreviewRequest], Awaitable[StatusPreviewResult | None]] | None
    ),
) -> asyncio.Task[None] | None:
    if preview_executor is None:
        return None

    async def scheduler() -> None:
        wake_event = runtime.status_preview_wake_event
        if wake_event is None:
            wake_event = asyncio.Event()
            runtime.status_preview_wake_event = wake_event
        cancelled = False
        try:
            while runtime.detach_event is None or not runtime.detach_event.is_set():
                trigger = await _wait_for_status_preview_due(
                    runtime=runtime,
                    wake_event=wake_event,
                )
                if trigger is None:
                    break
                preview_request = await _start_status_preview_request(
                    runtime=runtime,
                    trigger=trigger,
                )
                if preview_request is None:
                    continue
                request, preview_generation = preview_request
                preview_result = await _run_status_preview_request(
                    runtime=runtime,
                    track_background_task=track_background_task,
                    preview_executor=preview_executor,
                    request=request,
                )
                await publish_status_preview_result(
                    runtime=runtime,
                    event_bus=event_bus,
                    trigger=trigger,
                    preview_result=preview_result,
                    preview_generation=preview_generation,
                )
        except asyncio.CancelledError:
            cancelled = True
        finally:
            active_task = runtime.status_preview_active_request_task
            runtime.status_preview_active_request_task = None
            if active_task is not None and not active_task.done():
                active_task.cancel()
                await cancel_and_await((active_task,), task_label="status preview request task")
                if not active_task.cancelled():
                    exception = active_task.exception()
                    if exception is not None:
                        raise exception
        if cancelled:
            raise asyncio.CancelledError

    task = create_ephemeral_task(
        scheduler(),
        name=f"ws-chat-status-preview-{runtime.conv_id}",
    )
    track_background_task(task)
    return task


async def _wait_for_status_preview_due(
    *,
    runtime: AssistantTimelineRuntime,
    wake_event: asyncio.Event,
) -> str | None:
    while runtime.detach_event is None or not runtime.detach_event.is_set():
        if wake_event.is_set():
            wake_event.clear()
        lock = ensure_chat_stream_publish_lock(runtime)
        async with lock:
            if runtime.terminal_event_emitted or runtime.terminal_finalization_started:
                return None
            now_ms = monotonic_ms()
            trigger = resolve_status_preview_trigger(runtime=runtime, now_ms=now_ms)
            if trigger is not None:
                return trigger
            wait_ms = resolve_status_preview_next_due_ms(runtime=runtime, now_ms=now_ms)
        if wait_ms <= 0:
            await asyncio.sleep(SLEEP_ZERO_SECONDS)
            continue
        try:
            await asyncio.wait_for(wake_event.wait(), timeout=wait_ms / 1000)
        except TimeoutError:
            continue
        wake_event.clear()
    return None


async def _start_status_preview_request(
    *,
    runtime: AssistantTimelineRuntime,
    trigger: str,
) -> tuple[StatusPreviewRequest, int] | None:
    lock = ensure_chat_stream_publish_lock(runtime)
    async with lock:
        if runtime.terminal_event_emitted or runtime.terminal_finalization_started:
            return None
        now_ms = monotonic_ms()
        current_trigger = resolve_status_preview_trigger(runtime=runtime, now_ms=now_ms)
        if current_trigger != trigger:
            return None
        request = build_status_preview_request(runtime=runtime)
        if request is None:
            if trigger == "tool_call_completed":
                runtime.status_preview_pending_refresh = False
            return None
        runtime.status_preview_last_started_monotonic_ms = now_ms
        if trigger == "tool_call_completed":
            runtime.status_preview_pending_refresh = False
        return (request, runtime.status_preview_generation)


async def _run_status_preview_request(
    *,
    runtime: AssistantTimelineRuntime,
    track_background_task: Callable[[asyncio.Task[None]], None],
    preview_executor: Callable[[StatusPreviewRequest], Awaitable[StatusPreviewResult | None]],
    request: StatusPreviewRequest,
) -> StatusPreviewResult | None:
    result: StatusPreviewResult | None = None

    async def run_preview_request() -> None:
        nonlocal result
        try:
            result = await preview_executor(request)
        except STATUS_PREVIEW_FAILURE_EXCEPTIONS as exception:
            coerced = coerce_to_soai_error(
                exception,
                operation=OPERATION_PREVIEW_REQUEST,
            )
            log_handled_exception(
                get_logger(LOGGER_NAME),
                coerced,
                message="Status preview request failed (non-critical).",
                operation=OPERATION_PREVIEW_REQUEST,
                level="debug",
                details={"conv_id": runtime.conv_id, "request_id": runtime.request_id},
            )
            result = None

    active_task = create_ephemeral_task(
        run_preview_request(),
        name=f"ws-chat-status-preview-request-{runtime.conv_id}",
    )
    track_background_task(active_task)
    runtime.status_preview_active_request_task = active_task
    try:
        await active_task
        return result
    finally:
        if runtime.status_preview_active_request_task is active_task:
            runtime.status_preview_active_request_task = None
