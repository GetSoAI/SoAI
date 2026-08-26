"""SoAI - User-facing duration formatting helpers [backend/core/timing/duration_formatting.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

__all__ = ("format_delay_ms_for_user",)


def format_delay_ms_for_user(delay_ms: int) -> str:
    if isinstance(delay_ms, bool) or not isinstance(delay_ms, int | float):
        return "0s"

    normalized_ms = int(delay_ms)
    if normalized_ms <= 0:
        return "0s"
    if normalized_ms < 1000:
        return f"{normalized_ms}ms"

    seconds = normalized_ms / 1000.0
    formatted = f"{seconds:.2f}".rstrip("0").rstrip(".")
    return f"{formatted}s"
