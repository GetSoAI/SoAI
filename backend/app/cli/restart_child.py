"""SoAI - Windows restart child launcher [backend/app/cli/restart_child.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import sys
from collections.abc import Sequence

import psutil

from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.filesystem.open_files import open_text
from core.system.process_launcher import (
    SUBPROCESS_RECOVERABLE_EXCEPTIONS,
    spawn_handoff_process,
)
from core.timing.formatting import utc_now_iso

__all__ = ("main",)

PARENT_EXIT_TIMEOUT_SECONDS: float = 30.0
PARENT_CREATE_TIME_TOLERANCE_SECONDS: float = 0.001
MINIMUM_ARGUMENT_COUNT: int = 6
RESTART_CHILD_EXCEPTIONS: tuple[type[BaseException], ...] = (
    *RECOVERABLE_EXCEPTIONS,
    *SUBPROCESS_RECOVERABLE_EXCEPTIONS,
    RuntimeError,
    psutil.Error,
)


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) < MINIMUM_ARGUMENT_COUNT:
        sys.stderr.write(
            f"Restart child expected at least {MINIMUM_ARGUMENT_COUNT} arguments, got {len(args)}.\n",
        )
        return 2
    parent_pid_text, parent_create_time_text, cwd_path, creation_flags_text, error_log_path = args[
        :5
    ]
    relaunch_args = args[5:]
    try:
        parent_pid = int(parent_pid_text)
        parent_create_time = float(parent_create_time_text)
        creation_flags = int(creation_flags_text)
        _wait_for_parent_exit(parent_pid, parent_create_time)
        spawn_handoff_process(
            relaunch_args,
            cwd=cwd_path,
            creationflags=creation_flags,
            env=os.environ.copy(),
        )
    except RESTART_CHILD_EXCEPTIONS as exception:
        _append_error(
            error_log_path,
            f"{utc_now_iso()}: Failed to relaunch: {type(exception).__name__}: {exception}\nArgs: {args}\n",
        )
        return 1
    return 0


def _wait_for_parent_exit(parent_pid: int, parent_create_time: float) -> None:
    try:
        parent = psutil.Process(parent_pid)
        create_time_delta = abs(parent.create_time() - parent_create_time)
        if create_time_delta > PARENT_CREATE_TIME_TOLERANCE_SECONDS:
            return
        parent.wait(timeout=PARENT_EXIT_TIMEOUT_SECONDS)
    except psutil.NoSuchProcess:
        return


def _append_error(error_log_path: str, message: str) -> None:
    try:
        os.makedirs(os.path.dirname(error_log_path), exist_ok=True)
        with open_text(
            error_log_path,
            mode="a",
            encoding="utf-8",
            errors="replace",
        ) as file_handle:
            file_handle.write(message)
    except (OSError, ValueError) as exception:
        sys.stderr.write(
            f"{utc_now_iso()}: Failed to write restart child error log '{error_log_path}': {type(exception).__name__}: {exception}\n",
        )


if __name__ == "__main__":
    raise SystemExit(main())
