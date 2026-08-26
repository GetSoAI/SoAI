"""SoAI - Cancellable async command capture [backend/core/system/async_process_capture.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Mapping, Sequence

from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.process.termination import terminate_subprocess_gracefully
from core.system.async_process_spawning import spawn_async_process
from core.system.commands import CommandResult
from core.system.subprocess_platform import windows_no_window_creationflags

__all__ = ("run_argv_capture_async",)

LOGGER_NAME = "SoAI.core.system.async_process_capture"


async def run_argv_capture_async(
    argv: Sequence[str],
    *,
    timeout: float | None,
    env: Mapping[str, str] | None = None,
    cwd: str | None = None,
    encoding: str = "utf-8",
    errors: str = "replace",
) -> CommandResult:
    try:
        process = await spawn_async_process(
            argv,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
            cwd=cwd,
            creationflags=windows_no_window_creationflags(),
        )
    except OSError as exception:
        return CommandResult(stdout="", return_code=127, stderr=f"Command not found: {exception}")
    try:
        if timeout is None:
            stdout_bytes, stderr_bytes = await process.communicate()
        else:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                process.communicate(),
                timeout=max(0.1, float(timeout)),
            )
    except TimeoutError:
        await _terminate_process(process, operation="core.system.async_process_capture.timeout")
        timeout_value = timeout if timeout is not None else 0.0
        return CommandResult(
            stdout="",
            return_code=124,
            stderr=f"Timeout after {timeout_value}s",
        )
    except asyncio.CancelledError:
        await _terminate_process(process, operation="core.system.async_process_capture.cancelled")
        raise
    return CommandResult(
        stdout=stdout_bytes.decode(encoding, errors=errors),
        return_code=int(process.returncode or 0),
        stderr=stderr_bytes.decode(encoding, errors=errors),
    )


async def _terminate_process(process: asyncio.subprocess.Process, *, operation: str) -> None:
    if process.returncode is not None:
        return
    try:
        await terminate_subprocess_gracefully(
            process,
            logger=get_logger(LOGGER_NAME),
            operation=operation,
        )
    except RECOVERABLE_EXCEPTIONS:
        if process.returncode is None:
            raise
