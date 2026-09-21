"""SoAI - Shared upload size field and staged-size validation [backend/core/files/upload_size_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import PayloadTooLargeError, ValidationError
from core.validation.requirements import require_non_negative_exact_int

__all__ = (
    "STAGED_UPLOAD_SIZE_MISMATCH_MESSAGE",
    "UPLOAD_MAX_SIZE_EXCEEDED_MESSAGE",
    "ensure_safe_frontend_integer",
    "ensure_staged_size_matches_declared",
    "parse_size_bytes_field",
)

STAGED_UPLOAD_SIZE_MISMATCH_MESSAGE = "Upload size does not match declared size."
UPLOAD_MAX_SIZE_EXCEEDED_MESSAGE = "Upload exceeds configured maximum size."
MAX_SAFE_FRONTEND_INTEGER = 9_007_199_254_740_991


def parse_size_bytes_field(
    field_value: str,
    *,
    max_upload_bytes: int | None,
    field_name: str = "size_bytes",
) -> int:
    normalized_size = require_non_negative_exact_int(
        field_value,
        type_message=f"{field_name} must be an integer.",
        range_message=f"{field_name} must be >= 0.",
    )
    ensure_safe_frontend_integer(normalized_size, field_name=field_name)
    if max_upload_bytes is not None and normalized_size > max_upload_bytes:
        raise PayloadTooLargeError(UPLOAD_MAX_SIZE_EXCEEDED_MESSAGE)
    return normalized_size


def ensure_safe_frontend_integer(value: int, *, field_name: str) -> None:
    if value > MAX_SAFE_FRONTEND_INTEGER:
        raise ValidationError(f"{field_name} must be a safe integer.")


def ensure_staged_size_matches_declared(
    *,
    declared_size: int | None,
    staged_size: int,
) -> None:
    if declared_size is not None and staged_size != declared_size:
        raise ValidationError(STAGED_UPLOAD_SIZE_MISMATCH_MESSAGE)
