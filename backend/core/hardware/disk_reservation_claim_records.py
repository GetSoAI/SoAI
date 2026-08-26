"""SoAI - Disk reservation claim record metadata [backend/core/hardware/disk_reservation_claim_records.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import replace

from core.hardware.disk_reservation_records import DiskReservationRecord
from core.timing.epoch import epoch_ms

__all__ = (
    "build_disk_reservation_claim_record",
    "disk_reservation_claim_id",
    "disk_reservation_claim_parent_id",
    "has_active_claim_for_parent",
    "is_matching_disk_reservation_claim",
)

CLAIM_ID_DETAIL_KEY = "claim_id"
CLAIM_PARENT_DETAIL_KEY = "claim_parent_reservation_id"
CLAIM_OPERATION_SUFFIX = ".write_claim"


def build_disk_reservation_claim_record(
    parent_record: DiskReservationRecord,
    claim_id: str,
    claimed_bytes: int,
) -> DiskReservationRecord:
    details = dict(parent_record.details)
    details[CLAIM_ID_DETAIL_KEY] = claim_id
    details[CLAIM_PARENT_DETAIL_KEY] = parent_record.reservation_id
    return replace(
        parent_record,
        reservation_id=uuid.uuid4().hex,
        created_at_ms=int(epoch_ms()),
        operation=f"{parent_record.operation}{CLAIM_OPERATION_SUFFIX}",
        remaining_bytes=claimed_bytes,
        original_required_bytes=claimed_bytes,
        details=details,
    )


def disk_reservation_claim_id(record: DiskReservationRecord) -> str:
    value = record.details.get(CLAIM_ID_DETAIL_KEY)
    return value if isinstance(value, str) and value else ""


def disk_reservation_claim_parent_id(record: DiskReservationRecord) -> str:
    value = record.details.get(CLAIM_PARENT_DETAIL_KEY)
    return value if isinstance(value, str) and value else ""


def is_matching_disk_reservation_claim(record: DiskReservationRecord, claim_id: str) -> bool:
    return disk_reservation_claim_id(record) == claim_id


def has_active_claim_for_parent(
    records: Sequence[DiskReservationRecord],
    parent_ids: set[str],
) -> bool:
    for record in records:
        if disk_reservation_claim_parent_id(record) in parent_ids:
            return True
    return False
