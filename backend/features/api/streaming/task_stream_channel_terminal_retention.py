"""SoAI - Task stream terminal retention helpers [backend/features/api/streaming/task_stream_channel_terminal_retention.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.concurrency.deadlines import MonotonicDeadline, deadline_after
from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.types_base import Event
from core.metrics.protocols import MetricsManagerProtocol
from core.tasks.protocols import TaskRegistryProtocol
from features.api.streaming.task_stream_terminal_state import (
    build_terminal_event,
    check_task_terminal,
)

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol

__all__ = (
    "TaskStreamTerminalRetention",
    "resolve_retained_terminal_event",
)

OPERATION_RESOLVE_RETAINED_TERMINAL = "api.streaming.task_stream_channel_terminal_retention"


@dataclass(slots=True)
class TaskStreamTerminalRetention:
    retention_seconds: float
    completion_event: asyncio.Event | None = None
    terminal_deadline: MonotonicDeadline | None = None
    terminal_buffered: bool = False

    def mark_terminal_observed(self) -> None:
        if self.terminal_buffered:
            return
        self.terminal_buffered = True
        self.terminal_deadline = deadline_after(self.retention_seconds)

    def has_expired(self) -> bool:
        deadline = self.terminal_deadline
        return deadline is not None and deadline.expired()


async def resolve_retained_terminal_event(
    *,
    retention: TaskStreamTerminalRetention,
    task_registry: TaskRegistryProtocol,
    task_id: str | None,
    metrics_manager: MetricsManagerProtocol | None,
    logger: LoggerProtocol,
) -> Event | None:
    if retention.terminal_buffered or not task_id:
        return None
    if retention.completion_event is None:
        try:
            retention.completion_event = await task_registry.ensure_completion_event(
                task_id,
                set_if_terminal=False,
            )
        except AttributeError:
            retention.completion_event = None
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                logger,
                exception,
                message="Failed to ensure completion event for terminal retention (non-critical).",
                operation=OPERATION_RESOLVE_RETAINED_TERMINAL,
                level="debug",
            )
            retention.completion_event = None
    terminal_detected = False
    completion_event = retention.completion_event
    if completion_event is not None and completion_event.is_set():
        terminal_detected = True
    elif completion_event is None:
        terminal_detected = await check_task_terminal(task_registry, task_id, logger=logger)
    if not terminal_detected:
        return None
    terminal_event = await build_terminal_event(
        task_registry=task_registry,
        task_id=task_id,
        metrics_manager=metrics_manager,
        fallback_if_missing=True,
        logger=logger,
    )
    if terminal_event is None:
        return None
    retention.mark_terminal_observed()
    return terminal_event
