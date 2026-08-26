"""SoAI - Background process launching utilities [backend/core/system/process_launcher.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import logging
import subprocess
import threading
from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING

from core.system.protocols import StartupInfoProtocol
from core.system.subprocess_platform import (
    resolve_subprocess_creationflags,
    resolve_subprocess_startupinfo,
)

if TYPE_CHECKING:
    type StdStream = int | None
    type ManagedProcess = subprocess.Popen[str] | subprocess.Popen[bytes]

__all__ = (
    "DEVNULL_STREAM",
    "SUBPROCESS_RECOVERABLE_EXCEPTIONS",
    "spawn_background_process",
    "spawn_handoff_process",
    "spawn_managed_process",
)

LOGGER_NAME = "SoAI.core.system.process_launcher"
DEVNULL_STREAM = subprocess.DEVNULL
SUBPROCESS_RECOVERABLE_EXCEPTIONS: tuple[type[Exception], ...] = (
    OSError,
    subprocess.SubprocessError,
)


def spawn_managed_process(
    command: Sequence[str],
    *,
    cwd: str | None = None,
    env: Mapping[str, str] | None = None,
    start_new_session: bool = False,
    creationflags: int = 0,
    close_fds: bool = True,
    stdin: StdStream = None,
    stdout: StdStream = None,
    stderr: StdStream = None,
    text: bool = False,
    bufsize: int = -1,
    encoding: str | None = None,
    errors: str | None = None,
    startupinfo: StartupInfoProtocol | None = None,
) -> ManagedProcess:
    return subprocess.Popen(
        list(command),
        cwd=cwd,
        env=dict(env) if env is not None else None,
        start_new_session=start_new_session,
        creationflags=resolve_subprocess_creationflags(creationflags),
        close_fds=close_fds,
        stdin=stdin,
        stdout=stdout,
        stderr=stderr,
        text=text,
        bufsize=bufsize,
        encoding=encoding,
        errors=errors,
        startupinfo=resolve_subprocess_startupinfo(startupinfo),
    )


def spawn_background_process(
    command: Sequence[str],
    *,
    cwd: str | None = None,
    env: Mapping[str, str] | None = None,
    start_new_session: bool = False,
    creationflags: int = 0,
    close_fds: bool = True,
    stdin: StdStream = None,
    stdout: StdStream = None,
    stderr: StdStream = None,
    text: bool = False,
    bufsize: int = -1,
    encoding: str | None = None,
    errors: str | None = None,
    startupinfo: StartupInfoProtocol | None = None,
) -> None:
    if subprocess.PIPE in (stdout, stderr):
        raise ValueError(
            "spawn_background_process does not support subprocess.PIPE for stdout or stderr; use spawn_managed_process and drain pipes explicitly.",
        )
    logger = logging.getLogger(LOGGER_NAME)
    process_handle = spawn_managed_process(
        command,
        cwd=cwd,
        env=env,
        start_new_session=start_new_session,
        creationflags=creationflags,
        close_fds=close_fds,
        stdin=stdin,
        stdout=stdout,
        stderr=stderr,
        text=text,
        bufsize=bufsize,
        encoding=encoding,
        errors=errors,
        startupinfo=startupinfo,
    )
    first_argv = command[0] if command else "unknown"
    command_label = first_argv.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]

    def _run_process() -> None:
        try:
            with process_handle:
                process_handle.wait()
        except (OSError, ValueError, subprocess.SubprocessError, RuntimeError) as exception:
            logger.error(
                "Background process thread failed for command: %s",
                list(command),
                exc_info=(type(exception), exception, exception.__traceback__),
            )

    thread = threading.Thread(
        target=_run_process,
        name=f"soai-bg-proc-{command_label}-{process_handle.pid}",
        daemon=True,
    )
    thread.start()


def spawn_handoff_process(
    command: Sequence[str],
    *,
    cwd: str | None = None,
    env: Mapping[str, str] | None = None,
    start_new_session: bool = False,
    creationflags: int = 0,
    close_fds: bool = True,
    stdin: StdStream = None,
    stdout: StdStream = None,
    stderr: StdStream = None,
    text: bool = False,
    bufsize: int = -1,
    encoding: str | None = None,
    errors: str | None = None,
    startupinfo: StartupInfoProtocol | None = None,
) -> ManagedProcess:
    if not command:
        raise ValueError("spawn_handoff_process requires a non-empty command.")
    if subprocess.PIPE in (stdin, stdout, stderr):
        raise ValueError(
            "spawn_handoff_process does not support subprocess.PIPE for stdin, stdout, or stderr; use spawn_managed_process and drain pipes explicitly.",
        )
    process_handle = spawn_managed_process(
        command,
        cwd=cwd,
        env=env,
        start_new_session=start_new_session,
        creationflags=creationflags,
        close_fds=close_fds,
        stdin=stdin,
        stdout=stdout,
        stderr=stderr,
        text=text,
        bufsize=bufsize,
        encoding=encoding,
        errors=errors,
        startupinfo=startupinfo,
    )
    return process_handle
