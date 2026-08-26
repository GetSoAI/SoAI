"""SoAI - Disk-space validation error construction [backend/core/hardware/disk_space_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Mapping

from core.errors.exceptions import InsufficientDiskSpaceError, ValidationError
from core.formatting.bytes import format_bytes
from core.types.json import JSONDict, JSONValue
from core.validation.strict_numbers import require_non_negative_int_strict

__all__ = ("require_disk_space_available",)


def require_disk_space_available(
    *,
    check_path: str,
    available_bytes: int,
    required_bytes: int,
    tolerance_bytes: int,
    operation: str,
    details: Mapping[str, JSONValue] | None = None,
    mount_point: str | None = None,
    disk_usage_path: str | None = None,
) -> None:
    if not operation.strip():
        raise ValidationError("operation is required to validate disk space.")
    operation_value = operation.strip()
    if not check_path.strip():
        raise ValidationError("check_path is required to validate disk space.")
    check_path_value = check_path.strip()
    required_value = require_non_negative_int_strict(
        required_bytes,
        error_message="required_bytes must be a non-negative integer",
    )
    tolerance_value = require_non_negative_int_strict(
        tolerance_bytes,
        error_message="tolerance_bytes must be a non-negative integer",
    )
    available_value = require_non_negative_int_strict(
        available_bytes,
        error_message="available_bytes must be a non-negative integer",
    )
    required_total = required_value + tolerance_value
    if available_value >= required_total:
        return
    deficit = required_total - available_value
    error_details: JSONDict = {
        "operation": operation_value,
        "check_path": check_path_value,
        "required_bytes": required_value,
        "tolerance_bytes": tolerance_value,
        "required_with_tolerance_bytes": required_total,
        "available_bytes": available_value,
        "deficit_bytes": deficit,
    }
    if mount_point is not None:
        error_details["mount_point"] = mount_point
    if disk_usage_path is not None:
        error_details["disk_usage_path"] = disk_usage_path
    if details:
        error_details["context"] = dict(details)
    raise InsufficientDiskSpaceError(
        f"Insufficient disk space to start this operation. Required: {format_bytes(required_value)} (+ {format_bytes(tolerance_value)} safety tolerance = {format_bytes(required_total)}); Available: {format_bytes(available_value)} (short by {format_bytes(deficit)}).",
        details=error_details,
        operation=operation_value,
    )
