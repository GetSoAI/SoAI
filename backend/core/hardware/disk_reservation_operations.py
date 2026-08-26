"""SoAI - Disk reservation operation primitives [backend/core/hardware/disk_reservation_operations.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import override

from core.hardware.disk_reservation_ledger import DiskSpaceReservationLedger
from core.hardware.disk_reservation_records import DiskSpaceReservationRequest
from core.hardware.protocols_storage import (
    DiskSpaceReservationLeaseProtocol,
    DiskSpaceSnapshotProtocol,
    StorageManagerProtocol,
)
from core.types.json import JSONValue

__all__ = (
    "DiskReservationBackedStorage",
    "require_install_volume_free_disk_space",
    "reserve_disk_space_for_path",
    "reserve_install_volume_disk_space",
    "reserve_many_disk_spaces_with_ledger",
)


class DiskReservationBackedStorage(StorageManagerProtocol):
    def __init__(
        self,
        *,
        base_dir: str,
        reservation_ledger: DiskSpaceReservationLedger,
    ) -> None:
        self.base_dir = base_dir
        self._reservation_ledger = reservation_ledger

    @override
    def reserve_disk_space(
        self,
        *,
        path: str,
        required_bytes: int,
        operation: str,
        details: Mapping[str, JSONValue] | None = None,
    ) -> DiskSpaceReservationLeaseProtocol:
        return reserve_disk_space_for_path(
            self._reservation_ledger,
            path=path,
            required_bytes=required_bytes,
            operation=operation,
            details=details,
        )

    @override
    def reserve_many_disk_spaces(
        self,
        *,
        requests: Sequence[DiskSpaceReservationRequest],
    ) -> DiskSpaceReservationLeaseProtocol:
        return reserve_many_disk_spaces_with_ledger(
            self._reservation_ledger,
            requests=requests,
        )

    @override
    def reserve_disk_space_for_install_volume(
        self,
        *,
        required_bytes: int,
        operation: str,
        details: Mapping[str, JSONValue] | None = None,
    ) -> DiskSpaceReservationLeaseProtocol:
        return reserve_install_volume_disk_space(
            self,
            base_dir=self.base_dir,
            required_bytes=required_bytes,
            operation=operation,
            details=details,
        )


def require_install_volume_free_disk_space(
    storage_manager: StorageManagerProtocol,
    *,
    base_dir: str,
    required_bytes: int,
    operation: str,
    details: Mapping[str, JSONValue] | None,
) -> DiskSpaceSnapshotProtocol:
    return storage_manager.require_free_disk_space(
        path=base_dir,
        required_bytes=required_bytes,
        operation=operation,
        details=details,
    )


def reserve_disk_space_for_path(
    ledger: DiskSpaceReservationLedger,
    *,
    path: str,
    required_bytes: int,
    operation: str,
    details: Mapping[str, JSONValue] | None,
) -> DiskSpaceReservationLeaseProtocol:
    return ledger.reserve(
        DiskSpaceReservationRequest(
            path=path,
            required_bytes=required_bytes,
            operation=operation,
            details=details,
        ),
    )


def reserve_many_disk_spaces_with_ledger(
    ledger: DiskSpaceReservationLedger,
    *,
    requests: Sequence[DiskSpaceReservationRequest],
) -> DiskSpaceReservationLeaseProtocol:
    return ledger.reserve_many(requests)


def reserve_install_volume_disk_space(
    storage_manager: StorageManagerProtocol,
    *,
    base_dir: str,
    required_bytes: int,
    operation: str,
    details: Mapping[str, JSONValue] | None,
) -> DiskSpaceReservationLeaseProtocol:
    return storage_manager.reserve_disk_space(
        path=base_dir,
        required_bytes=required_bytes,
        operation=operation,
        details=details,
    )
