"""SoAI - Terminal types and data classes [backend/terminal/types.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from terminal.internal_protocols import WindowsPTYProtocol

__all__ = ("PTYSession",)


class PTYSession:
    __slots__ = (
        "busy_callback",
        "busy_poll_task",
        "closed",
        "cols",
        "cleanup_lock",
        "exit_callback",
        "is_busy",
        "master_fd",
        "output_callback",
        "pid",
        "read_task",
        "rows",
        "session_id",
        "shell_path",
        "user_id",
    )

    def __init__(
        self,
        session_id: str,
        pid: int,
        master_fd: int | WindowsPTYProtocol,
        shell_path: str,
        cols: int,
        rows: int,
        user_id: int = 0,
        output_callback: Callable[[bytes], None] | None = None,
        exit_callback: Callable[[str, int], None] | None = None,
        busy_callback: Callable[[str, bool], None] | None = None,
        read_task: asyncio.Task[None] | None = None,
        busy_poll_task: asyncio.Task[None] | None = None,
        closed: bool = False,
        is_busy: bool = False,
    ) -> None:
        self.session_id = session_id
        self.pid = pid
        self.master_fd = master_fd
        self.shell_path = shell_path
        self.user_id = user_id
        self.cols = cols
        self.rows = rows
        self.cleanup_lock = asyncio.Lock()
        self.output_callback = output_callback
        self.exit_callback = exit_callback
        self.busy_callback = busy_callback
        self.read_task = read_task
        self.busy_poll_task = busy_poll_task
        self.closed = closed
        self.is_busy = is_busy
