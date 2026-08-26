"""SoAI - Backup directory permissions helpers [backend/app/backup/copy_no_symlinks/permissions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os

from core.errors.exceptions import SecurityError, ValidationError

__all__ = ("ensure_backup_directory_permissions",)


async def ensure_backup_directory_permissions(
    backup_root: str,
    *,
    is_windows: bool,
    force_walk: bool = False,
) -> None:
    if is_windows:
        return
    if not backup_root.strip():
        raise ValidationError("backup_root is required.")

    def _apply_permissions() -> None:
        try:
            os.chmod(backup_root, 0o700)
        except OSError as exception:
            raise SecurityError(
                f"Failed to set permissions on backup root '{backup_root}'.",
            ) from exception
        if not force_walk:
            return
        for root, dirs, files in os.walk(backup_root, followlinks=False):
            for directory_name in dirs:
                directory_path = os.path.join(root, directory_name)
                if os.path.islink(directory_path):
                    continue
                os.chmod(directory_path, 0o700)
            for file_name in files:
                file_path = os.path.join(root, file_name)
                if os.path.islink(file_path):
                    continue
                os.chmod(file_path, 0o600)

    await asyncio.to_thread(_apply_permissions)
