"""SoAI - Database I/O controller recovery and shutdown coordination [backend/database/io/controller/recovery.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from queue import Full
from typing import NoReturn

from core.concurrency.threading_async import join_thread, wait_for_threading_event
from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import DatabaseError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.protocols import LoggerProtocol
from core.state.errors import DatabaseUnavailableError
from core.timing.constants import CONTROL_TIMEOUT_SEC
from database.io.controller.internal_protocols import (
    DatabaseIOControllerRecoveryStateProtocol,
)
from database.io.controller.reset_state import (
    cancel_active_jobs,
    drain_pending_items,
    mark_active_jobs_outcome_unknown,
)
from database.io.internal_protocols import ShutdownSentinel

__all__ = (
    "enqueue_shutdown_sentinel",
    "join_writer_thread_with_interrupt",
    "raise_writer_thread_leak",
    "shutdown_writer_thread_after_failed_init",
    "start_writer_thread_runtime",
)

OPERATION_DATABASE_IO_CONTROLLER_ENQUEUE_SHUTDOWN_SENTINEL = (
    "database.io.controller.service.enqueue_shutdown_sentinel"
)
OPERATION_DATABASE_IO_CONTROLLER_SHUTDOWN_WRITER_THREAD_AFTER_FAILED_INIT = (
    "database.io.controller.service.shutdown_writer_thread_after_failed_init"
)


def enqueue_shutdown_sentinel(
    state: DatabaseIOControllerRecoveryStateProtocol,
    logger: LoggerProtocol,
    *,
    operation: str,
) -> None:
    try:
        state.queue.put_nowait(ShutdownSentinel)
    except Full as exception:
        log_handled_exception(
            logger,
            exception,
            message="Database write queue saturated while signaling shutdown (non-critical).",
            operation=OPERATION_DATABASE_IO_CONTROLLER_ENQUEUE_SHUTDOWN_SENTINEL,
            details={"shutdown_operation": operation},
            level="debug",
        )


async def _join_writer_thread_quietly(
    state: DatabaseIOControllerRecoveryStateProtocol,
    timeout: float,
    logger: LoggerProtocol,
    *,
    operation: str,
) -> bool:
    thread = state.thread
    if thread is None or not thread.is_alive():
        return True
    try:
        return await join_thread(thread, timeout=timeout)
    except RECOVERABLE_EXCEPTIONS as exception:
        log_handled_exception(
            logger,
            exception,
            message="Failed to join database writer thread (non-critical).",
            operation=operation,
            level="debug",
        )
        return False


async def join_writer_thread_with_interrupt(
    state: DatabaseIOControllerRecoveryStateProtocol,
    logger: LoggerProtocol,
    *,
    operation: str,
) -> bool:
    initial_timeout = max(float(state.shutdown_timeout), 0.1)
    if await _join_writer_thread_quietly(state, initial_timeout, logger, operation=operation):
        return True
    interrupt_issued = state.interrupt_active_connection()
    logger.warning(
        "Database writer thread still running after %.1fs; interrupt %s. Waiting for the writer thread to exit.",
        initial_timeout,
        "issued to active connection" if interrupt_issued else "unavailable (no active connection)",
    )
    escalation_timeout = max(
        float(state.shutdown_timeout),
        float(state.connect_timeout),
        CONTROL_TIMEOUT_SEC,
    )
    return await _join_writer_thread_quietly(
        state,
        escalation_timeout,
        logger,
        operation=operation,
    )


def raise_writer_thread_leak(
    state: DatabaseIOControllerRecoveryStateProtocol,
    logger: LoggerProtocol,
    *,
    operation: str,
) -> NoReturn:
    state.shutdown_event.set()
    state.writer_session_active.clear()
    state.bound_loop = None
    mark_active_jobs_outcome_unknown(state.operation_status_tracker, logger)
    drain_pending_items(state.queue, state.operation_status_tracker)
    logger.critical(
        "FATAL: Database writer thread did not shut down cleanly within timeout. Refusing to detach the live writer connection because it would fork the WAL lineage and corrupt the database.",
    )
    raise DatabaseError(
        "Database writer thread could not be joined; the writer connection must not outlive shutdown.",
        operation=operation,
    )


async def shutdown_writer_thread_after_failed_init(
    state: DatabaseIOControllerRecoveryStateProtocol,
    logger: LoggerProtocol,
    *,
    operation: str,
) -> None:
    thread = state.thread
    state.writer_session_active.clear()
    state.shutdown_event.set()
    cancel_active_jobs(state.operation_status_tracker, logger)
    enqueue_shutdown_sentinel(state, logger, operation=operation)
    if thread is None or not thread.is_alive():
        state.thread = None
        state.bound_loop = None
        drain_pending_items(state.queue, state.operation_status_tracker)
        return
    joined = await join_writer_thread_with_interrupt(
        state,
        logger,
        operation=OPERATION_DATABASE_IO_CONTROLLER_SHUTDOWN_WRITER_THREAD_AFTER_FAILED_INIT,
    )
    if not joined:
        raise_writer_thread_leak(
            state,
            logger,
            operation=OPERATION_DATABASE_IO_CONTROLLER_SHUTDOWN_WRITER_THREAD_AFTER_FAILED_INIT,
        )
    state.thread = None
    state.bound_loop = None
    drain_pending_items(state.queue, state.operation_status_tracker)


async def start_writer_thread_runtime(
    state: DatabaseIOControllerRecoveryStateProtocol,
    logger: LoggerProtocol,
) -> None:
    if state.thread is None or not state.thread.is_alive():
        raise DatabaseUnavailableError("Database writer thread is not running.")
    if state.runtime_ready_event.is_set():
        return
    state.runtime_start_event.set()
    runtime_ok = await wait_for_threading_event(
        state.runtime_ready_event,
        timeout=state.init_timeout,
    )
    if not runtime_ok:
        await shutdown_writer_thread_after_failed_init(
            state,
            logger,
            operation="database.io.controller.start_runtime.timeout",
        )
        raise DatabaseUnavailableError("Database runtime initialization timed out.")
    init_error = state.init_error
    if init_error is not None:
        await shutdown_writer_thread_after_failed_init(
            state,
            logger,
            operation="database.io.controller.start_runtime.init_error",
        )
        raise DatabaseUnavailableError("Database runtime initialization failed.") from init_error
