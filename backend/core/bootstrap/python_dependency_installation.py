"""SoAI - Native pip installation commands for managed dependencies [backend/core/bootstrap/python_dependency_installation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import ntpath
import os

from core.bootstrap.command_streaming import run_bootstrap_command
from core.bootstrap.install_diagnostics import InstallDiagnostics
from core.bootstrap.venv_paths import get_venv_path
from core.errors.exceptions import StateError
from core.filesystem.path_coercion import remove_windows_path_namespace
from core.platform.os import is_windows

__all__ = ("install_python_dependencies",)


def install_python_dependencies(
    *,
    repo_root_path: str,
    python_executable: str,
    requirements_path: str,
    diagnostics: InstallDiagnostics | None = None,
) -> None:
    install_command = _dependency_install_command(repo_root_path, python_executable)
    command = [
        *install_command,
        "--force-reinstall",
        "--no-deps",
        "--only-binary=:all:",
        "--require-hashes",
        "-r",
        os.path.join(
            repo_root_path, "backend", "core", "bootstrap", "tls_bootstrap_requirements.txt"
        ),
    ]
    if diagnostics is None:
        run_bootstrap_command(command, log_prefix="pip: ", cwd=repo_root_path)
    else:
        run_bootstrap_command(
            command, log_prefix="pip: ", cwd=repo_root_path, diagnostics=diagnostics
        )
    command = [*install_command, "wheel"]
    if diagnostics is None:
        run_bootstrap_command(command, log_prefix="pip: ", cwd=repo_root_path)
    else:
        run_bootstrap_command(
            command, log_prefix="pip: ", cwd=repo_root_path, diagnostics=diagnostics
        )
    command = [*install_command, "--upgrade-strategy", "eager", "-r", requirements_path]
    if diagnostics is None:
        run_bootstrap_command(command, log_prefix="pip: ", cwd=repo_root_path)
    else:
        run_bootstrap_command(
            command, log_prefix="pip: ", cwd=repo_root_path, diagnostics=diagnostics
        )


def _dependency_install_command(repo_root_path: str, python_executable: str) -> list[str]:
    command = [python_executable, "-m", "pip", "install", "--root-user-action=ignore", "--upgrade"]
    if is_windows():
        prefix = remove_windows_path_namespace(get_venv_path(repo_root_path))
        volume, _relative = ntpath.splitdrive(prefix)
        if not volume or not ntpath.isabs(prefix) or prefix.startswith("\\\\.\\"):
            raise StateError("The managed Python install prefix must be a drive or UNC path.")
        command.extend(("--prefix", prefix))
    return command
