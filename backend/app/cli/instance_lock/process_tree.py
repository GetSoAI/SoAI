"""SoAI - Process discovery and termination for instance locking [backend/app/cli/instance_lock/process_tree.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import logging
import os

import psutil

from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import StateError

__all__ = (
    "force_kill_process_native",
    "get_current_process_tree_pids",
    "terminate_process_native",
)

OPERATION_APP_CLI_INSTANCE_LOCK_PROCESS_TREE_SIGNAL_PROCESS_TREE = (
    "app.cli.instance_lock.process_tree.signal_process_tree"
)


def _build_process_tree(pid: int) -> list[psutil.Process]:
    try:
        process = psutil.Process(pid)
    except psutil.NoSuchProcess:
        return []
    processes = [process]
    try:
        processes.extend(process.children(recursive=True))
    except psutil.Error:
        return processes
    return processes


def get_current_process_tree_pids(*, logger: logging.Logger) -> set[int]:
    current_pid = os.getpid()
    protected_pids: set[int] = {current_pid}
    try:
        process = psutil.Process(current_pid)
    except psutil.Error:
        return protected_pids
    try:
        for parent in process.parents():
            try:
                parent_pid = parent.pid
            except AttributeError:
                parent_pid = None
            if isinstance(parent_pid, int) and parent_pid > 0:
                protected_pids.add(parent_pid)
    except psutil.Error:
        logger.debug("Failed to enumerate parent processes for PID %s", current_pid)
    try:
        for child in process.children(recursive=True):
            try:
                child_pid = child.pid
            except AttributeError:
                child_pid = None
            if isinstance(child_pid, int) and child_pid > 0:
                protected_pids.add(child_pid)
    except psutil.Error:
        logger.debug("Failed to enumerate child processes for PID %s", current_pid)
    return protected_pids


def terminate_process_native(
    pid: int,
    *,
    logger: logging.Logger,
    exclude_pids: set[int] | None = None,
) -> bool:
    return _signal_process_tree(
        pid,
        logger=logger,
        exclude_pids=exclude_pids,
        action="terminate",
        denied_message="Access denied terminating process (non-critical).",
        denied_operation="main.terminate_process.psutil",
        failure_message="Failed to terminate process via psutil (non-critical).",
        failure_operation="main.terminate_process.psutil",
    )


def force_kill_process_native(
    pid: int,
    *,
    logger: logging.Logger,
    exclude_pids: set[int] | None = None,
) -> bool:
    return _signal_process_tree(
        pid,
        logger=logger,
        exclude_pids=exclude_pids,
        action="kill",
        denied_message="Access denied killing process (non-critical).",
        denied_operation="main.force_kill_process.psutil",
        failure_message="Failed to kill process via psutil (non-critical).",
        failure_operation="main.force_kill_process.psutil",
    )


def _signal_process_tree(
    pid: int,
    *,
    logger: logging.Logger,
    exclude_pids: set[int] | None,
    action: str,
    denied_message: str,
    denied_operation: str,
    failure_message: str,
    failure_operation: str,
) -> bool:
    protected = exclude_pids or set()
    processes = _build_process_tree(pid)
    if not processes:
        return False
    sent = False
    for proc in processes:
        try:
            proc_pid_value = proc.pid
        except AttributeError:
            proc_pid_value = None
        if proc_pid_value in protected:
            continue
        try:
            if action == "terminate":
                proc.terminate()
            elif action == "kill":
                proc.kill()
            else:
                raise StateError(f"Unsupported process signal action: {action}")
            sent = True
        except psutil.NoSuchProcess:
            continue
        except psutil.AccessDenied as exception:
            log_handled_exception(
                logger,
                exception,
                message="Process signal denied (non-critical).",
                operation=OPERATION_APP_CLI_INSTANCE_LOCK_PROCESS_TREE_SIGNAL_PROCESS_TREE,
                details={
                    "pid": proc_pid_value if isinstance(proc_pid_value, int) else pid,
                    "denied_message": denied_message,
                    "denied_operation": denied_operation,
                },
                level="debug",
            )
        except psutil.Error as exception:
            log_handled_exception(
                logger,
                exception,
                message="Process signal failed (non-critical).",
                operation=OPERATION_APP_CLI_INSTANCE_LOCK_PROCESS_TREE_SIGNAL_PROCESS_TREE,
                details={
                    "pid": proc_pid_value if isinstance(proc_pid_value, int) else pid,
                    "failure_message": failure_message,
                    "failure_operation": failure_operation,
                },
                level="debug",
            )
    return sent
