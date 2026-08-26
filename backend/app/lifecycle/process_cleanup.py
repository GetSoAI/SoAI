"""SoAI - Scoped process cleanup after lifecycle shutdown [backend/app/lifecycle/process_cleanup.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import logging
import os

import psutil

from core.concurrency.deadlines import deadline_after
from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.runtime.process_identity import is_soai_owned_process_markers
from core.system.protocols import ManagedProcessProtocol
from core.timing.sleep import sleep_seconds

__all__ = ("cleanup_lingering_processes",)

OPERATION_PROCESS_CLEANUP = "app.lifecycle.process_cleanup"
PROCESS_CLEANUP_EXCEPTIONS: tuple[type[Exception], ...] = (
    psutil.Error,
    *RECOVERABLE_EXCEPTIONS,
)
PROCESS_EXIT_POLL_INTERVAL_SEC = 0.05


def _process_markers(process: psutil.Process) -> list[str]:
    values: list[str] = []
    try:
        values.extend(process.cmdline())
    except psutil.Error as exception:
        values.append(type(exception).__name__)
    try:
        values.append(process.cwd())
    except psutil.Error as exception:
        values.append(type(exception).__name__)
    return values


def _is_soai_owned_process(process: psutil.Process, base_dir: str) -> bool:
    normalized_base = os.path.abspath(base_dir)
    return is_soai_owned_process_markers(_process_markers(process), base_dir=normalized_base)


def _running_processes(processes: list[psutil.Process]) -> list[psutil.Process]:
    running: list[psutil.Process] = []
    for process in processes:
        try:
            if process.is_running() and process.status() != psutil.STATUS_ZOMBIE:
                running.append(process)
        except psutil.Error:
            continue
    return running


def _wait_for_exit(processes: list[psutil.Process], timeout_sec: float) -> list[psutil.Process]:
    deadline = deadline_after(timeout_sec)
    pending = list(processes)
    while pending and not deadline.expired():
        pending = _running_processes(pending)
        if pending:
            sleep_seconds(PROCESS_EXIT_POLL_INTERVAL_SEC)
    return _running_processes(pending)


def _is_transferred_process(
    process: psutil.Process,
    transferred_processes: tuple[ManagedProcessProtocol, ...],
) -> bool:
    for process_handle in transferred_processes:
        if process_handle.pid != process.pid:
            continue
        if process_handle.poll() is None or not _running_processes([process]):
            return True
    return False


def cleanup_lingering_processes(
    *,
    pid: int,
    base_dir: str,
    logger: logging.Logger,
    timeout_sec: float,
    transferred_processes: tuple[ManagedProcessProtocol, ...] = (),
) -> bool:
    try:
        current_process = psutil.Process(pid)
        children = current_process.children(recursive=True)
    except psutil.NoSuchProcess:
        return True
    except PROCESS_CLEANUP_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message="Failed to enumerate lingering child processes.",
            operation=OPERATION_PROCESS_CLEANUP,
            level="error",
        )
        return False
    if not children:
        return True
    owned: list[psutil.Process] = []
    unknown: list[psutil.Process] = []
    for child in children:
        if _is_transferred_process(child, transferred_processes):
            continue
        if _is_soai_owned_process(child, base_dir):
            owned.append(child)
        else:
            unknown.append(child)
    if unknown:
        logger.critical(
            "Found %s lingering child process(es) that are not clearly SoAI-owned; refusing blanket kill.",
            len(unknown),
        )
        for child in unknown[:25]:
            logger.critical(
                "Untracked lingering child process PID %s: %s",
                child.pid,
                _safe_process_name(child),
            )
    for child in owned:
        try:
            child.terminate()
        except psutil.NoSuchProcess:
            continue
        except PROCESS_CLEANUP_EXCEPTIONS as exception:
            log_exception(
                logger,
                exception,
                message="Failed to terminate SoAI-owned child process.",
                operation=OPERATION_PROCESS_CLEANUP,
                details={"pid": child.pid},
                level="error",
            )
    still_running = _wait_for_exit(owned, timeout_sec)
    for child in still_running:
        try:
            child.kill()
        except psutil.NoSuchProcess:
            continue
        except PROCESS_CLEANUP_EXCEPTIONS as exception:
            log_exception(
                logger,
                exception,
                message="Failed to kill SoAI-owned child process.",
                operation=OPERATION_PROCESS_CLEANUP,
                details={"pid": child.pid},
                level="error",
            )
    remaining_owned = _wait_for_exit(still_running, timeout_sec)
    if remaining_owned:
        logger.critical(
            "%s SoAI-owned child process(es) remained alive after forced cleanup.",
            len(remaining_owned),
        )
    return not unknown and not remaining_owned


def _safe_process_name(process: psutil.Process) -> str:
    try:
        return process.name()
    except psutil.Error:
        return "unavailable"
