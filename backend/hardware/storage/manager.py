"""SoAI - Storage manager for disk space validation [backend/hardware/storage/manager.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import TYPE_CHECKING, override

from core.config.byte_sizes import require_config_mib_to_bytes
from core.config.numeric import coerce_positive_float
from core.errors.exceptions import StateError, ValidationError
from core.hardware.disk_reservation_ledger import DiskSpaceReservationLedger
from core.hardware.disk_reservation_operations import DiskReservationBackedStorage
from core.hardware.disk_space_validation import require_disk_space_available
from core.hardware.disk_usage import read_disk_usage_with_parent_fallback
from core.hardware.protocols_storage import (
    DiskSpaceSnapshotProtocol,
)
from core.timing.constants import CONTROL_TIMEOUT_SEC
from core.validation.strict_numbers import require_non_negative_int_strict
from hardware.storage.dependencies import StorageManagerDependencies
from hardware.storage.path_resolution import resolve_mount_point
from hardware.storage.snapshot import DiskSpaceSnapshot

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = ("StorageManager",)

DISK_RESERVATION_LEDGER_FILENAME = "disk_space_reservations_v1.json"
DISK_RESERVATION_LOCK_FILENAME = "disk_space_reservations_v1.lock"


class StorageManager(DiskReservationBackedStorage):
    def __init__(self, deps: StorageManagerDependencies) -> None:
        super().__init__(
            base_dir=os.path.abspath(deps.base_dir),
            reservation_ledger=DiskSpaceReservationLedger(
                ledger_path=os.path.join(
                    os.path.abspath(
                        deps.files.resolve_path(deps.config.require_str("SYSTEM.PATHS.LOCKS")),
                    ),
                    DISK_RESERVATION_LEDGER_FILENAME,
                ),
                lock_path=os.path.join(
                    os.path.abspath(
                        deps.files.resolve_path(deps.config.require_str("SYSTEM.PATHS.LOCKS")),
                    ),
                    DISK_RESERVATION_LOCK_FILENAME,
                ),
                lock_timeout_sec=coerce_positive_float(
                    deps.config.get(
                        "SYSTEM.HARDWARE.DISK_RESERVATION_LOCK_TIMEOUT_SEC",
                        CONTROL_TIMEOUT_SEC,
                    ),
                    default=CONTROL_TIMEOUT_SEC,
                    minimum=0.1,
                    label="SYSTEM.HARDWARE.DISK_RESERVATION_LOCK_TIMEOUT_SEC",
                ),
                tolerance_bytes=require_config_mib_to_bytes(
                    deps.config.get("SYSTEM.HARDWARE.DISK_FREE_SPACE_TOLERANCE_MB"),
                    field="SYSTEM.HARDWARE.DISK_FREE_SPACE_TOLERANCE_MB",
                    missing_message=(
                        "SYSTEM.HARDWARE.DISK_FREE_SPACE_TOLERANCE_MB must be a non-negative integer"
                    ),
                    invalid_message=(
                        "SYSTEM.HARDWARE.DISK_FREE_SPACE_TOLERANCE_MB must be a non-negative integer"
                    ),
                    positive_message=(
                        "SYSTEM.HARDWARE.DISK_FREE_SPACE_TOLERANCE_MB must be a non-negative integer"
                    ),
                    allow_zero=True,
                    build_error=ValidationError,
                ),
            ),
        )
        self._deps = deps
        self._locks_dir = self._resolve_locks_dir()

    @override
    def get_disk_space_tolerance_bytes(self) -> int:
        raw_value = self._deps.config.get("SYSTEM.HARDWARE.DISK_FREE_SPACE_TOLERANCE_MB")
        return require_config_mib_to_bytes(
            raw_value,
            field="SYSTEM.HARDWARE.DISK_FREE_SPACE_TOLERANCE_MB",
            missing_message=(
                "SYSTEM.HARDWARE.DISK_FREE_SPACE_TOLERANCE_MB must be a non-negative integer"
            ),
            invalid_message=(
                "SYSTEM.HARDWARE.DISK_FREE_SPACE_TOLERANCE_MB must be a non-negative integer"
            ),
            positive_message=(
                "SYSTEM.HARDWARE.DISK_FREE_SPACE_TOLERANCE_MB must be a non-negative integer"
            ),
            allow_zero=True,
            build_error=ValidationError,
        )

    @override
    def snapshot_disk_space(self, path: str) -> DiskSpaceSnapshotProtocol:
        if not path.strip():
            raise ValidationError("path is required to snapshot disk space.")
        normalized = os.path.abspath(path)
        usage_path = normalized
        try:
            disk_usage = read_disk_usage_with_parent_fallback(normalized)
            usage_path = disk_usage.disk_usage_path
        except OSError as exception:
            raise StateError(
                f"Failed to read disk usage for '{normalized}'.",
                details={"path": normalized, "disk_usage_path": usage_path},
                cause=exception,
            ) from exception
        return DiskSpaceSnapshot(
            check_path=normalized,
            mount_point=resolve_mount_point(normalized),
            total_bytes=disk_usage.total_bytes,
            free_bytes=disk_usage.free_bytes,
            used_bytes=disk_usage.used_bytes,
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
        if not operation.strip():
            raise ValidationError("operation is required to validate disk space.")
        required_value = require_non_negative_int_strict(
            required_bytes,
            error_message="required_bytes must be a non-negative integer",
        )
        tolerance_bytes = self.get_disk_space_tolerance_bytes()
        snapshot = self.snapshot_disk_space(path)
        require_disk_space_available(
            check_path=snapshot.check_path,
            mount_point=snapshot.mount_point,
            available_bytes=snapshot.free_bytes,
            required_bytes=required_value,
            tolerance_bytes=tolerance_bytes,
            operation=operation,
            details=details,
        )
        return snapshot

    def _resolve_locks_dir(self) -> str:
        raw_locks_path = self._deps.config.require_str("SYSTEM.PATHS.LOCKS")
        return os.path.abspath(self._deps.files.resolve_path(raw_locks_path))
