"""SoAI - Identity-verified process tree termination [backend/core/runtime/process_identity_kill.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import signal
from dataclasses import dataclass
from typing import TYPE_CHECKING

import psutil

from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.runtime.process_identity_signals import (
    process_identity_matches,
    read_process_create_time_ms,
    send_signal_to_process_matching_identity_blocking,
)

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol

__all__ = ("ProcessTreeKillResult", "force_kill_process_tree_matching_identity")

OPERATION_CORE_RUNTIME_PROCESS_IDENTITY_KILL = (
    "core.runtime.process_identity_kill.kill_process_tree"
)


@dataclass(frozen=True, slots=True)
class ProcessTreeKillResult:
    success: bool
    process_not_found: bool
    identity_mismatched: bool


def _kill_identity_checked_process(process: psutil.Process, expected_create_time_ms: int) -> bool:
    result = send_signal_to_process_matching_identity_blocking(
        process,
        expected_create_time_ms,
        signal.SIGKILL,
    )
    if result.process_not_found:
        raise psutil.NoSuchProcess(process.pid)
    return result.success


def _kill_matching_process_tree_blocking(
    pid: int,
    expected_create_time_ms: int,
    name_for_logging: str,
    logger: LoggerProtocol,
) -> ProcessTreeKillResult:
    try:
        parent = psutil.Process(pid)
        if not process_identity_matches(parent, expected_create_time_ms):
            return _identity_mismatch_result(pid, name_for_logging, logger)
        children = _resolve_child_identities(parent)
        parent_identity_mismatched = not process_identity_matches(
            parent,
            expected_create_time_ms,
        )
        killed_processes: list[psutil.Process] = []
        parent_not_found = False
        if not parent_identity_mismatched:
            try:
                if not _kill_identity_checked_process(parent, expected_create_time_ms):
                    parent_identity_mismatched = True
                else:
                    killed_processes.append(parent)
            except psutil.NoSuchProcess:
                parent_not_found = True
        for child, child_create_time_ms in children:
            try:
                if _kill_identity_checked_process(child, child_create_time_ms):
                    killed_processes.append(child)
            except psutil.NoSuchProcess:
                continue
        if parent_identity_mismatched and not killed_processes:
            return _identity_mismatch_result(pid, name_for_logging, logger)
        if parent_not_found and not killed_processes:
            logger.warning(
                "Process with PID %s for '%s' not found via psutil. It may have already terminated.",
                pid,
                name_for_logging,
            )
            return ProcessTreeKillResult(
                success=True,
                process_not_found=True,
                identity_mismatched=False,
            )
        psutil.wait_procs(killed_processes, timeout=3.0)
        logger.info(
            "Successfully killed identity-verified process tree for '%s' (PID: %s).",
            name_for_logging,
            pid,
        )
        return ProcessTreeKillResult(
            success=True,
            process_not_found=False,
            identity_mismatched=False,
        )
    except psutil.AccessDenied as exception:
        log_exception(
            logger,
            exception,
            message=f"Access denied during identity-verified process cleanup for PID {pid}",
            operation=OPERATION_CORE_RUNTIME_PROCESS_IDENTITY_KILL,
        )
        return ProcessTreeKillResult(
            success=False,
            process_not_found=False,
            identity_mismatched=False,
        )
    except psutil.NoSuchProcess:
        logger.warning(
            "Process with PID %s for '%s' not found via psutil. It may have already terminated.",
            pid,
            name_for_logging,
        )
        return ProcessTreeKillResult(
            success=True,
            process_not_found=True,
            identity_mismatched=False,
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message=f"Failed to kill identity-verified process tree for PID {pid}",
            operation=OPERATION_CORE_RUNTIME_PROCESS_IDENTITY_KILL,
        )
        return ProcessTreeKillResult(
            success=False,
            process_not_found=False,
            identity_mismatched=False,
        )


def _resolve_child_identities(parent: psutil.Process) -> list[tuple[psutil.Process, int]]:
    children: list[tuple[psutil.Process, int]] = []
    for child in parent.children(recursive=True):
        try:
            children.append((child, read_process_create_time_ms(child)))
        except psutil.NoSuchProcess:
            continue
    return children


def _identity_mismatch_result(
    pid: int,
    name_for_logging: str,
    logger: LoggerProtocol,
) -> ProcessTreeKillResult:
    logger.warning(
        "Process identity mismatch for '%s' (PID: %s); refusing to kill.",
        name_for_logging,
        pid,
    )
    return ProcessTreeKillResult(
        success=False,
        process_not_found=False,
        identity_mismatched=True,
    )


async def force_kill_process_tree_matching_identity(
    pid: int | None,
    expected_create_time_ms: int,
    name_for_logging: str,
    logger: LoggerProtocol,
) -> ProcessTreeKillResult:
    if not pid:
        logger.warning("Cannot force-kill '%s': Invalid PID (None or 0).", name_for_logging)
        return ProcessTreeKillResult(
            success=False,
            process_not_found=False,
            identity_mismatched=False,
        )
    logger.critical(
        "Force-killing identity-verified process '%s' with PID: %s.",
        name_for_logging,
        pid,
    )
    return await asyncio.to_thread(
        _kill_matching_process_tree_blocking,
        pid,
        expected_create_time_ms,
        name_for_logging,
        logger,
    )
