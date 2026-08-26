"""SoAI - Cancellable media subprocess execution [backend/core/media/process_runtime.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import subprocess
from typing import TYPE_CHECKING

from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.errors.exceptions import ProcessError, ServiceUnavailableError, SoAITimeoutError
from core.errors.unexpected_exceptions import HANDLED_RUNTIME_EXCEPTIONS
from core.system.async_process_spawning import spawn_async_process
from core.timing.constants import LOCAL_IO_TIMEOUT_SEC

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = ("media_process_base_argv", "run_media_process")


def media_process_base_argv() -> list[str]:
    return ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y"]


async def _terminate_process(process: asyncio.subprocess.Process) -> None:
    try:
        process.terminate()
    except ProcessLookupError:
        return
    try:
        await asyncio.wait_for(process.wait(), timeout=LOCAL_IO_TIMEOUT_SEC)
    except TimeoutError:
        try:
            process.kill()
        except ProcessLookupError:
            return
        try:
            await asyncio.wait_for(process.wait(), timeout=LOCAL_IO_TIMEOUT_SEC)
        except ProcessLookupError:
            return
        except TimeoutError as exception:
            raise SoAITimeoutError(
                "Media process termination timed out.",
                cause=exception,
            ) from exception


async def run_media_process(
    argv: Sequence[str],
    *,
    timeout_seconds: float,
    dependency_name: str,
    operation_name: str,
    capture_stdout: bool,
) -> bytes:
    try:
        process = await spawn_async_process(
            argv,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE if capture_stdout else subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
    except FileNotFoundError as exception:
        raise ServiceUnavailableError(
            f"Media extraction requires {dependency_name}.",
            cause=exception,
        ) from exception
    try:
        try:
            stdout_bytes, _stderr_bytes = await asyncio.wait_for(
                process.communicate(),
                timeout=max(0.001, timeout_seconds),
            )
        except TimeoutError as exception:
            timeout_error = SoAITimeoutError(f"{operation_name} timed out.", cause=exception)
            try:
                await _terminate_process(process)
            except HANDLED_RUNTIME_EXCEPTIONS as cleanup_exception:
                timeout_error.add_note(f"Media process cleanup failed: {cleanup_exception}")
            raise timeout_error from exception
    except asyncio.CancelledError as exception:
        try:
            await uncancel_then_cleanup(_terminate_process(process))
        except HANDLED_RUNTIME_EXCEPTIONS as cleanup_exception:
            exception.add_note(f"Media process cleanup failed: {cleanup_exception}")
        raise
    if process.returncode != 0:
        raise ProcessError(f"{operation_name} failed.")
    return stdout_bytes or b""
