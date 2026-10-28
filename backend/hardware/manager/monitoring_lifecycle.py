"""SoAI - Hardware manager monitoring lifecycle operations [backend/hardware/manager/monitoring_lifecycle.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import threading
from collections.abc import Callable
from typing import TYPE_CHECKING

from core.concurrency.task_groups import cancel_and_await
from core.concurrency.threading_async import join_thread
from core.errors.exceptions import ProcessError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.runtime.platform import get_runtime_platform
from core.runtime.soai_identifiers import create_system_id
from core.tasks.asyncio_task_spawner import spawn_tracked_task
from hardware.manager.manager_state import HardwareManagerState
from hardware.manager.min_specs_task import run_periodic_min_specs_check
from hardware.manager.windows_static_inventory import run_windows_static_inventory_refresh
from hardware.monitoring.minimum_specs import check_minimum_specs
from hardware.monitoring.monitor_thread import monitoring_thread_func
from hardware.monitoring.network_speed_refresh import shutdown_network_speed_refresh

if TYPE_CHECKING:
    from core.concurrency.deadlines import MonotonicDeadline
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
    "require_hardware_monitoring_start_ready",
    "shutdown_hardware_monitoring",
    "start_hardware_monitoring",
)

LOGGER_NAME = "SoAI.hardware.manager.monitoring_lifecycle"
OPERATION = "hardware_manager.shutdown"


def require_hardware_monitoring_start_ready(*, state: HardwareManagerState) -> None:
    if state.monitoring_thread and state.monitoring_thread.is_alive():
        if state.monitoring_stop_event.is_set():
            raise ProcessError(
                "Previous hardware monitoring thread is still stopping.", operation=OPERATION
            )
        return
    if state.min_specs_task is not None and not state.min_specs_task.done():
        raise ProcessError(
            "Previous minimum specifications check is still stopping.", operation=OPERATION
        )
    with state.cache_lock:
        if state.disk_speed_refresh_task is not None and not state.disk_speed_refresh_task.done():
            raise ProcessError(
                "Previous disk speed refresh is still stopping.", operation=OPERATION
            )
    with state.cache_lock:
        if state.network_speed_refresh_future is not None:
            raise ProcessError("Previous network refresh is still stopping.", operation=OPERATION)
    static_inventory = state.windows_static_inventory
    if static_inventory.task is not None and not static_inventory.task.done():
        raise ProcessError(
            "Previous Windows static inventory worker is still stopping.", operation=OPERATION
        )


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
    require_hardware_monitoring_start_ready(state=state)
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
    static_inventory = state.windows_static_inventory
    if get_runtime_platform().is_windows:
        static_inventory.stopped.clear()
        static_inventory.refresh_eligibility.clear()
        static_inventory.task = spawn_tracked_task(
            run_windows_static_inventory_refresh(static_inventory, executor),
            name="hardware-windows-static-inventory",
            logger=logger,
            cancellation_binder=cancellation_binder,
            finalizer_tracker=finalizer_tracker,
            cancellation_id=create_system_id(
                subsystem="hardware_manager",
                owner="windows_static_inventory",
                include_random_suffix=False,
            ),
            owner="hardware_manager_windows_static_inventory",
            metadata={"refresh_interval_seconds": 300},
        )
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
    deadline: MonotonicDeadline | None = None,
) -> None:
    state.monitoring_stop_event.set()
    static_inventory = state.windows_static_inventory
    static_inventory.stopped.set()
    static_task = static_inventory.task
    with state.cache_lock:
        disk_speed_future = state.disk_speed_refresh_future
        disk_speed_task = state.disk_speed_refresh_task
        if disk_speed_task is None and disk_speed_future is not None:
            disk_speed_future.cancel()
            state.disk_speed_refresh_future = None
    min_specs_task = state.min_specs_task
    await cancel_and_await(
        [min_specs_task, disk_speed_task, static_task],
        timeout_sec=_remaining_join_timeout(join_timeout_seconds, deadline),
    )
    if static_task is not None and static_task.done():
        static_inventory.task = None
    if min_specs_task is not None and min_specs_task.done():
        state.min_specs_task = None
    with state.cache_lock:
        if disk_speed_task is not None and disk_speed_task.done():
            state.disk_speed_refresh_task = None
            state.disk_speed_refresh_future = None
    await shutdown_network_speed_refresh(
        state, _remaining_join_timeout(join_timeout_seconds, deadline)
    )
    get_logger(LOGGER_NAME).trace("HardwareManager shutdown initiated.")
    thread = state.monitoring_thread
    joined = True
    if thread is not None:
        try:
            joined = await join_thread(
                thread, timeout=_remaining_join_timeout(join_timeout_seconds, deadline)
            )
        except RECOVERABLE_EXCEPTIONS as exception:
            joined = not thread.is_alive()
            if joined:
                state.monitoring_thread = None
            raise ProcessError(
                "Hardware monitoring thread could not be joined; retry after its workers settle.",
                operation=OPERATION,
                cause=exception,
                details={
                    "monitoring_thread_pending": not joined,
                    "windows_static_inventory_pending": static_task is not None
                    and not static_task.done(),
                    "min_specs_pending": min_specs_task is not None and not min_specs_task.done(),
                    "disk_speed_refresh_pending": (
                        disk_speed_task is not None and not disk_speed_task.done()
                    ),
                },
            ) from exception
        if joined:
            state.monitoring_thread = None
    min_specs_pending = min_specs_task is not None and not min_specs_task.done()
    disk_speed_pending = disk_speed_task is not None and not disk_speed_task.done()
    static_pending = static_task is not None and not static_task.done()
    if not joined or min_specs_pending or disk_speed_pending or static_pending:
        raise ProcessError(
            "Hardware monitoring shutdown has not completed; retry after its workers settle.",
            operation=OPERATION,
            details={
                "monitoring_thread_pending": not joined,
                "windows_static_inventory_pending": static_task is not None
                and not static_task.done(),
                "min_specs_pending": min_specs_pending,
                "disk_speed_refresh_pending": disk_speed_pending,
            },
        )
    logger.trace("HardwareManager has been shut down.")


def _remaining_join_timeout(default: float, deadline: MonotonicDeadline | None) -> float:
    return default if deadline is None else deadline.remaining_seconds()
