"""SoAI - Restore disk reservation policy [backend/app/backup/restore_disk_reservations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import InsufficientDiskSpaceError, StateError, ValidationError

if TYPE_CHECKING:
    from core.hardware.protocols_storage import (
        DiskSpaceReservationLeaseProtocol,
        StorageManagerProtocol,
    )

__all__ = ("reserve_restore_disk_space",)


def reserve_restore_disk_space(
    *,
    storage_manager: StorageManagerProtocol,
    backups_path: str,
    backup_id: str,
    backup_path: str,
    snapshot_required_bytes: int,
    restore_required_bytes: int,
) -> tuple[DiskSpaceReservationLeaseProtocol, DiskSpaceReservationLeaseProtocol]:
    snapshot_reservation = storage_manager.reserve_disk_space(
        path=backups_path,
        required_bytes=snapshot_required_bytes,
        operation="application_restore.restore_backup",
        details={
            "purpose": "backup_restore_snapshot_path",
            "backup_id": backup_id,
            "backup_path": backup_path,
            "required_bytes": snapshot_required_bytes,
        },
    )
    try:
        restore_reservation = storage_manager.reserve_disk_space_for_install_volume(
            required_bytes=restore_required_bytes,
            operation="application_restore.restore_backup",
            details={
                "purpose": "backup_restore_install_volume",
                "backup_id": backup_id,
                "backup_path": backup_path,
                "required_bytes": restore_required_bytes,
            },
        )
    except (InsufficientDiskSpaceError, StateError, ValidationError):
        snapshot_reservation.release()
        raise
    return snapshot_reservation, restore_reservation
