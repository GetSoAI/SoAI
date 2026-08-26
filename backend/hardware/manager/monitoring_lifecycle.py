"""SoAI - Hardware manager monitoring lifecycle operations [backend/hardware/manager/monitoring_lifecycle.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import threading
from collections.abc import Callable
from typing import TYPE_CHECKING

from core.concurrency.threading_async import join_thread
from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.runtime.soai_identifiers import create_system_id
from core.tasks.asyncio_task_spawner import spawn_tracked_task
from hardware.manager.manager_state import HardwareManagerState
from hardware.manager.min_specs_task import run_periodic_min_specs_check
from hardware.monitoring.minimum_specs import check_minimum_specs
from hardware.monitoring.monitor_thread import monitoring_thread_func

if TYPE_CHECKING:
    from core.logging.protocols import TraceLogger
    from core.system.protocols import CommandExecutorProtocol
    from core.tasks.protocols import (
        TaskCancellationBinderProtocol,
        TaskFinalizerTrackerProtocol,
    )
    from hardware.cpu_rapl import RaplEnergyCache
    from hardware.internal_protocols import (
        MinimumSpecsManagerProtocol,
        MonitoringManagerProtocol,
    )

__all__ = (
    "shutdown_hardware_monitoring",
    "start_hardware_monitoring",
)

LOGGER_NAME = "SoAI.hardware.manager.monitoring_lifecycle"
OPERATION = "hardware_manager.shutdown"


def start_hardware_monitoring(
    *,
    manager: MonitoringManagerProtocol,
    min_specs_manager: MinimumSpecsManagerProtocol,
    state: HardwareManagerState,
    enabled: bool,
    hw_gpu_tuning_set_main_loop: Callable[[asyncio.AbstractEventLoop], None],
    cancellation_binder: TaskCancellationBinderProtocol,
    finalizer_tracker: TaskFinalizerTrackerProtocol,
    executor: CommandExecutorProtocol,
    logger: TraceLogger,
    rapl_energy_cache: RaplEnergyCache,
    min_specs_enabled: bool,
    monitoring_thread_name: str = "hardware_monitor_thread",
) -> bool:
    if not enabled:
        logger.debug("Hardware monitoring is disabled in configuration")
        return False
    if state.monitoring_thread and state.monitoring_thread.is_alive():
        logger.debug("Hardware monitoring thread is already running")
        return False
    loop = asyncio.get_running_loop()
    state.main_loop = loop
    hw_gpu_tuning_set_main_loop(loop)
    state.monitoring_stop_event.clear()
    thread = threading.Thread(
        target=monitoring_thread_func,
        args=(manager,),
        daemon=True,
        name=monitoring_thread_name,
    )
    state.monitoring_thread = thread
    thread.start()
    if min_specs_enabled:
        state.min_specs_task = spawn_tracked_task(
            run_periodic_min_specs_check(
                manager=min_specs_manager,
                executor=executor,
                logger=logger,
                check_minimum_specs=check_minimum_specs,
                rapl_energy_cache=rapl_energy_cache,
            ),
            name="hardware-manager-min-specs",
            logger=logger,
            cancellation_binder=cancellation_binder,
            finalizer_tracker=finalizer_tracker,
            cancellation_id=create_system_id(
                subsystem="hardware_manager",
                owner="min_specs",
                include_random_suffix=False,
            ),
            owner="hardware_manager_min_specs",
            metadata={"interval_ms": 21_600_000},
        )
    logger.trace(
        "Started hardware monitoring thread (interval: %ss)",
        max(0.001, float(manager.monitoring_interval_ms) / 1000.0),
    )
    return True


async def shutdown_hardware_monitoring(
    *,
    state: HardwareManagerState,
    logger: TraceLogger,
    join_timeout_seconds: float = 5.0,
) -> None:
    state.monitoring_stop_event.set()
    with state.cache_lock:
        disk_speed_future = state.disk_speed_refresh_future
        state.disk_speed_refresh_future = None
    if disk_speed_future is not None and not disk_speed_future.done():
        disk_speed_future.cancel()
    if state.min_specs_task and (not state.min_specs_task.done()):
        state.min_specs_task.cancel()
        try:
            await state.min_specs_task
        except asyncio.CancelledError:
            state.min_specs_task = None
    get_logger(LOGGER_NAME).trace("HardwareManager shutdown initiated.")
    thread = state.monitoring_thread
    if thread and thread.is_alive():
        try:
            await join_thread(thread, timeout=join_timeout_seconds)
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                logger,
                exception,
                message="Failed to join monitoring thread",
                operation=OPERATION,
            )
    if thread and thread.is_alive():
        logger.warning("Hardware monitoring thread did not exit cleanly within timeout.")
    state.monitoring_thread = None
    get_logger(LOGGER_NAME).trace("HardwareManager has been shut down.")
