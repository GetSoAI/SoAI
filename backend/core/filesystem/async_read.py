"""SoAI - Core async managed file chunk reader utilities [backend/core/filesystem/async_read.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator

from core.concurrency.bounded_blocking import (
    BoundedBlockingCancelledBase,
    BoundedBlockingPool,
    BoundedBlockingTimeoutBase,
    BoundedThreadPoolConfig,
    create_bounded_thread_pool_from_env,
    run_bounded_blocking_call,
)
from core.concurrency.bounded_pool_lifecycle import (
    resolve_lazy_bounded_pool,
    shutdown_lazy_bounded_pool,
)
from core.concurrency.ephemeral_tasks import spawn_ephemeral_task
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import ValidationError
from core.files.managed_file_opening import ManagedFileDescriptor, open_managed_file_descriptor
from core.files.managed_storage_errors import FileStorageSecurityError
from core.logging.trace import get_logger

__all__ = (
    "async_read_managed_file_chunks",
    "shutdown_file_read_executor",
)

LOGGER_NAME = "SoAI.core.filesystem.async_read"
OPERATION_CORE_FILESYSTEM_ASYNC_READ_CLOSE_HANDLE_AFTER_IN_FLIGHT_CLOSE = (
    "core.filesystem.async_read.close_handle_after_in_flight.close"
)
OPERATION_CORE_FILESYSTEM_ASYNC_READ_CLOSE_HANDLE_AFTER_IN_FLIGHT_WAIT = (
    "core.filesystem.async_read.close_handle_after_in_flight.wait"
)
OPERATION_CORE_FILESYSTEM_ASYNC_READ_CLOSE_HANDLE_AFTER_IN_FLIGHT_WAIT_CANCELLED = (
    "core.filesystem.async_read.close_handle_after_in_flight.wait_cancelled"
)
OPERATION_CORE_FILESYSTEM_ASYNC_READ_CLOSE_OPEN_HANDLE_AFTER_IN_FLIGHT_CLOSE = (
    "core.filesystem.async_read.close_open_handle_after_in_flight.close"
)
OPERATION_CORE_FILESYSTEM_ASYNC_READ_CLOSE_OPEN_HANDLE_AFTER_IN_FLIGHT_WAIT = (
    "core.filesystem.async_read.close_open_handle_after_in_flight.wait"
)

_DEFERRED_CLOSE_FAILURES: tuple[type[Exception], ...] = (
    FileStorageSecurityError,
    OSError,
    RuntimeError,
    TypeError,
    ValueError,
)


class _FileReadExecutorState:
    executor: BoundedBlockingPool | None = None


def _create_file_read_executor() -> BoundedBlockingPool:
    return create_bounded_thread_pool_from_env(
        BoundedThreadPoolConfig(
            label="file_read",
            thread_name_prefix="soai-file-read",
            max_workers_env="SOAI_FILE_READ_MAX_WORKERS",
            max_in_flight_env="SOAI_FILE_READ_MAX_IN_FLIGHT",
            default_max_workers=8,
            minimum_workers=1,
            maximum_workers=128,
            default_in_flight_multiplier=4,
            default_min_in_flight=32,
            max_in_flight_limit=8192,
        ),
    )


def _get_file_read_executor() -> BoundedBlockingPool:
    executor = resolve_lazy_bounded_pool(
        _FileReadExecutorState.executor,
        _create_file_read_executor,
    )
    _FileReadExecutorState.executor = executor
    return executor


async def _close_handle_after_in_flight(
    file_descriptor: int,
    in_flight: asyncio.Future[bytes],
) -> None:
    logger = get_logger(LOGGER_NAME)
    try:
        try:
            await asyncio.shield(in_flight)
        except asyncio.CancelledError as exception:
            coerced = coerce_to_soai_error(
                exception,
                operation="core.filesystem.async_read.close_handle_after_in_flight.wait_cancelled",
            )
            log_handled_exception(
                logger,
                coerced,
                message=(
                    "Deferred close observed cancellation while awaiting in-flight read "
                    "(non-critical)."
                ),
                operation=(
                    OPERATION_CORE_FILESYSTEM_ASYNC_READ_CLOSE_HANDLE_AFTER_IN_FLIGHT_WAIT_CANCELLED
                ),
                level="debug",
            )
        except _DEFERRED_CLOSE_FAILURES as exception:
            coerced = coerce_to_soai_error(
                exception,
                operation="core.filesystem.async_read.close_handle_after_in_flight.wait",
            )
            log_handled_exception(
                logger,
                coerced,
                message=(
                    "Failed while awaiting in-flight read during deferred close (non-critical)."
                ),
                operation=OPERATION_CORE_FILESYSTEM_ASYNC_READ_CLOSE_HANDLE_AFTER_IN_FLIGHT_WAIT,
                level="debug",
            )
        await asyncio.to_thread(os.close, file_descriptor)
    except asyncio.CancelledError:
        return
    except _DEFERRED_CLOSE_FAILURES as exception:
        coerced = coerce_to_soai_error(
            exception,
            operation="core.filesystem.async_read.close_handle_after_in_flight.close",
        )
        log_handled_exception(
            logger,
            coerced,
            message="Failed to close deferred file handle (non-critical).",
            operation=OPERATION_CORE_FILESYSTEM_ASYNC_READ_CLOSE_HANDLE_AFTER_IN_FLIGHT_CLOSE,
            level="debug",
        )
        return


async def _close_open_handle_after_in_flight(
    in_flight: asyncio.Future[ManagedFileDescriptor],
) -> None:
    logger = get_logger(LOGGER_NAME)
    try:
        managed_file = await asyncio.shield(in_flight)
    except asyncio.CancelledError:
        return
    except _DEFERRED_CLOSE_FAILURES as exception:
        coerced = coerce_to_soai_error(
            exception,
            operation="core.filesystem.async_read.close_open_handle_after_in_flight.wait",
        )
        log_handled_exception(
            logger,
            coerced,
            message="Failed while awaiting in-flight open during cleanup (non-critical).",
            operation=OPERATION_CORE_FILESYSTEM_ASYNC_READ_CLOSE_OPEN_HANDLE_AFTER_IN_FLIGHT_WAIT,
            level="debug",
        )
        return
    try:
        await asyncio.to_thread(os.close, managed_file.descriptor)
    except asyncio.CancelledError:
        return
    except _DEFERRED_CLOSE_FAILURES as exception:
        coerced = coerce_to_soai_error(
            exception,
            operation="core.filesystem.async_read.close_open_handle_after_in_flight.close",
        )
        log_handled_exception(
            logger,
            coerced,
            message="Failed to close file handle after open timeout (non-critical).",
            operation=OPERATION_CORE_FILESYSTEM_ASYNC_READ_CLOSE_OPEN_HANDLE_AFTER_IN_FLIGHT_CLOSE,
            level="debug",
        )
        return


async def async_read_managed_file_chunks(
    storage_root: str,
    file_path: str,
    *,
    chunk_size: int,
    read_timeout_sec: float,
    shutdown_event: asyncio.Event | None = None,
) -> AsyncIterator[bytes]:
    if chunk_size < 1:
        raise ValidationError("chunk_size must be >= 1.")
    if read_timeout_sec <= 0:
        raise ValidationError("read_timeout_sec must be > 0.")
    if shutdown_event is not None and shutdown_event.is_set():
        return
    managed_file: ManagedFileDescriptor | None = None
    deferred_close = False

    def _schedule_open_timeout_cleanup(in_flight: asyncio.Future[ManagedFileDescriptor]) -> None:
        spawn_ephemeral_task(
            _close_open_handle_after_in_flight(in_flight),
            name="file-open-timeout-cleanup",
        )

    def _schedule_open_cancelled_cleanup(in_flight: asyncio.Future[ManagedFileDescriptor]) -> None:
        spawn_ephemeral_task(
            _close_open_handle_after_in_flight(in_flight),
            name="file-open-cancelled-cleanup",
        )

    try:
        managed_file = await run_bounded_blocking_call(
            _get_file_read_executor(),
            open_managed_file_descriptor,
            storage_root,
            file_path,
            timeout_sec=read_timeout_sec,
            on_timeout=_schedule_open_timeout_cleanup,
            on_cancelled=_schedule_open_cancelled_cleanup,
        )
        file_descriptor = managed_file.descriptor
        while True:
            if shutdown_event is not None and shutdown_event.is_set():
                return
            deferred_close_for_timeout = False

            def _schedule_read_timeout_cleanup(in_flight: asyncio.Future[bytes]) -> None:
                nonlocal deferred_close_for_timeout
                deferred_close_for_timeout = True
                spawn_ephemeral_task(
                    _close_handle_after_in_flight(file_descriptor, in_flight),
                    name="file-read-timeout-cleanup",
                )

            def _schedule_read_cancelled_cleanup(in_flight: asyncio.Future[bytes]) -> None:
                nonlocal deferred_close_for_timeout
                deferred_close_for_timeout = True
                spawn_ephemeral_task(
                    _close_handle_after_in_flight(file_descriptor, in_flight),
                    name="file-read-cancelled-cleanup",
                )

            try:
                chunk = await run_bounded_blocking_call(
                    _get_file_read_executor(),
                    os.read,
                    file_descriptor,
                    chunk_size,
                    timeout_sec=read_timeout_sec,
                    on_timeout=_schedule_read_timeout_cleanup,
                    on_cancelled=_schedule_read_cancelled_cleanup,
                )
            except BoundedBlockingTimeoutBase:
                deferred_close = deferred_close_for_timeout
                raise
            except BoundedBlockingCancelledBase:
                deferred_close = deferred_close_for_timeout
                raise
            if not chunk:
                return
            yield chunk
    finally:
        if managed_file is not None and not deferred_close:
            await asyncio.to_thread(os.close, managed_file.descriptor)


def shutdown_file_read_executor() -> None:
    executor = _FileReadExecutorState.executor
    shutdown_lazy_bounded_pool(executor)
    _FileReadExecutorState.executor = None
