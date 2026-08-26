"""SoAI - Cancellation ID normalization [backend/core/tasks/cancellation_ids.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ValidationError

__all__ = (
    "SYSTEM_CANCELLATION_ID_PREFIX",
    "is_system_cancellation_id",
    "normalize_cancellation_id",
    "require_cancellation_id",
)

SYSTEM_CANCELLATION_ID_PREFIX = "soai::sys::"


def normalize_cancellation_id(value: str | int | None) -> str:
    raw_value = "" if value is None else str(value)
    return raw_value.strip()


def require_cancellation_id(value: str | int | None) -> str:
    normalized = normalize_cancellation_id(value)
    if not normalized:
        raise ValidationError("cancellation_id must be a non-empty string.")
    return normalized


def is_system_cancellation_id(value: str | int | None) -> bool:
    normalized = normalize_cancellation_id(value)
    return normalized.startswith(SYSTEM_CANCELLATION_ID_PREFIX)
