"""SoAI - History export time window parsing [backend/core/history/request/export_window.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.files.export import validate_export_time_window
from core.validation.integers import require_non_negative_exact_int

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("parse_optional_export_time_window",)


def _parse_optional_export_epoch_ms(data: JSONDict, key: str) -> int | None:
    value = data.get(key)
    if value is None:
        return None
    return require_non_negative_exact_int(
        value,
        type_message=f"{key} must be a non-negative integer.",
        range_message=f"{key} must be a non-negative integer.",
    )


def parse_optional_export_time_window(data: JSONDict) -> tuple[int | None, int | None]:
    start_ts_ms, end_ts_ms = (
        _parse_optional_export_epoch_ms(data, "start_ts_ms"),
        _parse_optional_export_epoch_ms(data, "end_ts_ms"),
    )
    validate_export_time_window(page_size=1, start_ts_ms=start_ts_ms, end_ts_ms=end_ts_ms)
    return (start_ts_ms, end_ts_ms)
