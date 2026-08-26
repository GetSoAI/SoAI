"""SoAI - Updater disk space checks [backend/app/updater/disk_space.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os

from core.errors.exceptions import StateError, ValidationError
from core.hardware.disk_space_validation import require_disk_space_available
from core.hardware.disk_usage import read_disk_usage_with_parent_fallback
from core.validation.strict_numbers import require_non_negative_int_strict

__all__ = ("require_disk_space_for_update",)


def require_disk_space_for_update(
    path: str,
    required_bytes: int,
    tolerance_bytes: int,
    *,
    operation: str = "application_updater.check_disk_space_for_update",
) -> bool:
    if not path.strip():
        raise ValidationError("path is required to validate disk space.")
    if not operation.strip():
        raise ValidationError("operation is required to validate disk space.")
    required_value = require_non_negative_int_strict(
        required_bytes,
        error_message="required_bytes must be a non-negative integer.",
    )
    tolerance_value_bytes = require_non_negative_int_strict(
        tolerance_bytes,
        error_message="tolerance_bytes must be a non-negative integer.",
    )
    disk_usage_path = os.path.abspath(path)
    try:
        snapshot = read_disk_usage_with_parent_fallback(path)
        disk_usage_path = snapshot.disk_usage_path
        require_disk_space_available(
            check_path=snapshot.check_path,
            disk_usage_path=snapshot.disk_usage_path,
            available_bytes=snapshot.free_bytes,
            required_bytes=required_value,
            tolerance_bytes=tolerance_value_bytes,
            operation=operation,
        )
        return True
    except OSError as exception:
        raise StateError(
            f"Failed to check disk space for '{os.path.abspath(path)}'.",
            details={"path": os.path.abspath(path), "disk_usage_path": disk_usage_path},
            operation=operation,
            cause=exception,
        ) from exception
