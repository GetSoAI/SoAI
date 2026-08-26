"""SoAI - Process lifecycle helpers for plugins [backend/plugin_sdk/contracts/process_lifecycle.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import io
import logging
import os
import signal
from collections.abc import Awaitable, Callable

from core.concurrency.cancellation_cleanup import uncancel_and_wait
from core.concurrency.task_groups import (
    DEFAULT_CANCELLATION_TIMEOUT_SEC,
    cancel_and_await,
)
from core.errors.exception_coercion import coerce_to_soai_error
from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.platform.os import is_windows
from core.system.async_process_spawning import spawn_async_process
from plugin_sdk.contracts.process_group_termination import terminate_remaining_process_group

__all__ = (
    "check_process_alive",
    "terminate_managed_process",
)

OPERATION_PLUGIN_SDK_CONTRACTS_PROCESS_LIFECYCLE_TERMINATE_MANAGED_PROCESS = (
    "plugin_sdk.contracts.process_lifecycle.terminate_managed_process"
)
PROCESS_LIFECYCLE_OPERATION_EXCEPTIONS: tuple[type[Exception], ...] = (
    *RECOVERABLE_EXCEPTIONS,
    OSError,
)


def check_process_alive(process: asyncio.subprocess.Process | None) -> bool:
    return process is not None and process.returncode is None


async def terminate_managed_process(
    *,
    process: asyncio.subprocess.Process,
    process_group_id: int | None = None,
    logger: logging.Logger,
    plugin_label: str,
    shutdown_timeout_sec: float = 30.0,
    kill_wait_sec: float = 10.0,
    use_process_group: bool = True,
    force_kill_tree_callback: Callable[[int, float], Awaitable[bool]] | None = None,
    log_consumer_tasks: list[asyncio.Task[None]] | None = None,
    log_file_handle: io.BufferedIOBase | None = None,
) -> bool:
    pid = process.pid
    terminated = process.returncode is not None
    owned_process_group_id = process_group_id if use_process_group and not is_windows() else None
    process_group_terminated = True
    if use_process_group and not is_windows() and owned_process_group_id is None and not terminated:
        try:
            owned_process_group_id = await asyncio.to_thread(os.getpgid, pid)
        except ProcessLookupError:
            terminated = True
        except OSError as exception:
            log_exception(
                logger,
                exception,
                message=f"Failed to identify {plugin_label} process group",
                operation=OPERATION_PLUGIN_SDK_CONTRACTS_PROCESS_LIFECYCLE_TERMINATE_MANAGED_PROCESS,
            )
            process_group_terminated = False
    if not terminated:
        logger.info(
            "Initiating termination for %s process with PID: %s",
            plugin_label,
            pid,
        )
    try:
        if not terminated:
            if use_process_group:
                if is_windows():
                    taskkill = await spawn_async_process(
                        ["taskkill", "/PID", str(pid), "/T"],
                        stdin=None,
                        stdout=asyncio.subprocess.DEVNULL,
                        stderr=asyncio.subprocess.DEVNULL,
                    )
                    await asyncio.wait_for(taskkill.wait(), timeout=shutdown_timeout_sec)
                else:
                    await asyncio.to_thread(
                        os.killpg,
                        owned_process_group_id if owned_process_group_id is not None else pid,
                        signal.SIGTERM,
                    )
            else:
                process.terminate()

            await asyncio.wait_for(process.wait(), timeout=shutdown_timeout_sec)
            terminated = process.returncode is not None
            if terminated:
                logger.info("%s process %s terminated gracefully.", plugin_label, pid)
    except TimeoutError:
        logger.warning(
            "%s process %s did not terminate gracefully. Killing.",
            plugin_label,
            pid,
        )
        try:
            if process.returncode is None:
                if use_process_group:
                    if is_windows():
                        taskkill = await spawn_async_process(
                            ["taskkill", "/F", "/PID", str(pid), "/T"],
                            stdin=None,
                            stdout=asyncio.subprocess.DEVNULL,
                            stderr=asyncio.subprocess.DEVNULL,
                        )
                        await asyncio.wait_for(taskkill.wait(), timeout=kill_wait_sec)
                    else:
                        await asyncio.to_thread(
                            os.killpg,
                            owned_process_group_id if owned_process_group_id is not None else pid,
                            signal.SIGKILL,
                        )
                else:
                    process.kill()
            await asyncio.wait_for(process.wait(), timeout=kill_wait_sec)
            terminated = process.returncode is not None
            if terminated:
                logger.info("%s process %s was forcefully killed.", plugin_label, pid)
        except ProcessLookupError:
            logger.warning(
                "Process %s already gone when attempting to kill %s.",
                pid,
                plugin_label,
            )
            terminated = True
        except TimeoutError:
            if force_kill_tree_callback is not None and process.returncode is None:
                logger.warning(
                    "%s process %s did not exit after force kill. Attempting kill-tree fallback.",
                    plugin_label,
                    pid,
                )
                try:
                    await force_kill_tree_callback(pid, kill_wait_sec)
                except PROCESS_LIFECYCLE_OPERATION_EXCEPTIONS as exception:
                    coerced = coerce_to_soai_error(
                        exception,
                        operation=f"{plugin_label}.stop.kill_tree",
                    )
                    log_exception(
                        logger,
                        coerced,
                        message="Kill-tree fallback failed",
                        operation=OPERATION_PLUGIN_SDK_CONTRACTS_PROCESS_LIFECYCLE_TERMINATE_MANAGED_PROCESS,
                    )
                try:
                    await asyncio.wait_for(process.wait(), timeout=kill_wait_sec)
                except TimeoutError:
                    logger.debug(
                        "%s process %s did not exit after kill-tree fallback wait.",
                        plugin_label,
                        pid,
                    )
                terminated = process.returncode is not None
            if not terminated:
                logger.error(
                    "Failed to kill %s process %s even with force.",
                    plugin_label,
                    pid,
                )
    except ProcessLookupError:
        logger.warning(
            "Process %s already gone during %s shutdown.",
            pid,
            plugin_label,
        )
        terminated = True
    except PermissionError:
        logger.warning(
            "Permission denied during shutdown of %s process %s.",
            plugin_label,
            pid,
        )
    except asyncio.CancelledError:
        if process.returncode is None:
            logger.warning(
                "%s process %s termination was cancelled. Killing before propagating cancellation.",
                plugin_label,
                pid,
            )
            try:
                if use_process_group:
                    if is_windows():
                        taskkill = await spawn_async_process(
                            ["taskkill", "/F", "/PID", str(pid), "/T"],
                            stdin=None,
                            stdout=asyncio.subprocess.DEVNULL,
                            stderr=asyncio.subprocess.DEVNULL,
                        )
                        await asyncio.wait_for(taskkill.wait(), timeout=kill_wait_sec)
                    else:
                        await asyncio.to_thread(
                            os.killpg,
                            owned_process_group_id if owned_process_group_id is not None else pid,
                            signal.SIGKILL,
                        )
                else:
                    process.kill()
                await asyncio.wait_for(process.wait(), timeout=kill_wait_sec)
                terminated = process.returncode is not None
            except ProcessLookupError:
                terminated = True
            except (TimeoutError, PermissionError) as exception:
                logger.error(
                    "Failed to kill %s process %s after termination cancellation: %s",
                    plugin_label,
                    pid,
                    exception,
                )
        raise
    except PROCESS_LIFECYCLE_OPERATION_EXCEPTIONS as exception:
        coerced = coerce_to_soai_error(
            exception,
            operation=f"{plugin_label}.stop",
        )
        log_exception(
            logger,
            coerced,
            message=f"Error during termination of PID {pid}",
            operation=OPERATION_PLUGIN_SDK_CONTRACTS_PROCESS_LIFECYCLE_TERMINATE_MANAGED_PROCESS,
        )
    finally:
        if owned_process_group_id is not None:
            process_group_terminated = await uncancel_and_wait(
                terminate_remaining_process_group(
                    owned_process_group_id,
                    logger=logger,
                    plugin_label=plugin_label,
                    operation=OPERATION_PLUGIN_SDK_CONTRACTS_PROCESS_LIFECYCLE_TERMINATE_MANAGED_PROCESS,
                    timeout_sec=kill_wait_sec,
                ),
            )
        await uncancel_and_wait(
            _cleanup_process_resources(
                logger=logger,
                plugin_label=plugin_label,
                log_consumer_tasks=log_consumer_tasks,
                log_file_handle=log_file_handle,
            ),
        )
    return (terminated or process.returncode is not None) and process_group_terminated


async def _cleanup_process_resources(
    *,
    logger: logging.Logger,
    plugin_label: str,
    log_consumer_tasks: list[asyncio.Task[None]] | None,
    log_file_handle: io.BufferedIOBase | None,
) -> None:
    if log_consumer_tasks is not None:
        await cancel_and_await(
            log_consumer_tasks,
            logger=logger,
            task_label="process log consumer tasks",
            timeout_sec=DEFAULT_CANCELLATION_TIMEOUT_SEC,
        )
        log_consumer_tasks.clear()
    if log_file_handle is not None:
        try:
            await asyncio.to_thread(log_file_handle.close)
        except OSError as exception:
            coerced = coerce_to_soai_error(
                exception,
                operation=f"{plugin_label}.stop.close_log",
            )
            log_exception(
                logger,
                coerced,
                message="Error closing process log file",
                operation=OPERATION_PLUGIN_SDK_CONTRACTS_PROCESS_LIFECYCLE_TERMINATE_MANAGED_PROCESS,
            )
