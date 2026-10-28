"""SoAI - Owned persisted network sample refresh [backend/hardware/monitoring/network_speed_refresh.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import time

from core.concurrency.deadlines import is_deadline_expired, wait_for_hard_deadline
from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import StateError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.errors.unexpected_exceptions import UNEXPECTED_RUNTIME_EXCEPTIONS
from core.timing.constants import LOCAL_IO_TIMEOUT_SEC
from hardware.internal_protocols import NetworkSpeedManagerProtocol
from hardware.manager.manager_state import HardwareManagerState

__all__ = ("schedule_network_speed_refresh", "shutdown_network_speed_refresh")

OPERATION = "hardware.network_speed.persisted_refresh"
REFRESH_FAILURES: tuple[type[Exception], ...] = (
    TimeoutError,
    OSError,
    StateError,
    *RECOVERABLE_EXCEPTIONS,
)


async def _refresh(manager: NetworkSpeedManagerProtocol, generation: int, deadline: float) -> None:
    state = manager.state
    with state.cache_lock:
        state.network_speed_refresh_task = asyncio.current_task()
        stopped = state.monitoring_stop_event.is_set()
    try:
        database = manager.database_hardware
        if stopped or database is None:
            return
        result = await wait_for_hard_deadline(
            deadline,
            lambda remaining: asyncio.wait_for(
                database.get_latest_network_speed_snapshot(), timeout=remaining
            ),
        )
        if is_deadline_expired(deadline):
            raise TimeoutError("Persisted network refresh completed after its deadline.")
        if not isinstance(result, dict):
            raise StateError("Persisted network snapshot is not an object.")
        with state.cache_lock:
            if state.monitoring_stop_event.is_set() or state.network_speed_generation != generation:
                return
            manager.set_network_speed_cache(result, cached_at=time.monotonic(), loaded_from_db=True)
            state.network_speed_refresh_failed = False
    except REFRESH_FAILURES as exception:
        with state.cache_lock:
            failure_active = state.network_speed_refresh_failed
            state.network_speed_refresh_failed = True
        if not failure_active:
            log_handled_exception(
                manager.logger,
                exception,
                message="Persisted network samples are unavailable; live counters remain active.",
                operation=OPERATION,
                level="warning",
            )
    except UNEXPECTED_RUNTIME_EXCEPTIONS as exception:
        with state.cache_lock:
            state.network_speed_refresh_failed = True
        log_handled_exception(
            manager.logger,
            exception,
            message="Persisted network refresh failed; valid live and retained data remain available.",
            operation=OPERATION,
            level="error",
        )
    finally:
        with state.cache_lock:
            state.network_speed_refresh_completed_monotonic = time.monotonic()


def schedule_network_speed_refresh(manager: NetworkSpeedManagerProtocol, now: float) -> None:
    state = manager.state
    future = state.network_speed_refresh_future
    task = state.network_speed_refresh_task
    if future is not None:
        if not future.done() or (task is not None and not task.done()):
            return
        state.network_speed_refresh_future = None
        state.network_speed_refresh_task = None
        if not future.cancelled():
            future.result()
    completed = state.network_speed_refresh_completed_monotonic
    if completed is not None and now - completed < manager.network_speed_cache_ttl_seconds:
        return
    loop = manager.main_loop
    if (
        manager.database_hardware is None
        or loop is None
        or loop.is_closed()
        or not loop.is_running()
        or state.monitoring_stop_event.is_set()
    ):
        return
    state.network_speed_generation += 1
    coroutine = _refresh(manager, state.network_speed_generation, now + LOCAL_IO_TIMEOUT_SEC)
    try:
        state.network_speed_refresh_future = asyncio.run_coroutine_threadsafe(coroutine, loop)
    except RuntimeError as exception:
        coroutine.close()
        state.network_speed_refresh_completed_monotonic = now
        failure_active = state.network_speed_refresh_failed
        state.network_speed_refresh_failed = True
        if not failure_active:
            log_handled_exception(
                manager.logger,
                exception,
                message="Persisted network refresh could not be scheduled.",
                operation=OPERATION,
                level="warning",
            )


async def shutdown_network_speed_refresh(state: HardwareManagerState, timeout: float) -> None:
    with state.cache_lock:
        future = state.network_speed_refresh_future
        task = state.network_speed_refresh_task
    if future is None:
        return
    if task is not None and not task.done():
        task.cancel()
    try:
        await asyncio.wait_for(asyncio.shield(asyncio.wrap_future(future)), timeout=timeout)
    except asyncio.CancelledError:
        owner = asyncio.current_task()
        if (owner is not None and owner.cancelling()) or task is None or not task.cancelled():
            raise
    with state.cache_lock:
        if state.network_speed_refresh_task is None or state.network_speed_refresh_task.done():
            state.network_speed_refresh_task = None
            state.network_speed_refresh_future = None
