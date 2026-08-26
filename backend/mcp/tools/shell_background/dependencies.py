"""SoAI - Background shell service dependencies [backend/mcp/tools/shell_background/dependencies.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.di.validation import require_dependencies

if TYPE_CHECKING:
    from core.events.protocols import EventBusProtocol
    from core.logging.protocols import LoggerProtocol
    from core.tasks.protocols import (
        TaskCancellationBinderProtocol,
        TaskFinalizerTrackerProtocol,
        TaskRegistryProtocol,
    )
    from core.tool_calls.protocols import DatabaseToolCallsProtocol

__all__ = ("ShellBackgroundServiceDependencies",)


@dataclass(frozen=True, slots=True)
class ShellBackgroundServiceDependencies:
    database_tool_calls: DatabaseToolCallsProtocol
    task_registry: TaskRegistryProtocol
    event_bus: EventBusProtocol
    task_cancellation_binder: TaskCancellationBinderProtocol
    task_finalizer_tracker: TaskFinalizerTrackerProtocol
    logger: LoggerProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="ShellBackgroundServiceDependencies",
            database_tool_calls=self.database_tool_calls,
            task_registry=self.task_registry,
            event_bus=self.event_bus,
            task_cancellation_binder=self.task_cancellation_binder,
            task_finalizer_tracker=self.task_finalizer_tracker,
            logger=self.logger,
        )
