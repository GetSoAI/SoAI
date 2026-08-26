"""SoAI - Stage-zero bootstrap environment helpers [backend/core/bootstrap/stage0_environment.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import shutil
import sys
import uuid

from core.bootstrap.launch_console import emit
from core.bootstrap.offline_mode import read_yaml_boolean_key
from core.bootstrap.runtime_directories import ensure_runtime_directory_environment
from core.bootstrap.venv_paths import get_venv_path, get_venv_python_executable
from core.config.file_permissions import secure_runtime_config_paths
from core.errors.exceptions import StateError
from core.meta.paths import get_config_yaml_path, join_data_abs
from core.system.process_launcher import SUBPROCESS_RECOVERABLE_EXCEPTIONS
from core.system.process_replacement import replace_current_process

__all__ = (
    "ensure_stage0_config_yaml_exists",
    "ensure_stage0_soai_python_version",
    "is_running_in_soai_venv",
    "is_stage0_offline_mode_enabled",
    "relaunch_in_venv",
    "relaunch_in_venv_or_emit_failure",
    "repo_root",
    "resolve_stage0_config_path",
)

MINIMUM_PYTHON_VERSION: tuple[int, int] = (3, 13)
RELAUNCH_FAILURE_EXCEPTIONS: tuple[type[BaseException], ...] = (
    *SUBPROCESS_RECOVERABLE_EXCEPTIONS,
    ValueError,
)


def repo_root() -> str:
    module_dir = os.path.dirname(__file__)
    return os.path.abspath(os.path.join(module_dir, os.pardir, os.pardir, os.pardir))


def ensure_stage0_soai_python_version() -> None:
    version_info = sys.version_info
    current_version_tuple = (int(version_info.major), int(version_info.minor))
    if current_version_tuple >= MINIMUM_PYTHON_VERSION:
        return
    min_version = f"{MINIMUM_PYTHON_VERSION[0]}.{MINIMUM_PYTHON_VERSION[1]}"
    current_version = f"{version_info.major}.{version_info.minor}.{version_info.micro}"
    raise StateError(
        f"SoAI requires Python {min_version} or later, but you are running Python {current_version}.\nPlease start SoAI through its managed runtime launcher.",
    )


def is_running_in_soai_venv(repo_root_path: str) -> bool:
    expected_python = os.path.realpath(get_venv_python_executable(get_venv_path(repo_root_path)))
    return os.path.realpath(sys.executable) == expected_python


def relaunch_in_venv(repo_root_path: str, *, entrypoint_path: str) -> int:
    python_executable = get_venv_python_executable(get_venv_path(repo_root_path))
    if not os.path.exists(python_executable):
        raise FileNotFoundError(
            f"Cannot relaunch because managed Python is missing at '{python_executable}'.",
        )
    ensure_runtime_directory_environment(repo_root_path)
    return replace_current_process([python_executable, entrypoint_path, *sys.argv[1:]])


def relaunch_in_venv_or_emit_failure(repo_root_path: str, *, entrypoint_path: str) -> bool:
    emit("INFO", "Launching SoAI managed environment...")
    relaunch_failed = False
    exit_code = 1
    try:
        exit_code = relaunch_in_venv(repo_root_path, entrypoint_path=entrypoint_path)
    except RELAUNCH_FAILURE_EXCEPTIONS as exception:
        emit(
            "ERROR",
            f"FATAL: Managed environment is missing or invalid: {type(exception).__name__}: {exception}",
        )
        relaunch_failed = True
    if relaunch_failed:
        return False
    return exit_code == 0


def resolve_stage0_config_path(repo_root_path: str) -> str:
    configured_path = os.environ.get("SOAI_CONFIG_PATH", "").strip()
    if configured_path:
        expanded = os.path.expanduser(os.path.expandvars(configured_path))
        if not os.path.isabs(expanded):
            expanded = os.path.join(repo_root_path, expanded)
        return os.path.abspath(expanded)
    return get_config_yaml_path(repo_root_path)


def ensure_stage0_config_yaml_exists(repo_root_path: str) -> None:
    config_path = resolve_stage0_config_path(repo_root_path)
    if os.path.isfile(config_path):
        secure_runtime_config_paths(config_path, f"{config_path}.backup")
        return
    default_config_path = join_data_abs(repo_root_path, "config", "config.default.yaml")
    if not os.path.isfile(default_config_path):
        return
    config_dir = os.path.dirname(config_path)
    if config_dir:
        os.makedirs(config_dir, exist_ok=True)
    temp_path = f"{config_path}.tmp.{os.getpid()}.{uuid.uuid4().hex}"
    try:
        descriptor = os.open(temp_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as target_handle:
            secure_runtime_config_paths(temp_path)
            with open(default_config_path, "rb") as source_handle:
                shutil.copyfileobj(source_handle, target_handle)
                target_handle.flush()
                os.fsync(target_handle.fileno())
        os.replace(temp_path, config_path)
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


def is_stage0_offline_mode_enabled(repo_root_path: str) -> bool:
    config_path = resolve_stage0_config_path(repo_root_path)
    if not os.path.isfile(config_path):
        return False
    try:
        parsed = read_yaml_boolean_key(config_path, key="SYSTEM.RUNTIME.STAY_OFFLINE")
    except (OSError, ValueError):
        parsed = None
    return bool(parsed)
