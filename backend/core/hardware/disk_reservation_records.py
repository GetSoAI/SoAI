"""SoAI - Disk reservation record models [backend/core/hardware/disk_reservation_records.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, TypedDict

from core.errors.exceptions import StateError, ValidationError
from core.hardware.disk_reservation_processes import (
    is_process_reservation_stale,
    read_process_start_token,
)
from core.hardware.disk_usage import read_disk_usage_with_parent_fallback
from core.serialization.json import normalize_for_json
from core.timing.epoch import epoch_ms
from core.types.json_value import require_json_dict
from core.validation.integers import is_non_negative_strict_int
from core.validation.strict_numbers import require_non_negative_int_strict

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "DiskReservationPayload",
    "DiskReservationRecord",
    "DiskReservationTarget",
    "DiskSpaceReservationRequest",
    "build_disk_reservation_record",
    "is_disk_reservation_record_stale",
    "parse_disk_reservation_record",
    "resolve_disk_reservation_target",
)


@dataclass(frozen=True, slots=True)
class DiskSpaceReservationRequest:
    path: str
    required_bytes: int
    operation: str
    details: Mapping[str, JSONValue] | None = None


@dataclass(frozen=True, slots=True)
class DiskReservationTarget:
    check_path: str
    disk_usage_path: str
    mount_key: str
    total_bytes: int
    free_bytes: int
    used_bytes: int


class DiskReservationPayload(TypedDict):
    reservation_id: str
    pid: int
    process_start_token: str
    created_at_ms: int
    operation: str
    check_path: str
    disk_usage_path: str
    mount_key: str
    remaining_bytes: int
    original_required_bytes: int
    details: JSONDict


@dataclass(frozen=True, slots=True)
class DiskReservationRecord:
    reservation_id: str
    pid: int
    process_start_token: str
    created_at_ms: int
    operation: str
    check_path: str
    disk_usage_path: str
    mount_key: str
    remaining_bytes: int
    original_required_bytes: int
    details: JSONDict

    def to_json(self) -> DiskReservationPayload:
        return {
            "reservation_id": self.reservation_id,
            "pid": self.pid,
            "process_start_token": self.process_start_token,
            "created_at_ms": self.created_at_ms,
            "operation": self.operation,
            "check_path": self.check_path,
            "disk_usage_path": self.disk_usage_path,
            "mount_key": self.mount_key,
            "remaining_bytes": self.remaining_bytes,
            "original_required_bytes": self.original_required_bytes,
            "details": dict(self.details),
        }


def resolve_disk_reservation_target(path: str) -> DiskReservationTarget:
    if not path.strip():
        raise ValidationError("path is required to reserve disk space.")
    check_path = os.path.abspath(path)
    try:
        usage = read_disk_usage_with_parent_fallback(check_path)
        stat_result = os.stat(usage.disk_usage_path)
    except OSError as exception:
        raise StateError(
            f"Failed to read disk usage for '{check_path}'.",
            details={"path": check_path},
            cause=exception,
        ) from exception
    mount_key = f"device:{stat_result.st_dev}"
    return DiskReservationTarget(
        check_path=check_path,
        disk_usage_path=os.path.abspath(usage.disk_usage_path),
        mount_key=mount_key,
        total_bytes=usage.total_bytes,
        free_bytes=usage.free_bytes,
        used_bytes=usage.used_bytes,
    )


def build_disk_reservation_record(
    request: DiskSpaceReservationRequest,
    target: DiskReservationTarget,
) -> DiskReservationRecord:
    required_bytes = require_non_negative_int_strict(
        request.required_bytes,
        error_message="required_bytes must be a non-negative integer",
    )
    operation = _require_non_empty_string(
        request.operation,
        field="operation",
        message="operation is required to reserve disk space.",
    )
    details_value = normalize_for_json(request.details or {})
    details = require_json_dict(details_value, label="disk reservation details")
    return DiskReservationRecord(
        reservation_id=uuid.uuid4().hex,
        pid=os.getpid(),
        process_start_token=read_process_start_token(os.getpid()),
        created_at_ms=int(epoch_ms()),
        operation=operation,
        check_path=target.check_path,
        disk_usage_path=target.disk_usage_path,
        mount_key=target.mount_key,
        remaining_bytes=required_bytes,
        original_required_bytes=required_bytes,
        details=details,
    )


def parse_disk_reservation_record(payload: Mapping[str, JSONValue]) -> DiskReservationRecord:
    details_value = payload.get("details")
    details = require_json_dict(details_value or {}, label="disk reservation details")
    return DiskReservationRecord(
        reservation_id=_require_non_empty_string(
            payload.get("reservation_id"),
            field="reservation_id",
            message="Disk reservation record is missing reservation_id.",
        ),
        pid=_require_non_negative_int(payload.get("pid"), field="pid"),
        process_start_token=_require_string(payload.get("process_start_token")),
        created_at_ms=_require_non_negative_int(
            payload.get("created_at_ms"),
            field="created_at_ms",
        ),
        operation=_require_non_empty_string(
            payload.get("operation"),
            field="operation",
            message="Disk reservation record is missing operation.",
        ),
        check_path=_require_non_empty_string(
            payload.get("check_path"),
            field="check_path",
            message="Disk reservation record is missing check_path.",
        ),
        disk_usage_path=_require_non_empty_string(
            payload.get("disk_usage_path"),
            field="disk_usage_path",
            message="Disk reservation record is missing disk_usage_path.",
        ),
        mount_key=_require_non_empty_string(
            payload.get("mount_key"),
            field="mount_key",
            message="Disk reservation record is missing mount_key.",
        ),
        remaining_bytes=_require_non_negative_int(
            payload.get("remaining_bytes"),
            field="remaining_bytes",
        ),
        original_required_bytes=_require_non_negative_int(
            payload.get("original_required_bytes"),
            field="original_required_bytes",
        ),
        details=details,
    )


def is_disk_reservation_record_stale(record: DiskReservationRecord) -> bool:
    return is_process_reservation_stale(record.pid, record.process_start_token)


def _require_non_empty_string(value: JSONValue, *, field: str, message: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(message, details={"field": field})
    return value.strip()


def _require_string(value: JSONValue) -> str:
    if isinstance(value, str):
        return value
    return ""


def _require_non_negative_int(value: JSONValue, *, field: str) -> int:
    if not is_non_negative_strict_int(value):
        raise ValidationError(
            f"Disk reservation record field '{field}' must be a non-negative integer.",
        )
    return value
