"""SoAI - Async command output stream draining [backend/core/system/async_command_streams.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.protocols import LoggerProtocol

__all__ = ("drain_async_command_stream",)


async def drain_async_command_stream(
    reader: asyncio.StreamReader | None,
    *,
    chunks: list[str],
    on_line: Callable[[str], Awaitable[None]] | None,
    stream_name: str,
    process: asyncio.subprocess.Process,
    read_timeout_sec: float,
    logger: LoggerProtocol,
    operation: str,
) -> None:
    if reader is None:
        return
    timeout_value = max(0.05, float(read_timeout_sec))
    post_exit_timeouts = 0
    max_post_exit_timeouts = 6
    while True:
        try:
            line = await asyncio.wait_for(reader.readline(), timeout=timeout_value)
        except TimeoutError:
            if process.returncode is not None:
                post_exit_timeouts += 1
                if post_exit_timeouts >= max_post_exit_timeouts:
                    break
            else:
                post_exit_timeouts = 0
            continue
        post_exit_timeouts = 0
        if not line:
            break
        decoded = line.decode("utf-8", errors="replace")
        chunks.append(decoded)
        if on_line is not None:
            try:
                await on_line(decoded.rstrip("\r\n"))
            except RECOVERABLE_EXCEPTIONS as exception:
                log_exception(
                    logger,
                    exception,
                    message="Async command output callback failed.",
                    operation=operation,
                    details={"stream": stream_name},
                    level="warning",
                )
                raise
