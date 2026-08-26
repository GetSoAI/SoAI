"""SoAI - Inactivity monitor dependency contract [backend/orchestrator/inactivity_dependencies.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from core.config.protocols import ConfigProtocol
from core.di.validation import require_dependencies
from core.events.protocols import EventBusProtocol
from core.logging.protocols import LoggerProtocol
from core.metrics.protocols import MetricsManagerProtocol
from core.tasks.protocols import (
    TaskCancellationBinderProtocol,
    TaskFinalizerTrackerProtocol,
)

__all__ = ("InactivityMonitorDependencies",)


@dataclass(frozen=True, slots=True)
class InactivityMonitorDependencies:
    config: ConfigProtocol
    event_bus: EventBusProtocol
    main_shutdown_coro: Callable[[], Awaitable[None]]
    cancellation_binder: TaskCancellationBinderProtocol
    finalizer_tracker: TaskFinalizerTrackerProtocol
    metrics_manager: MetricsManagerProtocol
    audit_logger: LoggerProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="InactivityMonitorDependencies",
            audit_logger=self.audit_logger,
            cancellation_binder=self.cancellation_binder,
            config=self.config,
            event_bus=self.event_bus,
            finalizer_tracker=self.finalizer_tracker,
            main_shutdown_coro=self.main_shutdown_coro,
            metrics_manager=self.metrics_manager,
        )
