"""SoAI - Purger executor for launching detached cleanup processes [backend/app/purger/executor.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import platform
import sys
from typing import TYPE_CHECKING

from app.cli.windows_console_service import (
    WindowsConsoleService,
    WindowsConsoleServiceDependencies,
)
from app.purger.script import PURGER_SCRIPT
from core.errors.exceptions import ConfigurationError
from core.logging.trace import get_logger
from core.runtime.process_identity import SOAI_BACKEND_MAIN_SUBPATH
from core.system.process_launcher import spawn_managed_process

if TYPE_CHECKING:
    from core.system.process_launcher import ManagedProcess

__all__ = ("launch_detached_purger",)

LOGGER_NAME = "SoAI.app.purger.executor"


def launch_detached_purger(
    base_dir: str,
    sentinel_path: str,
    manifest_path: str,
) -> ManagedProcess:
    managed_python = sys.executable
    if not os.path.exists(managed_python):
        raise ConfigurationError(
            f"FATAL: Managed Python interpreter not found at expected path: {managed_python}. Cannot launch purger.",
        )
    cmd = [
        managed_python,
        "-c",
        PURGER_SCRIPT,
        base_dir,
        sentinel_path,
        manifest_path,
    ]
    env = os.environ.copy()
    if platform.system() == "Windows":
        creationflags = WindowsConsoleService(
            WindowsConsoleServiceDependencies(logger=get_logger(LOGGER_NAME)),
        ).get_subprocess_flags()
        start_new_session = False
    else:
        creationflags = 0
        start_new_session = True
    backend_dir = os.path.dirname(os.path.join(base_dir, SOAI_BACKEND_MAIN_SUBPATH))
    return spawn_managed_process(
        cmd,
        cwd=backend_dir,
        env=env,
        creationflags=creationflags,
        start_new_session=start_new_session,
    )
