"""SoAI - Hardware monitor background thread loop [backend/hardware/monitoring/monitor_thread.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exception_logging import log_exception
from core.errors.exceptions import StateError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.timing.monotonic import monotonic_ms
from hardware.internal_protocols import MonitoringManagerProtocol

__all__ = ("monitoring_thread_func",)

OPERATION = "hardware.monitoring_thread"
MONITORING_RECOVERABLE_EXCEPTIONS: tuple[type[Exception], ...] = (
    *RECOVERABLE_EXCEPTIONS,
    StateError,
)


def monitoring_thread_func(manager: MonitoringManagerProtocol) -> None:
    stop_event = manager.monitoring_stop_event
    interval_ms = max(1.0, float(manager.monitoring_interval_ms))
    next_deadline_ms = monotonic_ms() + interval_ms
    while not stop_event.is_set():
        try:
            if stop_event.wait(max(0.0, next_deadline_ms - monotonic_ms()) / 1000.0):
                break
            if stop_event.is_set():
                break
            info = manager.sync_get_system_info(
                cache=False,
                include_gpu_capabilities=False,
            )
            if stop_event.is_set():
                break
            manager.monitoring_coordinator.dispatch_snapshot(info, manager.main_loop)
        except MONITORING_RECOVERABLE_EXCEPTIONS as exception:
            if not stop_event.is_set() and manager.logger is not None:
                log_exception(
                    manager.logger,
                    exception,
                    message="Error in hardware monitoring thread",
                    operation=OPERATION,
                )
        interval_ms = max(1.0, float(manager.monitoring_interval_ms))
        next_deadline_ms += interval_ms
        now_ms = monotonic_ms()
        if next_deadline_ms <= now_ms:
            next_deadline_ms += ((now_ms - next_deadline_ms) // interval_ms + 1) * interval_ms
