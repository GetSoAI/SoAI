"""SoAI - PTY I/O operations with platform dispatch [backend/terminal/pty_io.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os
import sys

from core.errors.exception_logging import log_exception
from core.errors.exceptions import StateError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.terminal.pty_validation import clamp_pty_dimensions
from terminal.dependencies import PTYIOHandlerDependencies
from terminal.platform_session_validation import (
    require_linux_master_fd,
    require_windows_master_fd,
)
from terminal.types import PTYSession

__all__ = ("PTYIOHandler",)

OPERATION_TERMINAL_PTY_IO_RESIZE = "terminal.pty_io.resize"
OPERATION_TERMINAL_PTY_IO_WRITE_INPUT = "terminal.pty_io.write_input"
PTY_IO_OPERATION_EXCEPTIONS: tuple[type[Exception], ...] = (
    *RECOVERABLE_EXCEPTIONS,
    OSError,
    RuntimeError,
    ValueError,
)


if sys.platform == "win32":
    from terminal.pty_windows import close_pty
else:
    from terminal.pty_linux import resize_pty
    from terminal.pty_linux_cleanup import close_pty


class PTYIOHandler:

    def __init__(self, deps: PTYIOHandlerDependencies) -> None:
        self._logger = deps.logger

    async def write_input(self, session: PTYSession, data: bytes) -> None:
        try:
            loop = asyncio.get_running_loop()
            if sys.platform == "win32":
                master_fd = require_windows_master_fd(session.master_fd)
                decoded = data.decode("utf-8", errors="replace")
                await loop.run_in_executor(None, master_fd.write, decoded)
            else:
                master_fd = require_linux_master_fd(session.master_fd)
                await loop.run_in_executor(None, os.write, master_fd, data)
        except PTY_IO_OPERATION_EXCEPTIONS as exception:
            log_exception(
                self._logger,
                exception,
                message="Failed to write to PTY",
                operation=OPERATION_TERMINAL_PTY_IO_WRITE_INPUT,
            )
            raise StateError(f"Failed to write to PTY: {exception}") from exception

    async def resize(self, session: PTYSession, cols: int, rows: int) -> None:
        cols, rows = clamp_pty_dimensions(cols, rows)
        try:
            loop = asyncio.get_running_loop()
            if sys.platform == "win32":
                master_fd = require_windows_master_fd(session.master_fd)
                await loop.run_in_executor(None, master_fd.set_size, cols, rows)
            else:
                master_fd = require_linux_master_fd(session.master_fd)
                await loop.run_in_executor(None, resize_pty, master_fd, cols, rows)
            session.cols = cols
            session.rows = rows
        except PTY_IO_OPERATION_EXCEPTIONS as exception:
            log_exception(
                self._logger,
                exception,
                message="Failed to resize PTY",
                operation=OPERATION_TERMINAL_PTY_IO_RESIZE,
            )
            raise StateError(f"Failed to resize PTY: {exception}") from exception

    async def close_resources(self, session: PTYSession) -> None:
        loop = asyncio.get_running_loop()
        if sys.platform == "win32":
            master_fd = require_windows_master_fd(session.master_fd)
            await loop.run_in_executor(None, close_pty, master_fd)
            return
        master_fd = require_linux_master_fd(session.master_fd)
        await loop.run_in_executor(None, close_pty, master_fd, session.pid)
