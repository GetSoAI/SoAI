"""SoAI - Windows install target validation [backend/core/bootstrap/install_target_windows.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import re
from contextlib import ExitStack

from core.bootstrap.install_locks import lock_dir_has_live_owner
from core.errors.exceptions import SoAIError, StateError, ValidationError
from core.files.temp_files import create_secure_temp_binary_handle
from core.files.windows_managed_path_handles import open_windows_managed_path_handles
from core.files.windows_reparse_points import is_windows_reparse_point
from core.files.windows_reserved_names import WINDOWS_RESERVED_DEVICE_NAMES
from core.filesystem.open_files import read_regular_file_no_symlink
from core.filesystem.path_coercion import normalize_filesystem_path
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
    if os.name == "nt":
        if clean_target.startswith(("\\\\?\\", "\\\\.\\")):
            raise ValueError(
                "--target requires a logical drive or UNC path, not a device namespace."
            )
        normalized = os.path.abspath(clean_target)
        volume, relative = os.path.splitdrive(normalized)
        if not volume or ":" in relative:
            raise ValueError(
                "--target requires a drive or UNC path without alternate data streams."
            )
        for component in relative.strip("\\").split("\\"):
            if (
                not component
                or component.endswith((".", " "))
                or any(ord(character) < 32 or character in '<>"|?*' for character in component)
                or component.split(".", 1)[0].upper() in WINDOWS_RESERVED_DEVICE_NAMES
            ):
                raise ValueError("--target contains an unsupported Windows path component.")
    target_name = os.path.basename(os.path.normpath(clean_target))
    if target_name in {"", ".", ".."}:
        raise ValueError(f"Install target must name a concrete SoAI directory: {target}")
    return os.path.abspath(clean_target)


def validate_windows_install_target(target_root: str, *, create: bool = True) -> None:
    current = os.path.abspath(target_root)
    while True:
        filesystem_path = normalize_filesystem_path(current)
        if os.path.lexists(filesystem_path):
            identity = os.stat(filesystem_path, follow_symlinks=False)
            if os.path.islink(filesystem_path) or is_windows_reparse_point(identity):
                raise ValidationError(
                    "Install target ancestors must not be links or reparse points."
                )
            if not os.path.isdir(filesystem_path):
                raise ValidationError("Install target and its ancestors must be directories.")
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent
    if os.path.islink(normalize_filesystem_path(target_root)):
        raise ValidationError(
            f"Install target must not be a symlink: {target_root}",
            details={"target_root": target_root},
            operation="bootstrap.install.validate_target",
        )
    if not create:
        return
    parent_dir = os.path.dirname(target_root)
    os.makedirs(normalize_filesystem_path(parent_dir), exist_ok=True)
    if os.path.exists(normalize_filesystem_path(target_root)) and not os.path.isdir(
        normalize_filesystem_path(target_root)
    ):
        raise ValidationError(
            f"Install target exists but is not a directory: {target_root}",
            details={"target_root": target_root},
            operation="bootstrap.install.validate_target",
        )
    if not os.path.exists(normalize_filesystem_path(target_root)):
        os.makedirs(normalize_filesystem_path(target_root), exist_ok=False)
    _require_writable_directory(target_root)


def recognizable_windows_install_target(target_root: str) -> bool:
    target_root = normalize_filesystem_path(target_root)
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
    backend_entrypoint = os.path.join(target_root, *SOAI_BACKEND_MAIN_SUBPATH.split("/"))
    windows_launcher = os.path.join(target_root, "soai.exe")
    posix_launcher = os.path.join(target_root, "soai.sh")
    if os.path.isfile(backend_entrypoint) and (
        os.path.isfile(windows_launcher) or os.path.isfile(posix_launcher)
    ):
        return True
    retained_marker: bytes | None = None
    try:
        retained_marker = read_regular_file_no_symlink(
            os.path.join(target_root, ".soai-install-root"), max_bytes=128
        )
    except (OSError, SoAIError):
        retained_marker = None
    return (
        retained_marker is not None
        and re.fullmatch(
            rb"SoAI Windows Installer Root(?:\r\nVersion=[0-9]+\.[0-9]+\.[0-9]+)?(?:\r\n)?",
            retained_marker,
        )
        is not None
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
    handle, probe_path = create_secure_temp_binary_handle(
        directory=directory, prefix=".soai_write_probe."
    )
    try:
        with handle:
            handle.write(b"ok\n")
    finally:
        os.unlink(normalize_filesystem_path(probe_path))


def validate_windows_launcher_configuration(source_root: str, target_root: str) -> None:
    candidate = read_regular_file_no_symlink(
        os.path.join(source_root, "soai.exe.config"), max_bytes=32768
    )
    candidate_template = read_regular_file_no_symlink(
        os.path.join(source_root, "installer-support", "soai.exe.config"), max_bytes=32768
    )
    if candidate != candidate_template:
        raise ValidationError(
            "The source launcher configuration does not match its installer template."
        )
    target_configuration = os.path.join(target_root, "soai.exe.config")
    if not os.path.lexists(normalize_filesystem_path(target_configuration)):
        return
    attributes = os.stat(normalize_filesystem_path(target_configuration), follow_symlinks=False)
    if os.path.islink(normalize_filesystem_path(target_configuration)) or is_windows_reparse_point(
        attributes
    ):
        raise ValidationError("Launcher configuration must not be a link or reparse point.")
    actual = read_regular_file_no_symlink(target_configuration, max_bytes=32768)
    if actual == candidate:
        return
    installed_template = os.path.join(target_root, "installer-support", "soai.exe.config")
    if os.path.isfile(normalize_filesystem_path(installed_template)):
        installed_manifest = os.path.join(target_root, "installer-support", "installed-files.txt")
        if os.path.isfile(normalize_filesystem_path(installed_manifest)):
            inventory = read_regular_file_no_symlink(installed_manifest, max_bytes=8 * 1024 * 1024)
            if (
                b"soai.exe.config" in inventory.splitlines()
                and actual == read_regular_file_no_symlink(installed_template, max_bytes=32768)
            ):
                return
    raise ValidationError(
        "A custom launcher configuration conflicts with this installation; existing bytes have been retained."
    )


def retain_windows_install_ancestors(directory: str, resources: ExitStack) -> None:
    if os.name != "nt":
        return
    ancestor = os.path.abspath(directory)
    while not os.path.lexists(normalize_filesystem_path(ancestor)):
        parent = os.path.dirname(ancestor)
        if parent == ancestor:
            raise ValidationError("Install target volume is unavailable.")
        ancestor = parent
    volume_root = os.path.splitdrive(ancestor)[0] + os.sep
    resources.enter_context(
        open_windows_managed_path_handles(volume_root, ancestor, require_directory=True)
    )


def create_windows_install_directories(directory: str, resources: ExitStack) -> None:
    if os.name != "nt":
        return
    missing: list[str] = []
    ancestor = os.path.abspath(directory)
    while not os.path.lexists(normalize_filesystem_path(ancestor)):
        missing.append(ancestor)
        ancestor = os.path.dirname(ancestor)
    retain_windows_install_ancestors(ancestor, resources)
    for segment_path in reversed(missing):
        os.mkdir(normalize_filesystem_path(segment_path))
        retain_windows_install_ancestors(segment_path, resources)
