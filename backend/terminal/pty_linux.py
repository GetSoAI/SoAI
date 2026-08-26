"""SoAI - Linux PTY implementation [backend/terminal/pty_linux.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import errno
import fcntl
import os
import pty
import select
import struct
import termios

from core.filesystem.open_files import open_text
from terminal.shell_command import PTYShellCommand

__all__ = (
    "has_child_processes",
    "read_pty",
    "read_pty_nonblocking",
    "resize_pty",
    "spawn_pty",
)


def spawn_pty(
    shell_command: PTYShellCommand,
    cols: int,
    rows: int,
    cwd: str,
    env: dict[str, str],
) -> tuple[int, int]:
    master_fd, slave_fd = pty.openpty()
    slave_name = os.ttyname(slave_fd)
    winsize = struct.pack("HHHH", rows, cols, 0, 0)
    fcntl.ioctl(slave_fd, termios.TIOCSWINSZ, winsize)
    pid = os.fork()
    if pid == 0:
        try:
            os.close(master_fd)
            os.setsid()
            controlling_fd = os.open(slave_name, os.O_RDWR)
            fcntl.ioctl(controlling_fd, termios.TIOCSCTTY, 0)
            os.dup2(controlling_fd, 0)
            os.dup2(controlling_fd, 1)
            os.dup2(controlling_fd, 2)
            if slave_fd > 2:
                os.close(slave_fd)
            if controlling_fd > 2:
                os.close(controlling_fd)
            os.tcsetpgrp(0, os.getpgrp())
            os.chdir(cwd)
            os.execvpe(shell_command.executable_path, list(shell_command.argv), env)
        except (OSError, ValueError) as exception:
            try:
                message = f"PTY exec failed: {type(exception).__name__}: {exception}\n"
                os.write(2, message.encode("utf-8", errors="replace"))
            except OSError:
                os._exit(127)
            os._exit(127)
    os.close(slave_fd)
    flags = fcntl.fcntl(master_fd, fcntl.F_GETFL)
    fcntl.fcntl(master_fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
    return (master_fd, pid)


def resize_pty(master_fd: int, cols: int, rows: int) -> None:
    winsize = struct.pack("HHHH", rows, cols, 0, 0)
    fcntl.ioctl(master_fd, termios.TIOCSWINSZ, winsize)


def read_pty(master_fd: int, size: int = 4096) -> bytes | None:
    try:
        ready, _, _ = select.select([master_fd], [], [], 0.1)
        if not ready:
            return b""
        data = os.read(master_fd, size)
        if not data:
            return None
        return data
    except BlockingIOError:
        return b""
    except ValueError:
        return None
    except OSError as exception:
        return _resolve_read_error(exception)


def read_pty_nonblocking(master_fd: int, size: int = 4096) -> bytes | None:
    try:
        data = os.read(master_fd, size)
        if not data:
            return None
        return data
    except BlockingIOError:
        return b""
    except ValueError:
        return None
    except OSError as exception:
        return _resolve_read_error(exception)


def _resolve_read_error(exception: OSError) -> bytes | None:
    if exception.errno in {errno.EAGAIN, errno.EWOULDBLOCK, errno.EINTR}:
        return b""
    if exception.errno in {errno.EIO, errno.EBADF}:
        return None
    raise exception


def has_child_processes(pid: int) -> bool:
    try:
        children_path = f"/proc/{pid}/task/{pid}/children"
        with open_text(children_path, encoding="utf-8") as file_handle:
            content = file_handle.read().strip()
            return bool(content)
    except OSError:
        return False
