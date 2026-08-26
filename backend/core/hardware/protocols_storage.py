"""SoAI - Storage and disk reservation protocols [backend/core/hardware/protocols_storage.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Buffer, Mapping, Sequence
from types import TracebackType
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from core.hardware.disk_reservation_records import DiskSpaceReservationRequest
    from core.types.json import JSONValue

__all__ = (
    "BinaryWriteHandleProtocol",
    "DiskReservationLedgerProtocol",
    "DiskSpaceReservationLeaseProtocol",
    "DiskSpaceReservationProviderProtocol",
    "DiskSpaceSnapshotProtocol",
    "DiskSpaceWriteClaimProtocol",
    "StorageManagerProtocol",
)


class DiskReservationLedgerProtocol(Protocol):
    def claim_reservation_bytes(self, reservation_ids: Sequence[str], amount: int) -> str: ...
    def commit_reservation_claim(self, claim_id: str) -> None: ...
    def rollback_reservation_claim(self, claim_id: str) -> None: ...
    def release_reservations(self, reservation_ids: Sequence[str]) -> None: ...


class DiskSpaceWriteClaimProtocol(Protocol):
    def commit(self) -> None: ...
    def rollback(self) -> None: ...
    def __enter__(self) -> DiskSpaceWriteClaimProtocol: ...
    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...


class DiskSpaceReservationLeaseProtocol(Protocol):
    def claim_write_bytes(self, bytes_to_write: int) -> DiskSpaceWriteClaimProtocol: ...
    def release(self) -> None: ...
    def __enter__(self) -> DiskSpaceReservationLeaseProtocol: ...
    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...


class BinaryWriteHandleProtocol(Protocol):
    def write(self, data: Buffer, /) -> int | None: ...


class DiskSpaceReservationProviderProtocol(Protocol):
    def reserve_disk_space(
        self,
        *,
        path: str,
        required_bytes: int,
        operation: str,
        details: Mapping[str, JSONValue] | None = None,
    ) -> DiskSpaceReservationLeaseProtocol: ...
    def reserve_many_disk_spaces(
        self,
        *,
        requests: Sequence[DiskSpaceReservationRequest],
    ) -> DiskSpaceReservationLeaseProtocol: ...


class StorageManagerProtocol(Protocol):
    def reserve_disk_space(
        self,
        *,
        path: str,
        required_bytes: int,
        operation: str,
        details: Mapping[str, JSONValue] | None = None,
    ) -> DiskSpaceReservationLeaseProtocol: ...
    def reserve_many_disk_spaces(
        self,
        *,
        requests: Sequence[DiskSpaceReservationRequest],
    ) -> DiskSpaceReservationLeaseProtocol: ...
    def get_disk_space_tolerance_bytes(self) -> int: ...
    def snapshot_disk_space(self, path: str) -> DiskSpaceSnapshotProtocol: ...
    def require_free_disk_space(
        self,
        *,
        path: str,
        required_bytes: int,
        operation: str,
        details: Mapping[str, JSONValue] | None = None,
    ) -> DiskSpaceSnapshotProtocol: ...
    def reserve_disk_space_for_install_volume(
        self,
        *,
        required_bytes: int,
        operation: str,
        details: Mapping[str, JSONValue] | None = None,
    ) -> DiskSpaceReservationLeaseProtocol: ...


class DiskSpaceSnapshotProtocol(Protocol):
    @property
    def check_path(self) -> str: ...
    @property
    def mount_point(self) -> str | None: ...
    @property
    def total_bytes(self) -> int: ...
    @property
    def free_bytes(self) -> int: ...
    @property
    def used_bytes(self) -> int: ...
    @property
    def percent_used(self) -> float | None: ...
