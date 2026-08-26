"""SoAI - Inactivity monitor composition for application assembly [backend/app/composition/build_inactivity_monitor.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import logging

from app.internal_protocols import LifecycleCoordinatorProtocol
from app.lifecycle.signals import initiate_shutdown_signal
from core.config.protocols import ConfigProtocol
from core.events.protocols import EventBusProtocol
from core.logging.trace import get_logger
from core.metrics.protocols import MetricsManagerProtocol
from core.runtime.protocols import RuntimeStateStoreProtocol
from core.tasks.protocols import (
    TaskCancellationBinderProtocol,
    TaskFinalizerTrackerProtocol,
)
from orchestrator.director import InactivityMonitor
from orchestrator.inactivity_dependencies import InactivityMonitorDependencies

__all__ = ("build_inactivity_monitor",)

LOGGER_NAME = "SoAI.app.composition.build_inactivity_monitor"


def build_inactivity_monitor(
    *,
    config: ConfigProtocol,
    event_bus: EventBusProtocol,
    runtime_state: RuntimeStateStoreProtocol,
    cancellation_binder: TaskCancellationBinderProtocol,
    finalizer_tracker: TaskFinalizerTrackerProtocol,
    metrics_manager: MetricsManagerProtocol,
    lifecycle_logger: logging.Logger,
    lifecycle_coordinator: LifecycleCoordinatorProtocol,
) -> InactivityMonitor:
    async def shutdown_from_inactivity() -> None:
        initiate_shutdown_signal(
            runtime_state.shutdown_event,
            runtime_state.system_stop_event,
            runtime_state.async_loop,
            "inactivity_monitor",
            lifecycle_logger,
            runtime_state.is_shutting_down,
        )

    monitor = InactivityMonitor(
        InactivityMonitorDependencies(
            config=config,
            event_bus=event_bus,
            main_shutdown_coro=shutdown_from_inactivity,
            cancellation_binder=cancellation_binder,
            finalizer_tracker=finalizer_tracker,
            metrics_manager=metrics_manager,
            audit_logger=get_logger(LOGGER_NAME),
        ),
    )
    lifecycle_coordinator.register_actor(monitor)
    return monitor
