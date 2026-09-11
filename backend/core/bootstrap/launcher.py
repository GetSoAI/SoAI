"""SoAI - Runtime bootstrap coordinator [backend/core/bootstrap/launcher.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os

from core.bootstrap.command_streaming import run_bootstrap_command
from core.bootstrap.launcher_config import ensure_config_yaml_exists
from core.bootstrap.lock import acquire_interprocess_lock
from core.bootstrap.python_dependencies import bootstrap_python_dependencies_if_needed
from core.bootstrap.runtime_directories import (
    LOCKS_PATH_ENV,
    ensure_runtime_directory_environment,
)
from core.bootstrap.stage0_environment import ensure_stage0_soai_python_version
from core.bootstrap.venv_paths import get_venv_path, get_venv_python_executable

__all__ = (
    "BOOTSTRAP_LOCK_FILENAME",
    "LOCKS_PATH_ENV",
    "bootstrap_if_needed",
)

BOOTSTRAP_LOCK_FILENAME = "soai.main_bootstrap.lock"


def bootstrap_if_needed(repo_root_path: str) -> None:
    ensure_stage0_soai_python_version()
    ensure_config_yaml_exists(repo_root_path)
    venv_path = get_venv_path(repo_root_path)
    python_executable = get_venv_python_executable(venv_path)
    if not os.path.exists(python_executable):
        raise FileNotFoundError(
            f"SoAI managed environment is missing. Start SoAI via soai.sh or soai.exe to create it. Expected python at '{python_executable}'.",
        )
    bootstrap_python_dependencies_if_needed(
        repo_root_path,
        python_executable=python_executable,
    )
    runtime_directories = ensure_runtime_directory_environment(repo_root_path)
    lock_path = os.path.join(
        runtime_directories.locks_path,
        BOOTSTRAP_LOCK_FILENAME,
    )
    with acquire_interprocess_lock(lock_path, timeout_sec=1200.0):
        _ensure_runtime_artifacts_via_managed_python(
            repo_root_path,
            python_executable=python_executable,
        )


def _ensure_runtime_artifacts_via_managed_python(
    repo_root_path: str,
    *,
    python_executable: str,
) -> None:
    env = dict(os.environ)
    backend_path = os.path.join(os.path.abspath(repo_root_path), "backend")
    existing_python_path = env.get("PYTHONPATH", "").strip()
    env["PYTHONPATH"] = (
        backend_path
        if not existing_python_path
        else f"{backend_path}{os.pathsep}{existing_python_path}"
    )
    command = [
        python_executable,
        "-P",
        "-m",
        "core.bootstrap.runtime_artifacts_cli",
        os.path.abspath(repo_root_path),
    ]
    run_bootstrap_command(
        command,
        log_prefix="artifacts: ",
        cwd=os.path.abspath(repo_root_path),
        env=env,
    )
