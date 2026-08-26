"""SoAI - Plugin filesystem permission helpers [backend/plugins/fs_permissions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os

from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.filesystem.open_files import open_binary
from core.logging.trace import get_logger

__all__ = ("ensure_correct_permissions", "ensure_single_path_permissions")

LOGGER_NAME = "SoAI.plugins.fs_permissions"
OPERATION = "plugin_helper.ensure_correct_permissions"


def _apply_single_permission(target_path: str, is_dir: bool) -> None:
    if os.path.islink(target_path):
        return
    mode = 0o755 if is_dir else 0o644
    if not is_dir:
        try:
            with open_binary(target_path, mode="rb") as handle:
                header = handle.read(4)
            if header.startswith(b"#!") or header.startswith(b"\x7fELF"):
                mode |= 0o111
        except OSError:
            return
    try:
        os.chmod(target_path, mode)
    except OSError:
        return


def _apply_permissions_recursively(root_path: str) -> None:
    if not os.path.exists(root_path):
        return
    is_root_dir = os.path.isdir(root_path)
    _apply_single_permission(root_path, is_root_dir)
    if not is_root_dir:
        return
    for walked_root, directories, filenames in os.walk(root_path, topdown=True):
        if "venv" in walked_root.lower() or os.path.islink(walked_root):
            directories[:] = []
            continue
        allowed_directories: list[str] = []
        for directory_name in list(directories):
            directory_path = os.path.join(walked_root, directory_name)
            if "venv" in directory_name.lower() or os.path.islink(directory_path):
                continue
            allowed_directories.append(directory_name)
            _apply_single_permission(directory_path, True)
        directories[:] = allowed_directories
        for file_name in filenames:
            _apply_single_permission(os.path.join(walked_root, file_name), False)


async def ensure_correct_permissions(path: str) -> None:
    logger = get_logger(LOGGER_NAME)
    if not path:
        return
    try:
        await asyncio.to_thread(_apply_permissions_recursively, path)
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message="Could not set permissions for path.",
            operation=OPERATION,
            details={"path": path},
            level="warning",
        )


async def ensure_single_path_permissions(path: str) -> None:
    logger = get_logger(LOGGER_NAME)
    if not path:
        return
    try:
        await asyncio.to_thread(_apply_single_permission, path, os.path.isdir(path))
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message="Could not set permissions for path.",
            operation=OPERATION,
            details={"path": path},
            level="warning",
        )
