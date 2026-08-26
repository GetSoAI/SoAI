"""SoAI - Backup slot allocation helpers [backend/app/backup/backup_slots.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os

from app.backup.backup_naming import generate_unique_backup_path
from core.errors.exceptions import ConcurrencyError, ValidationError

__all__ = ("create_backup_slot",)


def create_backup_slot(backups_path: str) -> tuple[str, str]:
    if not backups_path.strip():
        raise ValidationError("backups_path is required.")
    for _attempt in range(1000):
        final_path, part_path = generate_unique_backup_path(backups_path)
        try:
            os.makedirs(part_path, mode=0o700, exist_ok=False)
            return final_path, part_path
        except FileExistsError:
            continue
    raise ConcurrencyError(
        "Failed to allocate a unique backup staging directory.",
        details={"backups_path": backups_path},
    )
