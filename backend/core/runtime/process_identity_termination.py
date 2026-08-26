"""SoAI - Identity-verified graceful process termination [backend/core/runtime/process_identity_termination.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import signal
from dataclasses import dataclass
from typing import TYPE_CHECKING

import psutil

from core.errors.exception_logging import log_exception
from core.runtime.process_identity_kill import force_kill_process_tree_matching_identity
from core.runtime.process_identity_signals import (
    send_signal_to_process_matching_identity,
    wait_for_process_identity_mismatch_or_gone,
)

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol

__all__ = (
    "ProcessIdentityTerminationResult",
    "terminate_process_matching_identity",
)

OPERATION_CORE_RUNTIME_PROCESS_IDENTITY_TERMINATION = (
    "core.runtime.process_identity_termination.terminate_process"
)


@dataclass(frozen=True, slots=True)
class ProcessIdentityTerminationResult:
    terminated: bool


async def terminate_process_matching_identity(
    pid: int,
    expected_create_time_ms: int,
    name_for_logging: str,
    logger: LoggerProtocol,
    *,
    graceful_timeout_sec: float,
    force_timeout_sec: float,
) -> ProcessIdentityTerminationResult:
    try:
        graceful_signal = await send_signal_to_process_matching_identity(
            pid,
            expected_create_time_ms,
            signal.SIGTERM,
        )
    except psutil.AccessDenied as exception:
        log_exception(
            logger,
            exception,
            message=f"Access denied during identity-verified graceful termination for PID {pid}",
            operation=OPERATION_CORE_RUNTIME_PROCESS_IDENTITY_TERMINATION,
        )
        return ProcessIdentityTerminationResult(terminated=False)
    if graceful_signal.process_not_found:
        return ProcessIdentityTerminationResult(terminated=True)
    if graceful_signal.identity_mismatched:
        logger.warning(
            "Process identity mismatch for '%s' (PID: %s); refusing graceful termination.",
            name_for_logging,
            pid,
        )
        return ProcessIdentityTerminationResult(terminated=False)
    if not graceful_signal.success:
        return ProcessIdentityTerminationResult(terminated=False)
    if await wait_for_process_identity_mismatch_or_gone(
        pid,
        expected_create_time_ms,
        timeout_sec=graceful_timeout_sec,
    ):
        logger.info(
            "Gracefully terminated identity-verified process '%s' with PID: %s.",
            name_for_logging,
            pid,
        )
        return ProcessIdentityTerminationResult(terminated=True)
    force_result = await force_kill_process_tree_matching_identity(
        pid,
        expected_create_time_ms,
        name_for_logging,
        logger,
    )
    if force_result.process_not_found:
        return ProcessIdentityTerminationResult(terminated=True)
    if force_result.identity_mismatched:
        return ProcessIdentityTerminationResult(terminated=False)
    if not force_result.success:
        return ProcessIdentityTerminationResult(terminated=False)
    terminated = await wait_for_process_identity_mismatch_or_gone(
        pid,
        expected_create_time_ms,
        timeout_sec=force_timeout_sec,
    )
    return ProcessIdentityTerminationResult(terminated=terminated)
