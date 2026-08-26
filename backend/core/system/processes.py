"""SoAI - Process listing and termination via psutil [backend/core/system/processes.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import math
from contextlib import nullcontext
from typing import TYPE_CHECKING

import psutil

from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.platform.os import is_windows
from core.timing.constants import SHORT_POLL_INTERVAL_SEC

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "get_process_list",
    "kill_process_psutil",
)

LOGGER_NAME = "SoAI.core.system.processes"
OPERATION_SYSTEM_PROCESSES_KILL_PROCESS_PSUTIL_ACCESS = (
    "system.processes.kill_process_psutil.access"
)
OPERATION_SYSTEM_PROCESSES_KILL_PROCESS_PSUTIL_KILL = "system.processes.kill_process_psutil.kill"
OPERATION_SYSTEM_PROCESSES_KILL_PROCESS_PSUTIL_WAIT = "system.processes.kill_process_psutil.wait"


def get_process_list(filter_str: str | None = None) -> list[JSONDict]:
    primed_processes: list[tuple[psutil.Process, str, str]] = []
    for process in psutil.process_iter(
        ["pid", "name", "username", "cpu_percent", "memory_info", "create_time"],
    ):
        try:
            name_value = process.name()
            username_value = process.username()
            if filter_str and filter_str.lower() not in name_value.lower():
                continue
            pid_value = int(process.pid)
            if pid_value <= 0:
                continue
            process.cpu_percent(interval=None)
            primed_processes.append((process, name_value, username_value))
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    _ = psutil.cpu_percent(interval=SHORT_POLL_INTERVAL_SEC)
    procs: list[JSONDict] = []
    for process, name_value, username_value in primed_processes:
        try:
            try:
                oneshot_context = process.oneshot()
            except AttributeError:
                oneshot_context = nullcontext()
            with oneshot_context:
                pid_value = int(process.pid)
                if pid_value <= 0:
                    continue
                cpu_percent = float(process.cpu_percent(interval=None))
                rss_bytes = float(process.memory_info().rss)
                swap_mb, swap_known = _read_process_swap_mb(process)
                create_time = float(process.create_time())
            procs.append(
                {
                    "pid": pid_value,
                    "name": name_value,
                    "username": username_value,
                    "cpuPercent": cpu_percent,
                    "memoryMb": rss_bytes / 1024**2,
                    "swapMb": swap_mb,
                    "swapKnown": swap_known,
                    "createTimeMs": int(create_time * 1000),
                },
            )
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    return procs


def _read_process_swap_mb(process: psutil.Process) -> tuple[float | None, bool]:
    try:
        full_info = process.memory_full_info()
        swap_value = full_info.swap
    except (
        AttributeError,
        RuntimeError,
        psutil.AccessDenied,
        psutil.NoSuchProcess,
        psutil.ZombieProcess,
    ):
        return (None, False)
    if not isinstance(swap_value, int | float) or isinstance(swap_value, bool):
        return (None, False)
    swap_bytes = float(swap_value)
    if not math.isfinite(swap_bytes) or swap_bytes < 0:
        return (None, False)
    return (swap_bytes / 1024**2, True)


def kill_process_psutil(
    pid: int,
    signal_to_send: int = 15,
) -> tuple[bool, str]:
    logger = get_logger(LOGGER_NAME)
    if not isinstance(pid, int) or pid <= 0:
        return (False, f"Invalid PID: {pid}")
    try:
        proc = psutil.Process(pid)
        if is_windows():
            proc.kill()
            proc.wait(timeout=5)
            return (True, f"Process {pid} terminated.")
        if signal_to_send == 9:
            proc.kill()
            proc.wait(timeout=5)
            return (True, f"Process {pid} terminated.")
        proc.send_signal(signal_to_send)
        try:
            proc.wait(timeout=5)
        except RECOVERABLE_EXCEPTIONS as exception:
            log_handled_exception(
                logger,
                exception,
                message="psutil process wait failed after signal (non-critical).",
                operation=OPERATION_SYSTEM_PROCESSES_KILL_PROCESS_PSUTIL_WAIT,
                details={"pid": pid},
                level="debug",
            )
        return (True, f"Signal {signal_to_send} sent to process {pid}.")
    except psutil.NoSuchProcess:
        return (False, f"Process {pid} not found.")
    except psutil.AccessDenied as exception:
        log_exception(
            logger,
            exception,
            message="psutil access denied for PID",
            operation=OPERATION_SYSTEM_PROCESSES_KILL_PROCESS_PSUTIL_ACCESS,
            details={"pid": pid},
            level="warning",
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message="psutil kill failed for PID",
            operation=OPERATION_SYSTEM_PROCESSES_KILL_PROCESS_PSUTIL_KILL,
            details={"pid": pid},
            level="warning",
        )
    return (False, f"Failed to kill process {pid} using psutil.")
