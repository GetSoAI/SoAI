"""SoAI - Packaged bootstrap asset path validation [backend/core/bootstrap/packaged_asset_paths.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import stat

from core.errors.exceptions import StateError
from core.files.windows_reparse_points import is_windows_reparse_point

__all__ = ("resolve_packaged_asset",)


def resolve_packaged_asset(
    repo_root_path: str,
    *,
    selected_directory: tuple[str, ...],
    filename: str,
    managed_asset: str,
) -> str | None:
    current_path = os.path.abspath(repo_root_path)
    for component in selected_directory:
        current_path = os.path.join(current_path, component)
        if not os.path.lexists(current_path):
            return None
        _require_plain_directory(current_path, managed_asset)
    archive_path = os.path.join(current_path, filename)
    if not os.path.lexists(archive_path):
        raise StateError(f"Packaged {managed_asset} directory is present but its asset is missing.")
    _require_plain_file(archive_path, managed_asset)
    return archive_path


def _require_plain_directory(path: str, managed_asset: str) -> None:
    try:
        status = os.lstat(path)
    except OSError as exception:
        raise StateError(f"Packaged {managed_asset} directory is unreadable.") from exception
    if not stat.S_ISDIR(status.st_mode) or _is_redirected(status):
        raise StateError(f"Packaged {managed_asset} directory is unsafe.")


def _require_plain_file(path: str, managed_asset: str) -> None:
    try:
        status = os.lstat(path)
    except OSError as exception:
        raise StateError(f"Packaged {managed_asset} asset is unreadable.") from exception
    if not stat.S_ISREG(status.st_mode) or _is_redirected(status):
        raise StateError(f"Packaged {managed_asset} asset is unsafe.")


def _is_redirected(status: os.stat_result) -> bool:
    return stat.S_ISLNK(status.st_mode) or is_windows_reparse_point(status)
