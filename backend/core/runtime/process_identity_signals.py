"""SoAI - Identity-verified process signal helpers [backend/core/runtime/process_identity_signals.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os
import signal
import sys
from dataclasses import dataclass

import psutil

from core.timing.constants import SHORT_POLL_INTERVAL_SEC

__all__ = (
    "ProcessIdentitySignalResult",
    "process_identity_matches",
    "read_process_create_time_ms",
    "send_signal_to_process_matching_identity",
    "send_signal_to_process_matching_identity_blocking",
    "wait_for_process_identity_mismatch_or_gone",
)


@dataclass(frozen=True, slots=True)
class ProcessIdentitySignalResult:
    success: bool
    process_not_found: bool
    identity_mismatched: bool


def read_process_create_time_ms(process: psutil.Process) -> int:
    return int(process.create_time() * 1000.0)


def process_identity_matches(process: psutil.Process, expected_create_time_ms: int) -> bool:
    return read_process_create_time_ms(process) == expected_create_time_ms


def send_signal_to_process_matching_identity_blocking(
    process: psutil.Process,
    expected_create_time_ms: int,
    signal_number: int,
) -> ProcessIdentitySignalResult:
    try:
        pidfd_result = _send_signal_with_pidfd_if_available(
            process,
            expected_create_time_ms,
            signal_number,
        )
        if pidfd_result is not None:
            return pidfd_result
        fresh_process = psutil.Process(process.pid)
        if not process_identity_matches(fresh_process, expected_create_time_ms):
            return ProcessIdentitySignalResult(
                success=False,
                process_not_found=False,
                identity_mismatched=True,
            )
        fresh_process.send_signal(signal_number)
        return ProcessIdentitySignalResult(
            success=True,
            process_not_found=False,
            identity_mismatched=False,
        )
    except psutil.NoSuchProcess:
        return ProcessIdentitySignalResult(
            success=False,
            process_not_found=True,
            identity_mismatched=False,
        )


async def send_signal_to_process_matching_identity(
    pid: int,
    expected_create_time_ms: int,
    signal_number: int,
) -> ProcessIdentitySignalResult:
    return await asyncio.to_thread(
        _send_signal_to_pid_matching_identity_blocking,
        pid,
        expected_create_time_ms,
        signal_number,
    )


async def wait_for_process_identity_mismatch_or_gone(
    pid: int,
    expected_create_time_ms: int,
    *,
    timeout_sec: float,
) -> bool:
    deadline = asyncio.get_running_loop().time() + timeout_sec
    while asyncio.get_running_loop().time() < deadline:
        try:
            process = psutil.Process(pid)
            if not process_identity_matches(process, expected_create_time_ms):
                return True
        except psutil.NoSuchProcess:
            return True
        except psutil.AccessDenied:
            return False
        await asyncio.sleep(SHORT_POLL_INTERVAL_SEC)
    return False


def _send_signal_to_pid_matching_identity_blocking(
    pid: int,
    expected_create_time_ms: int,
    signal_number: int,
) -> ProcessIdentitySignalResult:
    try:
        process = psutil.Process(pid)
        return send_signal_to_process_matching_identity_blocking(
            process,
            expected_create_time_ms,
            signal_number,
        )
    except psutil.NoSuchProcess:
        return ProcessIdentitySignalResult(
            success=False,
            process_not_found=True,
            identity_mismatched=False,
        )


def _send_signal_with_pidfd_if_available(
    process: psutil.Process,
    expected_create_time_ms: int,
    signal_number: int,
) -> ProcessIdentitySignalResult | None:
    if sys.platform != "linux":
        return None
    try:
        file_descriptor = os.pidfd_open(process.pid)
    except AttributeError:
        return None
    except ProcessLookupError:
        return ProcessIdentitySignalResult(
            success=False,
            process_not_found=True,
            identity_mismatched=False,
        )
    try:
        fresh_process = psutil.Process(process.pid)
        if not process_identity_matches(fresh_process, expected_create_time_ms):
            return ProcessIdentitySignalResult(
                success=False,
                process_not_found=False,
                identity_mismatched=True,
            )
        signal.pidfd_send_signal(file_descriptor, signal_number)
        return ProcessIdentitySignalResult(
            success=True,
            process_not_found=False,
            identity_mismatched=False,
        )
    except AttributeError:
        return None
    except ProcessLookupError:
        return ProcessIdentitySignalResult(
            success=False,
            process_not_found=True,
            identity_mismatched=False,
        )
    finally:
        os.close(file_descriptor)
