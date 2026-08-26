"""SoAI - Plugin environment command execution [backend/plugins/environments/commands.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os
import shutil
import sys

from core.errors.exceptions import ProcessError, StateError
from core.system.async_process_capture import run_argv_capture_async
from core.system.commands import CommandResult

__all__ = (
    "delete_plugin_environment_path",
    "ensure_plugin_environment_python",
    "install_plugin_environment_requirements",
    "query_plugin_environment_freeze",
    "resolve_plugin_environment_python",
)


def resolve_plugin_environment_python(env_path: str) -> str:
    bin_dir, python_executable = (
        ("Scripts", "python.exe") if sys.platform == "win32" else ("bin", "python")
    )
    return os.path.join(env_path, bin_dir, python_executable)


async def _run_env_command(argv: list[str], *, timeout_sec: float | None) -> CommandResult:
    return await run_argv_capture_async(
        argv,
        timeout=timeout_sec,
        encoding="utf-8",
        errors="replace",
    )


def _require_env_command_success(result: CommandResult, argv: list[str], *, operation: str) -> None:
    if result.return_code == 0:
        return
    raise ProcessError(
        "Plugin environment command failed.",
        operation=operation,
        details={
            "argv": list(argv),
            "return_code": result.return_code,
            "stdout": result.stdout,
            "stderr": result.stderr,
        },
    )


async def delete_plugin_environment_path(env_path: str) -> None:
    if os.path.exists(env_path):
        await asyncio.to_thread(shutil.rmtree, env_path)


async def ensure_plugin_environment_python(
    env_path: str,
    base_python_executable: str,
) -> str:
    base_python = os.path.abspath(str(base_python_executable or "").strip())
    if not os.path.isfile(base_python):
        raise StateError("Managed SoAI Python executable was not found.")
    python_executable = resolve_plugin_environment_python(env_path)
    if not os.path.isfile(python_executable):
        await delete_plugin_environment_path(env_path)
        create_argv = [base_python, "-m", "venv", env_path]
        create_result = await _run_env_command(
            create_argv,
            timeout_sec=None,
        )
        _require_env_command_success(
            create_result,
            create_argv,
            operation="plugins.environments.create",
        )
    if not os.path.isfile(python_executable):
        raise StateError("Plugin environment Python executable was not created.")
    ensurepip_argv = [python_executable, "-m", "ensurepip", "--upgrade"]
    ensurepip_result = await _run_env_command(
        ensurepip_argv,
        timeout_sec=None,
    )
    _require_env_command_success(
        ensurepip_result,
        ensurepip_argv,
        operation="plugins.environments.ensurepip",
    )
    return python_executable


async def install_plugin_environment_requirements(
    python_executable: str,
    baseline_requirements: tuple[str, ...],
    plugin_requirements: tuple[str, ...],
) -> None:
    base_argv = [
        python_executable,
        "-m",
        "pip",
        "install",
        "--no-cache-dir",
        "--upgrade",
        "pip",
        "setuptools",
        "wheel",
    ]
    base_result = await _run_env_command(base_argv, timeout_sec=None)
    _require_env_command_success(
        base_result,
        base_argv,
        operation="plugins.environments.install_baseline",
    )
    if baseline_requirements:
        baseline_argv = [
            python_executable,
            "-m",
            "pip",
            "install",
            "--no-cache-dir",
            *baseline_requirements,
        ]
        baseline_install_result = await _run_env_command(
            baseline_argv,
            timeout_sec=None,
        )
        _require_env_command_success(
            baseline_install_result,
            baseline_argv,
            operation="plugins.environments.install_worker_baseline",
        )
    if not plugin_requirements:
        return
    requirements_argv = [
        python_executable,
        "-m",
        "pip",
        "install",
        "--no-cache-dir",
        *plugin_requirements,
    ]
    requirements_result = await _run_env_command(
        requirements_argv,
        timeout_sec=None,
    )
    _require_env_command_success(
        requirements_result,
        requirements_argv,
        operation="plugins.environments.install_requirements",
    )


async def query_plugin_environment_freeze(python_executable: str) -> list[str]:
    argv = [python_executable, "-m", "pip", "freeze", "--all"]
    result = await _run_env_command(argv, timeout_sec=None)
    _require_env_command_success(result, argv, operation="plugins.environments.freeze")
    return sorted(line.strip() for line in result.stdout.splitlines() if line.strip())
