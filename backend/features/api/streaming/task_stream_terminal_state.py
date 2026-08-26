"""SoAI - Task stream terminal-state detection and synthesis [backend/features/api/streaming/task_stream_terminal_state.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.types_base import Event
from core.metrics.keyspace_paths_event_streaming import (
    STREAMING_COUNTER_CHANNEL_EVICTION_TERMINAL,
)
from core.metrics.protocols import MetricsManagerProtocol
from core.tasks.protocols import TaskRegistryProtocol
from features.api.streaming.delivery_metrics import record_delivery_metric
from features.api.streaming.task_polling import task_to_complete_event
from features.api.streaming.terminal_events import build_eviction_terminal_event

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from core.tasks.task import Task

__all__ = (
    "build_terminal_event",
    "check_task_terminal",
)

OPERATION_CHECK_TASK_TERMINAL = "api.streaming.task_stream_terminal_state.check_terminal"
OPERATION_BUILD_TERMINAL_EVENT = "api.streaming.task_stream_terminal_state.build_event"


async def check_task_terminal(
    task_registry: TaskRegistryProtocol,
    task_id: str,
    *,
    logger: LoggerProtocol,
) -> bool:
    completion_event: asyncio.Event | None = None
    try:
        async with task_registry.completion_events_lock:
            completion_event = task_registry.completion_events.get(task_id)
    except AttributeError:
        completion_event = None
    if completion_event is not None and completion_event.is_set():
        return True
    try:
        task: Task | None = await task_registry.get(task_id, force_refresh=False)
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message="Failed to check task terminal state (non-critical).",
            operation=OPERATION_CHECK_TASK_TERMINAL,
            level="debug",
        )
        return False
    if task is None:
        return True
    return task.status.is_terminal()


async def build_terminal_event(
    *,
    task_registry: TaskRegistryProtocol,
    task_id: str,
    metrics_manager: MetricsManagerProtocol | None,
    fallback_if_missing: bool,
    logger: LoggerProtocol,
) -> Event | None:
    try:
        task = await task_registry.get(task_id, force_refresh=False)
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message="Failed to build terminal event; using fallback (non-critical).",
            operation=OPERATION_BUILD_TERMINAL_EVENT,
            level="debug",
        )
        if fallback_if_missing:
            record_delivery_metric(metrics_manager, STREAMING_COUNTER_CHANNEL_EVICTION_TERMINAL)
            return build_eviction_terminal_event(task_id)
        return None
    if task is None:
        if fallback_if_missing:
            record_delivery_metric(metrics_manager, STREAMING_COUNTER_CHANNEL_EVICTION_TERMINAL)
            return build_eviction_terminal_event(task_id)
        return None
    if not task.status.is_terminal():
        return None
    return task_to_complete_event(task)
