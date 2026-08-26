"""SoAI - Windows managed Python venv creation [backend/core/bootstrap/windows_managed_venv.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import sys

from core.bootstrap.lock import acquire_interprocess_lock
from core.bootstrap.runtime_directories import ensure_runtime_directory_environment
from core.bootstrap.stage0_environment import is_stage0_offline_mode_enabled
from core.bootstrap.venv_paths import get_venv_path, get_venv_python_executable
from core.bootstrap.windows_sqlite_runtime import ensure_windows_sqlite_runtime
from core.errors.exceptions import StateError
from core.platform.os import is_windows
from core.system.commands import run_argv_capture
from core.timing.constants import SETUP_TIMEOUT_SEC

__all__ = (
    "WINDOWS_MANAGED_VENV_LOCK_FILENAME",
    "ensure_windows_managed_venv",
)

WINDOWS_MANAGED_VENV_LOCK_FILENAME = "soai.windows_managed_venv.lock"
WINDOWS_MANAGED_VENV_LOCK_TIMEOUT_SEC: float = 1200.0


def ensure_windows_managed_venv(repo_root_path: str) -> str:
    if not is_windows():
        raise StateError("Windows managed venv creation is only valid on Windows.")
    repo_root = os.path.abspath(repo_root_path)
    runtime_directories = ensure_runtime_directory_environment(repo_root)
    lock_path = os.path.join(
        runtime_directories.locks_path,
        WINDOWS_MANAGED_VENV_LOCK_FILENAME,
    )
    with acquire_interprocess_lock(
        lock_path,
        timeout_sec=WINDOWS_MANAGED_VENV_LOCK_TIMEOUT_SEC,
    ):
        offline_mode = is_stage0_offline_mode_enabled(repo_root)
        ensure_windows_sqlite_runtime(
            repo_root,
            runtime_directories,
            python_executable=sys.executable,
            offline_mode=offline_mode,
        )
        venv_path = get_venv_path(repo_root)
        python_executable = get_venv_python_executable(venv_path)
        if os.path.isfile(python_executable):
            ensure_windows_sqlite_runtime(
                repo_root,
                runtime_directories,
                python_executable=python_executable,
                offline_mode=offline_mode,
            )
            return python_executable
        if os.path.exists(venv_path):
            raise StateError(
                " ".join(
                    (
                        f"SoAI managed environment is incomplete at '{venv_path}'.",
                        f"Expected python at '{python_executable}'.",
                        "Remove the incomplete directory and start SoAI again.",
                    ),
                ),
            )
        result = run_argv_capture(
            [sys.executable, "-m", "venv", venv_path],
            cwd=repo_root,
            encoding="utf-8",
            errors="replace",
            timeout=SETUP_TIMEOUT_SEC,
        )
        if result.return_code != 0:
            output = result.stderr.strip() or result.stdout.strip() or "no output"
            raise StateError(
                " ".join(
                    (
                        f"Failed to create SoAI managed environment at '{venv_path}'",
                        f"with exit code {result.return_code}: {output}",
                    ),
                ),
            )
        if not os.path.isfile(python_executable):
            raise StateError(
                " ".join(
                    (
                        "SoAI managed environment creation completed but python is missing",
                        f"at '{python_executable}'.",
                    ),
                ),
            )
        ensure_windows_sqlite_runtime(
            repo_root,
            runtime_directories,
            python_executable=python_executable,
            offline_mode=offline_mode,
        )
        return python_executable
