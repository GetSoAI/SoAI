"""SoAI - Bootstrap command streaming helpers [backend/core/bootstrap/command_streaming.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import subprocess

from core.bootstrap.launch_console import emit
from core.errors.exceptions import StateError
from core.system.process_launcher import spawn_managed_process

__all__ = ("run_bootstrap_command",)


def run_bootstrap_command(
    command: list[str],
    *,
    log_prefix: str,
    cwd: str | None = None,
    env: dict[str, str] | None = None,
) -> None:
    with spawn_managed_process(
        command,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    ) as process:
        try:
            if process.stdout is None:
                raise StateError("Subprocess stdout pipe is unavailable.")
            for line in process.stdout:
                if isinstance(line, bytes):
                    stripped = line.decode("utf-8", errors="replace").strip()
                else:
                    stripped = line.strip()
                if stripped:
                    emit("INFO", f"{log_prefix}{stripped}")
            exit_code = process.wait()
        except KeyboardInterrupt:
            process.kill()
            raise
    if exit_code != 0:
        raise subprocess.CalledProcessError(exit_code, command)
