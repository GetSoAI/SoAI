"""SoAI - Seconds value coercion helpers [backend/core/timing/seconds_coercion.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = (
    "coerce_timeout_log_value",
    "format_timeout_seconds",
)


def coerce_timeout_log_value(value: JSONValue) -> float | int | str | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float | str | type(None)):
        return value
    return None


def format_timeout_seconds(raw_timeout: float | str | None) -> str:
    if raw_timeout is None or isinstance(raw_timeout, bool):
        return "N/A"
    try:
        return f"{float(raw_timeout):.3f}s"
    except (TypeError, ValueError):
        return "N/A"
