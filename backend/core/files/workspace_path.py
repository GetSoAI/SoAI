"""SoAI - Shared workspace path helpers [backend/core/files/workspace_path.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os

from core.errors.exceptions import StateError, ValidationError
from core.files.protocols import FilesPathResolverProtocol
from core.files.workspace_descriptor import is_disallowed_workspace_link

__all__ = (
    "create_workspace_directory",
    "resolve_existing_workspace_directory",
    "resolve_workspace_real_path",
    "validate_workspace_directory_exists",
)


def _absolute_root_parts(path: str) -> tuple[str, list[str]]:
    absolute_path = os.path.abspath(path)
    drive, tail = os.path.splitdrive(absolute_path)
    root = f"{drive}{os.sep}" if os.path.isabs(absolute_path) else drive
    parts = [part for part in tail.split(os.sep) if part]
    return absolute_path, [root, *parts]


def _join_workspace_path(base_path: str, part: str) -> str:
    if base_path.endswith(os.sep):
        return f"{base_path}{part}"
    return f"{base_path}{os.sep}{part}"


def _validate_workspace_root_path(path: str, *, require_existing_directory: bool) -> str:
    if not path.strip():
        raise ValidationError("workspace_path must be a non-empty string.")
    if "\x00" in path:
        raise ValidationError("workspace_path contains an invalid character.")
    if not os.path.isabs(path):
        raise ValidationError("workspace_path must be an absolute path.")
    absolute_path, parts = _absolute_root_parts(path)
    current_path = ""
    for index, part in enumerate(parts):
        current_path = part if index == 0 else _join_workspace_path(current_path, part)
        try:
            stat_result = os.lstat(current_path)
        except FileNotFoundError as exception:
            if not require_existing_directory:
                return absolute_path
            raise ValidationError("workspace_path must be an existing directory.") from exception
        except OSError as exception:
            raise ValidationError("Failed to inspect the configured workspace path.") from exception
        if is_disallowed_workspace_link(stat_result):
            raise ValidationError("workspace_path cannot traverse symbolic links.")
        if not os.path.isdir(current_path):
            raise ValidationError("workspace_path must be an existing directory.")
    return absolute_path


def resolve_workspace_real_path(files: FilesPathResolverProtocol, workspace_path: str) -> str:
    if not workspace_path.strip():
        raise ValidationError("workspace_path must be a non-empty string.")
    try:
        resolved = files.resolve_path(workspace_path.strip())
    except (StateError, ValidationError) as exception:
        raise ValidationError("Failed to resolve the configured workspace path.") from exception
    return _validate_workspace_root_path(resolved, require_existing_directory=False)


def create_workspace_directory(real_path: str) -> None:
    if not real_path.strip():
        raise ValidationError("real_path must be a non-empty string.")
    if "\x00" in real_path:
        raise ValidationError("real_path contains an invalid character.")
    try:
        os.makedirs(real_path, exist_ok=True)
    except OSError as exception:
        raise ValidationError(
            "Failed to create or access the configured workspace path.",
        ) from exception


def resolve_existing_workspace_directory(workspace_path: str) -> str:
    return _validate_workspace_root_path(workspace_path, require_existing_directory=True)


def validate_workspace_directory_exists(real_path: str) -> None:
    _validate_workspace_root_path(real_path, require_existing_directory=True)
