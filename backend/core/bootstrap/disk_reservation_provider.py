"""SoAI - Bootstrap disk reservation provider [backend/core/bootstrap/disk_reservation_provider.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import override

from core.bootstrap.disk_reservation_config import (
    resolve_bootstrap_disk_reservation_config,
)
from core.errors.exceptions import StateError, ValidationError
from core.hardware.disk_reservation_ledger import DiskSpaceReservationLedger
from core.hardware.disk_reservation_operations import DiskReservationBackedStorage
from core.hardware.disk_space_validation import require_disk_space_available
from core.hardware.disk_usage import read_disk_usage_with_parent_fallback
from core.hardware.protocols_storage import (
    DiskSpaceSnapshotProtocol,
)
from core.types.json import JSONValue

__all__ = (
    "BootstrapDiskReservationProvider",
    "create_bootstrap_disk_reservation_provider",
)

_DISK_RESERVATION_LEDGER_FILENAME = "disk_space_reservations_v1.json"
_DISK_RESERVATION_LOCK_FILENAME = "disk_space_reservations_v1.lock"


@dataclass(frozen=True, slots=True)
class _BootstrapDiskSpaceSnapshot:
    check_path: str
    mount_point: str | None
    total_bytes: int
    free_bytes: int
    used_bytes: int

    @property
    def percent_used(self) -> float | None:
        if self.total_bytes <= 0:
            return None
        return (self.used_bytes / self.total_bytes) * 100.0


class BootstrapDiskReservationProvider(DiskReservationBackedStorage):
    def __init__(
        self,
        *,
        base_dir: str,
        locks_dir: str,
        tolerance_bytes: int,
        lock_timeout_sec: float,
    ) -> None:
        if not base_dir.strip():
            raise ValidationError("Bootstrap disk reservation base_dir is required.")
        resolved_base_dir = os.path.abspath(base_dir)
        self._locks_dir = os.path.abspath(locks_dir)
        os.makedirs(self._locks_dir, exist_ok=True)
        self._tolerance_bytes = tolerance_bytes
        super().__init__(
            base_dir=resolved_base_dir,
            reservation_ledger=DiskSpaceReservationLedger(
                ledger_path=os.path.join(self._locks_dir, _DISK_RESERVATION_LEDGER_FILENAME),
                lock_path=os.path.join(self._locks_dir, _DISK_RESERVATION_LOCK_FILENAME),
                lock_timeout_sec=lock_timeout_sec,
                tolerance_bytes=tolerance_bytes,
            ),
        )

    @override
    def get_disk_space_tolerance_bytes(self) -> int:
        return self._tolerance_bytes

    @override
    def snapshot_disk_space(self, path: str) -> DiskSpaceSnapshotProtocol:
        if not isinstance(path, str) or not path.strip():
            raise ValidationError("path is required to snapshot disk space.")
        normalized = os.path.abspath(path)
        try:
            usage = read_disk_usage_with_parent_fallback(normalized)
        except OSError as exception:
            raise StateError(
                f"Failed to read disk usage for '{normalized}'.",
                details={"path": normalized},
                cause=exception,
            ) from exception
        return _BootstrapDiskSpaceSnapshot(
            check_path=normalized,
            mount_point=None,
            total_bytes=usage.total_bytes,
            free_bytes=usage.free_bytes,
            used_bytes=usage.used_bytes,
        )

    @override
    def require_free_disk_space(
        self,
        *,
        path: str,
        required_bytes: int,
        operation: str,
        details: Mapping[str, JSONValue] | None = None,
    ) -> DiskSpaceSnapshotProtocol:
        snapshot = self.snapshot_disk_space(path)
        require_disk_space_available(
            check_path=snapshot.check_path,
            available_bytes=snapshot.free_bytes,
            required_bytes=required_bytes,
            tolerance_bytes=self._tolerance_bytes,
            operation=operation,
            details=details,
        )
        return snapshot


def create_bootstrap_disk_reservation_provider(
    repo_root_path: str,
) -> BootstrapDiskReservationProvider:
    resolved_config = resolve_bootstrap_disk_reservation_config(repo_root_path)
    return BootstrapDiskReservationProvider(
        base_dir=resolved_config.base_dir,
        locks_dir=resolved_config.locks_dir,
        tolerance_bytes=resolved_config.tolerance_bytes,
        lock_timeout_sec=resolved_config.lock_timeout_sec,
    )
