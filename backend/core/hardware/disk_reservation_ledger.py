"""SoAI - Persistent disk reservation ledger [backend/core/hardware/disk_reservation_ledger.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import replace

from core.errors.exceptions import ValidationError
from core.hardware.disk_reservation_claim_records import (
    build_disk_reservation_claim_record,
    disk_reservation_claim_id,
    disk_reservation_claim_parent_id,
    has_active_claim_for_parent,
    is_matching_disk_reservation_claim,
)
from core.hardware.disk_reservation_leases import DiskSpaceReservationLease
from core.hardware.disk_reservation_records import (
    DiskReservationRecord,
    DiskSpaceReservationRequest,
    build_disk_reservation_record,
    resolve_disk_reservation_target,
)
from core.hardware.disk_reservation_store import DiskReservationFileStore
from core.hardware.disk_space_validation import require_disk_space_available
from core.validation.strict_numbers import require_non_negative_int_strict
from core.validation.strings import require_trimmed_json_text

__all__ = (
    "DiskSpaceReservationLease",
    "DiskSpaceReservationLedger",
)


class DiskSpaceReservationLedger:
    def __init__(
        self,
        *,
        ledger_path: str,
        lock_path: str,
        lock_timeout_sec: float,
        tolerance_bytes: int,
    ) -> None:
        self._store = DiskReservationFileStore(
            ledger_path=ledger_path,
            lock_path=lock_path,
            lock_timeout_sec=lock_timeout_sec,
        )
        self._tolerance_bytes = require_non_negative_int_strict(
            tolerance_bytes,
            error_message="tolerance_bytes must be a non-negative integer",
        )

    def reserve(self, request: DiskSpaceReservationRequest) -> DiskSpaceReservationLease:
        return self.reserve_many((request,))

    def reserve_many(
        self,
        requests: Sequence[DiskSpaceReservationRequest],
    ) -> DiskSpaceReservationLease:
        if not requests:
            return DiskSpaceReservationLease(self, ())
        with self._store.locked():
            active_records = self._store.read_active_records_locked()
            new_records: list[DiskReservationRecord] = []
            requested_by_mount: dict[str, int] = {}
            target_by_mount: dict[str, tuple[str, str, int]] = {}
            for request in requests:
                target = resolve_disk_reservation_target(request.path)
                record = build_disk_reservation_record(request, target)
                if record.remaining_bytes <= 0:
                    continue
                new_records.append(record)
                requested_by_mount[target.mount_key] = (
                    requested_by_mount.get(target.mount_key, 0) + record.remaining_bytes
                )
                target_by_mount[target.mount_key] = (
                    target.check_path,
                    target.disk_usage_path,
                    target.free_bytes,
                )
            active_by_mount = _sum_remaining_by_mount(active_records)
            for mount_key, requested_bytes in requested_by_mount.items():
                check_path, disk_usage_path, free_bytes = target_by_mount[mount_key]
                active_reserved_bytes = active_by_mount.get(mount_key, 0)
                available_after_active_reservations = max(0, free_bytes - active_reserved_bytes)
                require_disk_space_available(
                    check_path=check_path,
                    disk_usage_path=disk_usage_path,
                    available_bytes=available_after_active_reservations,
                    required_bytes=requested_bytes,
                    tolerance_bytes=self._tolerance_bytes,
                    operation="core.hardware.disk_space_reservation",
                    details={
                        "requested_operation": _first_operation_for_mount(new_records, mount_key),
                        "active_reserved_bytes": active_reserved_bytes,
                    },
                )
            if not new_records:
                return DiskSpaceReservationLease(self, ())
            self._store.write_records_locked((*active_records, *new_records))
        return DiskSpaceReservationLease(self, [record.reservation_id for record in new_records])

    def claim_reservation_bytes(self, reservation_ids: Sequence[str], amount: int) -> str:
        if not reservation_ids:
            raise ValidationError("Cannot claim bytes without an active disk reservation.")
        bytes_to_claim = require_non_negative_int_strict(
            amount,
            error_message="amount must be a non-negative integer",
        )
        if bytes_to_claim <= 0:
            raise ValidationError("Disk write claim amount must be greater than zero.")
        id_set = set(reservation_ids)
        claim_id = uuid.uuid4().hex
        with self._store.locked():
            records = self._store.read_active_records_locked()
            claimable_bytes = sum(
                record.remaining_bytes for record in records if record.reservation_id in id_set
            )
            if claimable_bytes < bytes_to_claim:
                raise ValidationError(
                    "Disk write claim exceeds remaining reservation bytes.",
                    details={
                        "requested_bytes": bytes_to_claim,
                        "remaining_bytes": claimable_bytes,
                    },
                )
            remaining_to_claim = bytes_to_claim
            updated_records: list[DiskReservationRecord] = []
            claim_records: list[DiskReservationRecord] = []
            for record in records:
                if record.reservation_id not in id_set or remaining_to_claim <= 0:
                    updated_records.append(record)
                    continue
                claimed = min(record.remaining_bytes, remaining_to_claim)
                updated_records.append(
                    replace(record, remaining_bytes=record.remaining_bytes - claimed),
                )
                claim_records.append(build_disk_reservation_claim_record(record, claim_id, claimed))
                remaining_to_claim -= claimed
            self._store.write_records_locked((*updated_records, *claim_records))
        return claim_id

    def commit_reservation_claim(self, claim_id: str) -> None:
        normalized_claim_id = _require_claim_id(claim_id)
        with self._store.locked():
            found_claim = False
            active_records = self._store.read_active_records_locked()
            records = [
                record
                for record in active_records
                if not is_matching_disk_reservation_claim(record, normalized_claim_id)
            ]
            found_claim = len(records) != len(active_records)
            if not found_claim:
                raise ValidationError("Disk write claim is not active.")
            self._store.write_records_locked(records)

    def rollback_reservation_claim(self, claim_id: str) -> None:
        normalized_claim_id = _require_claim_id(claim_id)
        with self._store.locked():
            records = self._store.read_active_records_locked()
            claim_records = [
                record
                for record in records
                if disk_reservation_claim_id(record) == normalized_claim_id
            ]
            if not claim_records:
                raise ValidationError("Disk write claim is not active.")
            rollback_by_parent: dict[str, int] = {}
            for record in claim_records:
                parent_id = disk_reservation_claim_parent_id(record)
                if not parent_id:
                    raise ValidationError("Disk write claim is missing its parent reservation.")
                rollback_by_parent[parent_id] = (
                    rollback_by_parent.get(parent_id, 0) + record.remaining_bytes
                )
            restored_parent_ids: set[str] = set()
            updated_records: list[DiskReservationRecord] = []
            for active_record in records:
                if disk_reservation_claim_id(active_record) == normalized_claim_id:
                    continue
                restore_bytes = rollback_by_parent.get(active_record.reservation_id, 0)
                updated_record = active_record
                if restore_bytes > 0:
                    updated_record = replace(
                        active_record,
                        remaining_bytes=active_record.remaining_bytes + restore_bytes,
                    )
                    restored_parent_ids.add(active_record.reservation_id)
                updated_records.append(updated_record)
            missing_parents = set(rollback_by_parent).difference(restored_parent_ids)
            if missing_parents:
                raise ValidationError(
                    "Disk write claim parent reservation is no longer active.",
                    details={"parent_reservation_ids": sorted(missing_parents)},
                )
            self._store.write_records_locked(updated_records)

    def release_reservations(self, reservation_ids: Sequence[str]) -> None:
        if not reservation_ids:
            return
        id_set = set(reservation_ids)
        with self._store.locked():
            active_records = self._store.read_active_records_locked()
            if has_active_claim_for_parent(active_records, id_set):
                raise ValidationError("Cannot release a disk reservation with active claims.")
            records = [record for record in active_records if record.reservation_id not in id_set]
            self._store.write_records_locked(records)


def _sum_remaining_by_mount(records: Sequence[DiskReservationRecord]) -> dict[str, int]:
    result: dict[str, int] = {}
    for record in records:
        result[record.mount_key] = result.get(record.mount_key, 0) + record.remaining_bytes
    return result


def _first_operation_for_mount(records: Sequence[DiskReservationRecord], mount_key: str) -> str:
    for record in records:
        if record.mount_key == mount_key:
            return record.operation
    return ""


def _require_claim_id(value: str) -> str:
    return require_trimmed_json_text(value, error_message="Disk write claim id is required.")
