"""SoAI - MCP stdio proxy stdout draining [backend/app/mcp_stdio_proxy_stdout.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import sys

from app.mcp_stdio_proxy_backpressure import put_stdout_line
from core.concurrency.task_groups import DEFAULT_CANCELLATION_TIMEOUT_SEC
from core.errors.exception_logging import log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.protocols import LoggerProtocol

__all__ = (
    "drain_stdout_writer",
    "write_stdout_lines",
)


async def write_stdout_lines(stdout_queue: asyncio.Queue[str]) -> None:
    while True:
        line = await stdout_queue.get()
        if line == "":
            return
        sys.stdout.write(line)
        sys.stdout.write("\n")
        sys.stdout.flush()


async def drain_stdout_writer(
    *,
    stdout_queue: asyncio.Queue[str],
    writer_task: asyncio.Task[None],
    logger: LoggerProtocol,
    operation: str,
) -> bool:
    try:
        await put_stdout_line(stdout_queue, "")
        await asyncio.wait_for(
            asyncio.shield(writer_task),
            timeout=DEFAULT_CANCELLATION_TIMEOUT_SEC,
        )
    except TimeoutError as exception:
        log_handled_exception(
            logger,
            exception,
            message="MCP stdio proxy stdout drain timed out (non-critical).",
            operation=operation,
            level="debug",
        )
        return False
    except asyncio.CancelledError as exception:
        if not writer_task.cancelled():
            raise
        log_handled_exception(
            logger,
            exception,
            message="MCP stdio proxy stdout writer was already cancelled (non-critical).",
            operation=operation,
            level="debug",
        )
        return False
    except RECOVERABLE_EXCEPTIONS as exception:
        log_handled_exception(
            logger,
            exception,
            message="MCP stdio proxy stdout drain failed (non-critical).",
            operation=operation,
            level="debug",
        )
        return writer_task.done()
    return True
