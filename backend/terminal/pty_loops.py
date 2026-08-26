"""SoAI - PTY background loop coroutines [backend/terminal/pty_loops.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import functools
import os
import sys
from collections.abc import Awaitable, Callable
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING

from core.callbacks.invocation import invoke_callback_safe
from core.errors.exception_logging import log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.timing.constants import FILE_LOCK_RETRY_INTERVAL_SEC, SHORT_POLL_INTERVAL_SEC
from terminal.platform_session_validation import (
    require_linux_master_fd,
    require_windows_master_fd,
)
from terminal.session_support import log_terminal_trace

if TYPE_CHECKING:
    from core.logging.protocols import TraceLogger
    from terminal.session_registry import PTYSessionStore
    from terminal.types import PTYSession

__all__ = (
    "run_pty_busy_poll_loop",
    "run_pty_read_loop",
    "shutdown_pty_read_executor",
)

OPERATION_TERMINAL_PTY_LOOPS_BUSY_POLL = "terminal.pty_loops.busy_poll"
OPERATION_TERMINAL_PTY_LOOPS_READ = "terminal.pty_loops.read"
OPERATION_TERMINAL_PTY_LOOPS_READ_ADD_READER = "terminal.pty_loops.read.add_reader"
PTY_LOOP_OPERATION_EXCEPTIONS: tuple[type[Exception], ...] = (
    *RECOVERABLE_EXCEPTIONS,
    OSError,
)


if sys.platform != "win32":
    from terminal.pty_linux import has_child_processes, read_pty, read_pty_nonblocking
else:
    from terminal.pty_windows import read_pty


_PTY_READ_EXECUTOR_WORKERS: int = 16


@functools.cache
def _get_pty_read_executor() -> ThreadPoolExecutor:
    return ThreadPoolExecutor(
        max_workers=_PTY_READ_EXECUTOR_WORKERS,
        thread_name_prefix="soai-pty-read",
    )


def shutdown_pty_read_executor() -> None:
    if _get_pty_read_executor.cache_info().currsize < 1:
        return
    executor = _get_pty_read_executor()
    executor.shutdown(wait=False)
    _get_pty_read_executor.cache_clear()


def _emit_pty_output(session: PTYSession, logger: TraceLogger, data: bytes) -> None:
    invoke_callback_safe(
        session.output_callback,
        logger,
        "terminal.pty_loops.read.output",
        "debug",
        data,
    )


async def run_pty_read_loop(
    session: PTYSession,
    registry: PTYSessionStore,
    on_exit: Callable[[str, int], Awaitable[None]],
    logger: TraceLogger,
) -> None:
    loop = asyncio.get_running_loop()
    if session.closed or (not registry.contains(session.session_id)):
        return
    was_cancelled = False
    reader_added = False
    exit_event = asyncio.Event()
    master_fd_to_remove: int | None = None
    try:
        if sys.platform == "win32":
            while not session.closed and registry.contains(session.session_id):
                try:
                    master_fd = require_windows_master_fd(session.master_fd)
                    data = read_pty(master_fd, 4096)
                    if data is None:
                        log_terminal_trace(
                            logger,
                            f"PTY EOF detected for session {session.session_id}",
                        )
                        break
                    if data:
                        _emit_pty_output(session, logger, data)
                    else:
                        await asyncio.sleep(SHORT_POLL_INTERVAL_SEC)
                except PTY_LOOP_OPERATION_EXCEPTIONS as read_err:
                    if session.closed:
                        break
                    log_handled_exception(
                        logger,
                        read_err,
                        message="PTY read error (non-critical).",
                        operation=OPERATION_TERMINAL_PTY_LOOPS_READ,
                        details={"session_id": session.session_id},
                        level="trace",
                    )
                    await asyncio.sleep(SHORT_POLL_INTERVAL_SEC)
        else:
            linux_master_fd = require_linux_master_fd(session.master_fd)
            use_executor = False

            def _on_read_ready(master_fd_value: int = linux_master_fd) -> None:
                if (
                    exit_event.is_set()
                    or session.closed
                    or (not registry.contains(session.session_id))
                ):
                    exit_event.set()
                    return
                try:
                    data = read_pty_nonblocking(master_fd_value, 4096)
                except PTY_LOOP_OPERATION_EXCEPTIONS as read_err:
                    log_handled_exception(
                        logger,
                        read_err,
                        message="PTY read error (non-critical).",
                        operation=OPERATION_TERMINAL_PTY_LOOPS_READ,
                        details={"session_id": session.session_id},
                        level="trace",
                    )
                    return
                if data is None:
                    log_terminal_trace(logger, f"PTY EOF detected for session {session.session_id}")
                    exit_event.set()
                    return
                if data:
                    _emit_pty_output(session, logger, data)

            try:
                loop.add_reader(linux_master_fd, _on_read_ready)
                reader_added = True
                master_fd_to_remove = linux_master_fd
            except PermissionError as exception:
                use_executor = True
                log_handled_exception(
                    logger,
                    exception,
                    message="Event-loop FD reader registration not permitted; falling back to thread-based PTY reads (non-critical).",
                    operation=OPERATION_TERMINAL_PTY_LOOPS_READ_ADD_READER,
                    details={"session_id": session.session_id, "master_fd": linux_master_fd},
                    level="debug",
                )

            if use_executor:
                executor = _get_pty_read_executor()
                while (
                    (not exit_event.is_set())
                    and (not session.closed)
                    and registry.contains(session.session_id)
                ):
                    data = await loop.run_in_executor(executor, read_pty, linux_master_fd, 4096)
                    if data is None:
                        log_terminal_trace(
                            logger,
                            f"PTY EOF detected for session {session.session_id}",
                        )
                        exit_event.set()
                        break
                    if data:
                        _emit_pty_output(session, logger, data)
                    else:
                        await asyncio.sleep(SHORT_POLL_INTERVAL_SEC)
            else:
                while (
                    (not exit_event.is_set())
                    and (not session.closed)
                    and registry.contains(session.session_id)
                ):
                    await asyncio.sleep(SHORT_POLL_INTERVAL_SEC)
    except asyncio.CancelledError:
        was_cancelled = True
        log_terminal_trace(logger, f"PTY read loop cancelled for session {session.session_id}")
    finally:
        if reader_added and (master_fd_to_remove is not None) and sys.platform != "win32":
            loop.remove_reader(master_fd_to_remove)
        if not was_cancelled and (not session.closed):
            exit_code = _resolve_exit_code(session, logger)
            invoke_callback_safe(
                session.exit_callback,
                logger,
                "terminal.pty_loops.read.exit",
                "debug",
                session.session_id,
                exit_code,
            )
            await on_exit(session.session_id, exit_code)


def _resolve_exit_code(session: PTYSession, logger: TraceLogger) -> int:
    if sys.platform == "win32":
        try:
            master_fd = require_windows_master_fd(session.master_fd)
            exit_status = master_fd.get_exitstatus()
            if isinstance(exit_status, int):
                return exit_status
        except PTY_LOOP_OPERATION_EXCEPTIONS as exception:
            log_terminal_trace(logger, f"Failed to resolve Windows PTY exit code: {exception}")
        return 0
    try:
        _, status = os.waitpid(session.pid, os.WNOHANG)
        if os.WIFEXITED(status):
            return os.WEXITSTATUS(status)
        return 0
    except OSError as exception:
        log_terminal_trace(logger, f"Failed to resolve PTY exit code: {exception}")
        return 0


async def run_pty_busy_poll_loop(
    session: PTYSession,
    registry: PTYSessionStore,
    logger: TraceLogger,
) -> None:
    if sys.platform == "win32":
        return
    try:
        while not session.closed and registry.contains(session.session_id):
            try:
                has_children = has_child_processes(session.pid)
                if has_children != session.is_busy:
                    session.is_busy = has_children
                    invoke_callback_safe(
                        session.busy_callback,
                        logger,
                        "terminal.pty_loops.busy_poll",
                        "debug",
                        session.session_id,
                        has_children,
                    )
            except PTY_LOOP_OPERATION_EXCEPTIONS as poll_err:
                if session.closed:
                    break
                log_handled_exception(
                    logger,
                    poll_err,
                    message="PTY busy poll error (non-critical).",
                    operation=OPERATION_TERMINAL_PTY_LOOPS_BUSY_POLL,
                    details={"session_id": session.session_id},
                    level="trace",
                )
            await asyncio.sleep(FILE_LOCK_RETRY_INTERVAL_SEC)
    except asyncio.CancelledError:
        log_terminal_trace(logger, f"PTY busy poll cancelled for session {session.session_id}")
