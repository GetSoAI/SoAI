"""SoAI - Automation occurrence window bounds validation [backend/features/automation/occurrence_window_bounds.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ValidationError
from core.timing.windows import validate_strict_window_range

__all__ = (
    "validate_window_max_items",
    "validate_window_pagination",
    "validate_window_range",
)


def validate_window_range(from_utc_ms: int, to_utc_ms: int) -> None:
    validate_strict_window_range(
        start_ms=from_utc_ms,
        end_ms=to_utc_ms,
        message="Automation window start must be before its end.",
    )


def validate_window_max_items(max_items: int | None) -> None:
    if max_items is not None and max_items <= 0:
        raise ValidationError("Automation window max_items must be positive.")


def validate_window_pagination(limit: int, offset: int) -> None:
    if limit <= 0:
        raise ValidationError("limit must be positive.")
    if offset < 0:
        raise ValidationError("offset must be non-negative.")
