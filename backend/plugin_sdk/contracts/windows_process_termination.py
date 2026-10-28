"""SoAI - Checked Windows process-tree termination ownership [backend/plugin_sdk/contracts/windows_process_termination.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import logging

from core.concurrency.cancellation_cleanup import wait_for_task_completion
from core.concurrency.deadlines import MonotonicDeadline, deadline_after
from core.files.windows_handle_operations import close_windows_handle
from core.security.public_text_redaction import sanitize_public_diagnostic_text
from core.system.async_process_capture import run_argv_capture_async
from core.system.windows_process_handles import retain_windows_process_handle

__all__ = ("terminate_windows_process_tree",)


async def terminate_windows_process_tree(
    process: asyncio.subprocess.Process,
    *,
    logger: logging.Logger,
    plugin_label: str,
    shutdown_timeout_sec: float,
    kill_wait_sec: float,
) -> bool:
    if process.returncode is not None:
        return True
    try:
        identity_handle = retain_windows_process_handle(process.pid)
    except OSError as exception:
        logger.warning(
            "Could not retain %s process identity for shutdown: %s", plugin_label, exception.errno
        )
        return False
    termination = asyncio.create_task(
        _terminate_owned_tree(
            process,
            logger=logger,
            plugin_label=plugin_label,
            shutdown_timeout_sec=shutdown_timeout_sec,
            kill_wait_sec=kill_wait_sec,
        ),
        name=f"{plugin_label}:windows-tree-termination",
    )
    try:
        return await asyncio.shield(termination)
    except asyncio.CancelledError:
        termination.cancel()
        await wait_for_task_completion(termination, retain_resources_until_complete=True)
        if not termination.cancelled():
            termination.result()
        raise
    finally:
        close_windows_handle(identity_handle)


async def _terminate_owned_tree(
    process: asyncio.subprocess.Process,
    *,
    logger: logging.Logger,
    plugin_label: str,
    shutdown_timeout_sec: float,
    kill_wait_sec: float,
) -> bool:
    force: asyncio.Task[bool] | None = None
    try:
        graceful_deadline = deadline_after(shutdown_timeout_sec)
        graceful_status = await _taskkill(process, graceful_deadline, force=False, logger=logger)
        if process.returncode is not None:
            return True
        if graceful_status == 0 and await _wait_for_exit(process, graceful_deadline):
            return True
        force = asyncio.create_task(
            _force_owned_tree(
                process,
                deadline_after(kill_wait_sec),
                logger=logger,
            ),
            name=f"{plugin_label}:windows-force-termination",
        )
        return await asyncio.shield(force)
    except asyncio.CancelledError:
        if force is None and process.returncode is None:
            force = asyncio.create_task(
                _force_owned_tree(
                    process,
                    deadline_after(kill_wait_sec),
                    logger=logger,
                ),
                name=f"{plugin_label}:windows-cancelled-force-termination",
            )
        if force is not None:
            await wait_for_task_completion(force, retain_resources_until_complete=True)
            force.result()
        raise


async def _force_owned_tree(
    process: asyncio.subprocess.Process,
    deadline: MonotonicDeadline,
    *,
    logger: logging.Logger,
) -> bool:
    if process.returncode is not None:
        return True
    status = await _taskkill(process, deadline, force=True, logger=logger)
    if process.returncode is not None:
        return True
    if status == 0 and await _wait_for_exit(process, deadline):
        return True
    return process.returncode is not None


async def _taskkill(
    process: asyncio.subprocess.Process,
    deadline: MonotonicDeadline,
    *,
    force: bool,
    logger: logging.Logger,
) -> int:
    if process.returncode is not None:
        return 0
    if deadline.expired():
        return 124
    command = ["taskkill", *(["/F"] if force else []), "/PID", str(process.pid), "/T"]
    capture = asyncio.create_task(
        run_argv_capture_async(command, timeout=deadline.remaining_seconds()),
        name="windows-termination-taskkill",
    )
    try:
        result = await asyncio.shield(capture)
    except asyncio.CancelledError:
        await wait_for_task_completion(capture, retain_resources_until_complete=True)
        if not capture.cancelled():
            capture.result()
        raise
    logger.debug(
        "Windows termination command completed: force=%s status=%s diagnostic=%s",
        force,
        result.return_code,
        sanitize_public_diagnostic_text(result.stderr),
    )
    return result.return_code


async def _wait_for_exit(process: asyncio.subprocess.Process, deadline: MonotonicDeadline) -> bool:
    if process.returncode is not None:
        return True
    if deadline.expired():
        return False
    try:
        await asyncio.wait_for(process.wait(), timeout=deadline.remaining_seconds())
    except TimeoutError:
        return process.returncode is not None
    return process.returncode is not None
