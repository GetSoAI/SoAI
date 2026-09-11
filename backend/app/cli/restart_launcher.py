"""SoAI - CLI restart relaunch operations [backend/app/cli/restart_launcher.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import logging
import os
import sys

import psutil

from app.cli.windows_console_service import (
    WindowsConsoleService,
    WindowsConsoleServiceDependencies,
)
from core.bootstrap.runtime_directories import ensure_runtime_directory_environment
from core.meta.paths import join_data_abs
from core.runtime.platform import get_runtime_platform
from core.system.process_launcher import DEVNULL_STREAM, spawn_handoff_process
from core.system.process_replacement import (
    flush_process_replacement_output,
    redirect_standard_streams_to_devnull,
    replace_current_process,
)

__all__ = ("relaunch_application", "spawn_replacement_application")


def _build_entrypoint_argv(cli_module: str, arguments: list[str]) -> list[str]:
    return [sys.executable, "-m", cli_module, *arguments]


def _windows_creation_flags(lifecycle_logger: logging.Logger) -> int:
    return WindowsConsoleService(
        WindowsConsoleServiceDependencies(logger=lifecycle_logger),
    ).get_subprocess_flags()


def relaunch_application(
    *,
    base_dir: str,
    lifecycle_logger: logging.Logger,
    cli_module: str,
) -> None:
    flush_process_replacement_output()
    ensure_runtime_directory_environment(base_dir)
    backend_dir = os.path.join(base_dir, "backend")
    restart_argv = _build_entrypoint_argv(cli_module, list(sys.argv[1:]))
    runtime_platform = get_runtime_platform()
    if runtime_platform.is_windows:
        flags = _windows_creation_flags(lifecycle_logger)
        parent_create_time = psutil.Process(os.getpid()).create_time()
        error_log_path = join_data_abs(base_dir, "logs", "soai_restart_launcher_error.log")
        launcher_cmd = [
            sys.executable,
            "-m",
            "app.cli.restart_child",
            str(os.getpid()),
            str(parent_create_time),
            backend_dir,
            str(flags),
            error_log_path,
        ] + restart_argv
        spawn_handoff_process(
            launcher_cmd,
            cwd=backend_dir,
            creationflags=flags,
            env=os.environ.copy(),
        )
        return
    redirect_standard_streams_to_devnull()
    os.chdir(backend_dir)
    replace_current_process(restart_argv)


def spawn_replacement_application(
    *,
    base_dir: str,
    lifecycle_logger: logging.Logger,
    cli_module: str,
) -> None:
    ensure_runtime_directory_environment(base_dir)
    backend_dir = os.path.join(base_dir, "backend")
    replacement_argv = _build_entrypoint_argv(cli_module, ["--start"])
    runtime_platform = get_runtime_platform()
    if runtime_platform.is_windows:
        flags = _windows_creation_flags(lifecycle_logger)
        spawn_handoff_process(
            replacement_argv,
            cwd=backend_dir,
            creationflags=flags,
            env=os.environ.copy(),
        )
        return
    spawn_handoff_process(
        replacement_argv,
        cwd=backend_dir,
        env=os.environ.copy(),
        start_new_session=True,
        stdin=DEVNULL_STREAM,
        stdout=DEVNULL_STREAM,
        stderr=DEVNULL_STREAM,
    )
