"""SoAI - Backup manifest entry builders [backend/app/backup/manifest_entries.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
import os

from core.backup.types import BackupFileEntry
from core.errors.exceptions import SecurityError, ValidationError
from core.filesystem.hashing import calculate_file_hash

__all__ = ("build_file_manifest_entry",)


async def build_file_manifest_entry(path: str) -> BackupFileEntry:
    if not path.strip():
        raise ValidationError("path is required.")
    file_hash = await calculate_file_hash(path)
    if not isinstance(file_hash, str) or not file_hash:
        raise SecurityError(f"Failed to compute hash for {path}.")
    size = await asyncio.to_thread(os.path.getsize, path)
    entry: BackupFileEntry = {"type": "file", "sha256": file_hash, "size": int(size)}
    return entry
