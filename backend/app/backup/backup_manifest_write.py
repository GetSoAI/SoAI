"""SoAI - Backup manifest disk-reserved writes [backend/app/backup/backup_manifest_write.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from app.backup.archive_io import serialize_manifest, write_manifest_content
from core.hardware.reservation_claims import claim_reserved_write

if TYPE_CHECKING:
    from core.backup.types import BackupManifest
    from core.hardware.protocols_storage import StorageManagerProtocol

__all__ = ("write_manifest_with_disk_reservation",)


async def write_manifest_with_disk_reservation(
    *,
    storage_manager: StorageManagerProtocol,
    manifest_path: str,
    manifest: BackupManifest,
    backup_id: str,
) -> None:
    manifest_content = serialize_manifest(manifest)
    manifest_bytes = len(manifest_content.encode("utf-8"))
    with storage_manager.reserve_disk_space(
        path=manifest_path,
        required_bytes=manifest_bytes,
        operation="application_backup.create_backup.manifest",
        details={
            "backup_id": backup_id,
            "manifest_path": manifest_path,
            "required_bytes": manifest_bytes,
        },
    ) as manifest_reservation:
        with claim_reserved_write(manifest_reservation, size_bytes=manifest_bytes):
            await asyncio.to_thread(write_manifest_content, manifest_path, manifest_content)
