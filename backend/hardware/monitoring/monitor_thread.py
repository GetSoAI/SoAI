"""SoAI - Hardware monitor background thread loop [backend/hardware/monitoring/monitor_thread.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exception_logging import log_exception
from core.errors.exceptions import StateError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from hardware.internal_protocols import MonitoringManagerProtocol

__all__ = ("monitoring_thread_func",)

OPERATION = "hardware.monitoring_thread"
MONITORING_RECOVERABLE_EXCEPTIONS: tuple[type[Exception], ...] = (
    *RECOVERABLE_EXCEPTIONS,
    StateError,
)


def monitoring_thread_func(manager: MonitoringManagerProtocol) -> None:
    stop_event = manager.monitoring_stop_event
    while not stop_event.is_set():
        try:
            interval_seconds = max(0.001, float(manager.monitoring_interval_ms) / 1000.0)
            if stop_event.wait(interval_seconds):
                break
            if stop_event.is_set():
                break
            info = manager.sync_get_system_info(
                cache=False,
                include_gpu_capabilities=False,
            )
            manager.monitoring_coordinator.dispatch_snapshot(info, manager.main_loop)
        except MONITORING_RECOVERABLE_EXCEPTIONS as exception:
            if not stop_event.is_set() and manager.logger is not None:
                log_exception(
                    manager.logger,
                    exception,
                    message="Error in hardware monitoring thread",
                    operation=OPERATION,
                )
