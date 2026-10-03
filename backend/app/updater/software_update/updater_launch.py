"""SoAI - Detached software updater process launch [backend/app/updater/software_update/updater_launch.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import sys
from typing import TYPE_CHECKING

from core.logging.log_path_resolution import resolve_log_directory
from core.platform.os import is_windows
from core.system.process_launcher import DEVNULL_STREAM, spawn_handoff_process
from core.system.windows_job_breakaway import windows_handoff_process_creationflags

if TYPE_CHECKING:
    from core.config.protocols import ConfigProtocol
    from core.system.process_launcher import ManagedProcess

__all__ = (
    "UPDATER_STDERR_LOG_FILENAME",
    "build_updater_command",
    "spawn_detached_updater",
)

UPDATER_STDERR_LOG_FILENAME = "application_updater.stderr.log"


def build_updater_command(
    *,
    cli_module: str,
    config_path: str,
    task_id: str,
    wait_for_pid: int,
) -> list[str]:
    return [
        sys.executable,
        "-m",
        cli_module,
        "--update-software",
        "--silent",
        "--config",
        config_path,
        "--task-id",
        task_id,
        "--wait-for-pid",
        str(wait_for_pid),
    ]


def spawn_detached_updater(
    *,
    base_dir: str,
    config: ConfigProtocol,
    command: list[str],
) -> ManagedProcess:
    backend_root = os.path.join(base_dir, "backend")
    environment = dict(os.environ)
    existing_pythonpath = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = (
        os.pathsep.join((backend_root, existing_pythonpath))
        if existing_pythonpath
        else backend_root
    )
    log_directory = resolve_log_directory(config)
    os.makedirs(log_directory, exist_ok=True)
    stderr_descriptor = os.open(
        os.path.join(log_directory, UPDATER_STDERR_LOG_FILENAME),
        os.O_WRONLY | os.O_CREAT | os.O_APPEND,
        0o600,
    )
    try:
        return spawn_handoff_process(
            command,
            cwd=backend_root,
            env=environment,
            creationflags=windows_handoff_process_creationflags(),
            start_new_session=not is_windows(),
            stdin=DEVNULL_STREAM,
            stdout=DEVNULL_STREAM,
            stderr=stderr_descriptor,
        )
    finally:
        os.close(stderr_descriptor)
