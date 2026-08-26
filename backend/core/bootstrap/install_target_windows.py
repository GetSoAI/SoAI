"""SoAI - Windows install target validation [backend/core/bootstrap/install_target_windows.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os

from core.bootstrap.install_locks import lock_dir_has_live_owner
from core.errors.exceptions import SoAIError, StateError, ValidationError
from core.meta.paths import join_data_abs
from core.runtime.instance_record import read_verified_runtime_instance_record
from core.runtime.process_identity import SOAI_BACKEND_MAIN_SUBPATH

__all__ = (
    "normalize_windows_install_target",
    "recognizable_windows_install_target",
    "reject_running_windows_target",
    "validate_windows_install_target",
)


def normalize_windows_install_target(target: str) -> str:
    clean_target = target.strip()
    if not clean_target:
        raise ValueError("--target requires a non-empty value.")
    if "\n" in clean_target or "\r" in clean_target or "\t" in clean_target:
        raise ValueError("--target must not contain control characters.")
    target_name = os.path.basename(os.path.normpath(clean_target))
    if target_name in {"", ".", ".."}:
        raise ValueError(f"Install target must name a concrete SoAI directory: {target}")
    return os.path.abspath(clean_target)


def validate_windows_install_target(target_root: str) -> None:
    if os.path.islink(target_root):
        raise ValidationError(
            f"Install target must not be a symlink: {target_root}",
            details={"target_root": target_root},
            operation="bootstrap.install.validate_target",
        )
    parent_dir = os.path.dirname(target_root)
    os.makedirs(parent_dir, exist_ok=True)
    if os.path.exists(target_root) and not os.path.isdir(target_root):
        raise ValidationError(
            f"Install target exists but is not a directory: {target_root}",
            details={"target_root": target_root},
            operation="bootstrap.install.validate_target",
        )
    if not os.path.exists(target_root):
        os.makedirs(target_root, exist_ok=False)
    _require_writable_directory(target_root)


def recognizable_windows_install_target(target_root: str) -> bool:
    if not os.path.exists(target_root):
        return True
    if not os.path.isdir(target_root):
        return False
    if not os.listdir(target_root):
        return True
    if os.path.isfile(os.path.join(target_root, ".soai_install_manifest.json")):
        return True
    if os.path.isfile(os.path.join(target_root, ".soai_install_in_progress")):
        return True
    backend_entrypoint = os.path.join(target_root, SOAI_BACKEND_MAIN_SUBPATH)
    windows_launcher = os.path.join(target_root, "soai.exe")
    posix_launcher = os.path.join(target_root, "soai.sh")
    return os.path.isfile(backend_entrypoint) and (
        os.path.isfile(windows_launcher) or os.path.isfile(posix_launcher)
    )


def reject_running_windows_target(target_root: str, *, expected_edition: str) -> None:
    runtime_lock = join_data_abs(target_root, "state", "locks", "soai.runtime.lock.d")
    if lock_dir_has_live_owner(runtime_lock) or _target_pid_is_running(
        target_root,
        expected_edition,
    ):
        raise StateError(
            f"Refusing to update target while SoAI is running: {target_root}",
            details={"target_root": target_root},
            operation="bootstrap.install.reject_running_target",
        )


def _target_pid_is_running(target_root: str, expected_edition: str) -> bool:
    pid_path = os.path.join(_target_temp_dir(target_root), "soai.pid")
    try:
        record = read_verified_runtime_instance_record(
            pid_path,
            base_dir=target_root,
            expected_edition=expected_edition,
        )
    except (OSError, SoAIError):
        record = None
    return record is not None


def _target_temp_dir(target_root: str) -> str:
    config_path = join_data_abs(target_root, "config", "config.yaml")
    default_temp = join_data_abs(target_root, "temp")
    if not os.path.isfile(config_path):
        return default_temp
    system_data = _target_config_path_value(config_path, "SYSTEM_DATA") or "data"
    system_data_dir = (
        system_data if os.path.isabs(system_data) else os.path.join(target_root, system_data)
    )
    temp_value = _target_config_path_value(config_path, "TEMP")
    if not temp_value:
        return default_temp
    return temp_value if os.path.isabs(temp_value) else os.path.join(system_data_dir, temp_value)


def _target_config_path_value(config_path: str, key: str) -> str:
    in_system = False
    in_paths = False
    system_indent = -1
    paths_indent = -1
    with open(config_path, encoding="utf-8", errors="strict") as handle:
        for raw_line in handle:
            stripped = raw_line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            indent = len(raw_line) - len(raw_line.lstrip())
            if stripped == "SYSTEM:":
                in_system = True
                in_paths = False
                system_indent = indent
                continue
            if in_system and indent <= system_indent and stripped != "SYSTEM:":
                in_system = False
                in_paths = False
            if in_system and stripped == "PATHS:":
                in_paths = True
                paths_indent = indent
                continue
            if in_paths and indent <= paths_indent and stripped != "PATHS:":
                in_paths = False
            prefix = f"{key}:"
            if in_paths and stripped.startswith(prefix):
                value = stripped[len(prefix) :].split("#", 1)[0].strip()
                return value.strip("'\"")
    return ""


def _require_writable_directory(directory: str) -> None:
    probe_path = os.path.join(directory, f".soai_write_probe.{os.getpid()}")
    with open(probe_path, "w", encoding="utf-8", errors="strict") as handle:
        handle.write("ok\n")
    os.unlink(probe_path)
