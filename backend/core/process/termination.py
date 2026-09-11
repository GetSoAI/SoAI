"""SoAI - Subprocess termination primitives [backend/core/process/termination.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os
import signal
import subprocess
from typing import TYPE_CHECKING

import psutil

from core.concurrency.deadlines import deadline_after
from core.errors.exception_logging import log_exception
from core.errors.exceptions import ProcessError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.protocols import LoggerProtocol
from core.timing.constants import LOCAL_IO_TIMEOUT_SEC, MODERATE_DELAY_SEC, RESPONSIVE_TIMEOUT_SEC
from core.timing.sleep import sleep_seconds

if TYPE_CHECKING:
    from core.system.process_launcher import ManagedProcess

__all__ = (
    "poll_process_exit_without_reaping",
    "terminate_subprocess_gracefully",
    "terminate_process_and_wait",
)


def _signal_process(
    process: asyncio.subprocess.Process,
    *,
    process_group: bool,
    force: bool,
) -> bool:
    try:
        if process_group:
            os.killpg(
                process.pid,
                signal.SIGKILL if force else signal.SIGTERM,
            )
        elif force:
            process.kill()
        else:
            process.terminate()
    except ProcessLookupError:
        return False
    return True


async def terminate_subprocess_gracefully(
    process: asyncio.subprocess.Process,
    *,
    graceful_timeout_sec: float = float(RESPONSIVE_TIMEOUT_SEC),
    logger: LoggerProtocol,
    operation: str,
    process_group: bool = False,
) -> None:
    try:
        _signal_process(process, process_group=process_group, force=False)
        try:
            await asyncio.wait_for(process.wait(), timeout=graceful_timeout_sec)
        except TimeoutError:
            _signal_process(process, process_group=process_group, force=True)
            await asyncio.wait_for(process.wait(), timeout=LOCAL_IO_TIMEOUT_SEC)
    except RECOVERABLE_EXCEPTIONS as termination_error:
        log_exception(
            logger,
            termination_error,
            message="Error during subprocess termination",
            operation=operation,
            level="warning",
        )
        raise ProcessError(
            "Subprocess termination failed.",
            operation=operation,
            cause=termination_error,
        ) from termination_error


def poll_process_exit_without_reaping(process: ManagedProcess) -> int | None:
    if os.name == "nt":
        return process.poll()
    if process.returncode is not None:
        return process.returncode
    status = os.waitid(os.P_PID, process.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT)
    if status is None:
        return None
    return status.si_status if status.si_code == os.CLD_EXITED else -status.si_status


def _process_group_has_running_members(group_id: int) -> bool:
    for member in psutil.process_iter():
        try:
            if os.getpgid(member.pid) == group_id and member.status() != psutil.STATUS_ZOMBIE:
                return True
        except (ProcessLookupError, psutil.NoSuchProcess):
            continue
    return False


def _terminate_process_group_and_wait(process: ManagedProcess, *, timeout_sec: float) -> None:
    if os.name == "nt" or process.returncode is not None:
        raise ProcessError("Process group cleanup requires an unreaped POSIX child.")
    poll_process_exit_without_reaping(process)
    if os.getpgid(process.pid) != process.pid:
        raise ProcessError("Process group cleanup requires its owned group leader.")
    for requested_signal in (signal.SIGTERM, signal.SIGKILL):
        os.killpg(process.pid, requested_signal)
        deadline = deadline_after(timeout_sec)
        while _process_group_has_running_members(process.pid):
            if deadline.expired():
                break
            sleep_seconds(MODERATE_DELAY_SEC)
        else:
            process.wait(timeout=timeout_sec)
            return
    raise ProcessError("Process group cleanup did not verify exit before its deadline.")


def terminate_process_and_wait(
    process: ManagedProcess, *, timeout_sec: float, process_group: bool = False
) -> None:
    if process_group:
        _terminate_process_group_and_wait(process, timeout_sec=timeout_sec)
        return
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=timeout_sec)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=timeout_sec)
