"""SoAI - Time window validation helpers [backend/core/timing/windows.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ValidationError

__all__ = ("validate_strict_window_range",)


def validate_strict_window_range(*, start_ms: int, end_ms: int, message: str) -> None:
    if end_ms <= start_ms:
        raise ValidationError(message)
