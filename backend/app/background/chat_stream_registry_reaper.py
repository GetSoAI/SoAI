"""SoAI - Active chat stream registry stale runtime reaper [backend/app/background/chat_stream_registry_reaper.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

from app.types_application import ApplicationContext
from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.tasks.cancellation import publish_cancel
from core.timing.constants import BACKGROUND_TIMEOUT_SEC, LOCAL_IO_TIMEOUT_SEC
from core.timing.monotonic import monotonic_ms
from features.assistant_timeline.models import AssistantTimelineRuntime
from features.chat.conversation_stream_cancellation import (
    mark_conversation_stream_runtime_cancellation_requested,
)

__all__ = ("run_chat_stream_registry_reaper",)

LOGGER_NAME = "SoAI.app.background.chat_stream_registry_reaper"
OPERATION_CANCEL_STALE = "chat_stream_registry_reaper.cancel_stale_runtime"
OPERATION_REMOVE_DONE = "chat_stream_registry_reaper.remove_done_runtime"
DEFAULT_STALE_THRESHOLD_SEC: float = 600.0
MIN_REAPER_INTERVAL_SEC_CONST = LOCAL_IO_TIMEOUT_SEC
MAX_REAPER_INTERVAL_SEC_CONST = BACKGROUND_TIMEOUT_SEC


def _resolve_stale_threshold_sec(application_context: ApplicationContext) -> float:
    stream_timeout_sec = application_context.services.configuration.config.get_float(
        "SERVER.HTTP.STREAMING.STREAM_INACTIVITY_TIMEOUT_SEC",
    )
    return max(DEFAULT_STALE_THRESHOLD_SEC, stream_timeout_sec * 2.0)


def _resolve_reaper_interval_sec(stale_threshold_sec: float) -> float:
    return min(
        MAX_REAPER_INTERVAL_SEC_CONST,
        max(MIN_REAPER_INTERVAL_SEC_CONST, stale_threshold_sec / 4.0),
    )


def _runtime_is_stale(
    runtime: AssistantTimelineRuntime,
    *,
    now_ms: int,
    stale_threshold_ms: int,
) -> bool:
    if runtime.terminal_persistence_completed:
        return False
    return now_ms - runtime.last_visible_activity_monotonic_ms > stale_threshold_ms


async def _cancel_stale_runtime(
    application_context: ApplicationContext,
    runtime: AssistantTimelineRuntime,
    reason: str,
) -> None:
    logger = application_context.logging.logger
    mark_conversation_stream_runtime_cancellation_requested(runtime, reason)
    try:
        await publish_cancel(
            application_context.services.infrastructure.event_bus,
            application_context.services.tasks.cancellation.coordinator,
            application_context.services.tasks.cancellation.history,
            None,
            reason,
            cancellation_id=runtime.task_cancellation_id,
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message="Failed to publish stale chat stream runtime cancellation.",
            operation=OPERATION_CANCEL_STALE,
            details={"conv_id": runtime.conv_id, "request_id": runtime.request_id},
            level="warning",
        )
    runner_task = runtime.runner_task
    if runner_task is not None and not runner_task.done():
        runner_task.cancel()


async def _scan_chat_stream_registry(
    application_context: ApplicationContext,
    *,
    stale_threshold_ms: int,
) -> None:
    logger = application_context.logging.logger
    now_ms = monotonic_ms()
    registry = application_context.api_runtime_singletons.chat_stream_registry
    for runtime in await registry.snapshot_active():
        runner_task = runtime.runner_task
        if (
            runner_task is not None
            and runner_task.done()
            and not runtime.terminal_persistence_completed
        ):
            logger.critical(
                "Removing completed chat stream runner left in registry. conv_id=%s request_id=%s",
                runtime.conv_id,
                runtime.request_id,
            )
            try:
                await registry.remove_if_same(runtime)
            except RECOVERABLE_EXCEPTIONS as exception:
                log_exception(
                    logger,
                    exception,
                    message="Failed to remove completed chat stream runtime from registry.",
                    operation=OPERATION_REMOVE_DONE,
                    details={"conv_id": runtime.conv_id, "request_id": runtime.request_id},
                    level="warning",
                )
            continue
        if not _runtime_is_stale(runtime, now_ms=now_ms, stale_threshold_ms=stale_threshold_ms):
            continue
        await _cancel_stale_runtime(
            application_context,
            runtime,
            "Chat stream registry reaper cancelled a stale runtime.",
        )


async def run_chat_stream_registry_reaper(application_context: ApplicationContext) -> None:
    stale_threshold_sec = _resolve_stale_threshold_sec(application_context)
    stale_threshold_ms = int(stale_threshold_sec * 1000.0)
    interval_sec = _resolve_reaper_interval_sec(stale_threshold_sec)
    shutdown_event = application_context.runtime.shutdown_event
    while not shutdown_event.is_set():
        try:
            await asyncio.wait_for(shutdown_event.wait(), timeout=interval_sec)
        except TimeoutError:
            await _scan_chat_stream_registry(
                application_context,
                stale_threshold_ms=stale_threshold_ms,
            )
