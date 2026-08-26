"""SoAI - Shared stage-zero application bootstrap [backend/core/bootstrap/stage0_application.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import subprocess
import sys

from core.bootstrap.install_deps_flags import contains_install_deps_flag
from core.bootstrap.launch_console import emit
from core.bootstrap.python_dependencies import bootstrap_python_dependencies_if_needed
from core.bootstrap.runtime_directories import ensure_runtime_directory_environment
from core.bootstrap.stage0_environment import (
    ensure_stage0_config_yaml_exists,
    ensure_stage0_soai_python_version,
    is_running_in_soai_venv,
    relaunch_in_venv_or_emit_failure,
    repo_root,
)
from core.runtime.opencl_environment import configure_opencl_runtime_environment
from core.system.process_replacement import replace_current_process

__all__ = ("run_stage0_application",)


def _python_path_including_backend(repo_root_path: str) -> str:
    backend_path = os.path.join(os.path.abspath(repo_root_path), "backend")
    inherited_python_path = os.environ.get("PYTHONPATH", "")
    inherited_entries = [entry for entry in inherited_python_path.split(os.pathsep) if entry]
    normalized_backend_path = os.path.normcase(backend_path)
    for entry in inherited_entries:
        if os.path.normcase(os.path.abspath(entry)) == normalized_backend_path:
            return inherited_python_path
    return os.pathsep.join([backend_path, *inherited_entries])


def _exec_bootstrap_module(repo_root_path: str, bootstrap_module: str) -> int:
    os.chdir(repo_root_path)
    os.environ["PYTHONPATH"] = _python_path_including_backend(repo_root_path)
    return replace_current_process(
        [sys.executable, "-m", bootstrap_module, *sys.argv[1:]],
    )


def run_stage0_application(*, bootstrap_module: str, entrypoint_path: str) -> int:
    repo_root_path = repo_root()
    configure_opencl_runtime_environment()
    ensure_stage0_config_yaml_exists(repo_root_path)
    ensure_runtime_directory_environment(repo_root_path)
    running_in_managed_runtime = is_running_in_soai_venv(repo_root_path)
    if os.name == "nt" and not running_in_managed_runtime:
        return _exec_bootstrap_module(repo_root_path, bootstrap_module)
    if not running_in_managed_runtime:
        launched = relaunch_in_venv_or_emit_failure(
            repo_root_path,
            entrypoint_path=entrypoint_path,
        )
        return 0 if launched else 1
    python_version_error: str | None = None
    try:
        ensure_stage0_soai_python_version()
    except RuntimeError as exception:
        python_version_error = str(exception)
    if python_version_error is not None:
        emit("ERROR", f"FATAL: {python_version_error}")
        return 1
    dependency_error: str | None = None
    changed = False
    try:
        changed = bootstrap_python_dependencies_if_needed(repo_root_path)
    except (
        OSError,
        RuntimeError,
        ValueError,
        subprocess.CalledProcessError,
    ) as exception:
        dependency_error = str(exception)
    if dependency_error is not None:
        emit("ERROR", f"FATAL: Python dependency bootstrap failed: {dependency_error}")
        return 1
    if changed and not contains_install_deps_flag(sys.argv[1:]):
        emit("INFO", "SoAI Python runtime dependencies are ready.")
    return _exec_bootstrap_module(repo_root_path, bootstrap_module)
