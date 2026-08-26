"""SoAI - Hardware history row processing [backend/database/repositories/hardware/history_row_processing.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.config.numeric import coerce_float_or_none
from core.metrics.ohlc_gap_fill import build_gap_fill_entry

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "process_ohlc_rows",
    "process_standard_rows",
)


def process_ohlc_rows(
    expected_timestamps: list[int],
    row_map: dict[int, JSONDict],
    metric_cols: list[str],
) -> tuple[list[JSONDict], int]:
    data_rows: list[JSONDict] = []
    gap_count = 0
    last_closes: dict[str, float | None] = dict.fromkeys(metric_cols)
    for timestamp in expected_timestamps:
        row = row_map.get(timestamp)
        row_data: JSONDict = {}
        is_row_gap_filled = False
        if row:
            sample_count_raw = row.get("sample_count")
            if isinstance(sample_count_raw, int):
                sample_count = sample_count_raw
            elif isinstance(sample_count_raw, str | float):
                sample_count = int(sample_count_raw)
            else:
                sample_count = 0
            for col in metric_cols:
                open_val = coerce_float_or_none(row.get(f"{col}_open"))
                high_val = coerce_float_or_none(row.get(f"{col}_high"))
                low_val = coerce_float_or_none(row.get(f"{col}_low"))
                close_val = coerce_float_or_none(row.get(f"{col}_close"))
                avg_val = coerce_float_or_none(row.get(f"{col}_avg"))
                if all(
                    metric_value is None
                    for metric_value in (open_val, high_val, low_val, close_val)
                ):
                    row_data[col] = None
                    continue
                row_data[col] = {
                    "open": open_val,
                    "high": high_val,
                    "low": low_val,
                    "close": close_val,
                    "avg": (
                        avg_val
                        if avg_val is not None
                        else close_val if close_val is not None else open_val
                    ),
                    "count": sample_count,
                    "gap_fill": False,
                    "interpolated": False,
                }
                if close_val is not None:
                    last_closes[col] = close_val
        else:
            for col in metric_cols:
                last_close = last_closes.get(col)
                entry = build_gap_fill_entry(last_close)
                if entry is None:
                    row_data[col] = None
                    continue
                is_row_gap_filled = True
                row_data[col] = entry
        if is_row_gap_filled:
            gap_count += 1
        data_rows.append(row_data)
    return (data_rows, gap_count)


def process_standard_rows(
    expected_timestamps: list[int],
    row_map: dict[int, JSONDict],
    metric_cols: list[str],
) -> tuple[list[JSONDict], int]:
    data_rows: list[JSONDict] = []
    gap_count = 0
    for timestamp in expected_timestamps:
        row = row_map.get(timestamp)
        row_data: JSONDict = {}
        is_row_gap_filled = False
        if row:
            for col in metric_cols:
                row_data[col] = coerce_float_or_none(row.get(f"{col}_value"))
            if not any(value is not None for value in row_data.values()):
                is_row_gap_filled = True
        else:
            row_data = dict.fromkeys(metric_cols)
            is_row_gap_filled = True
        if is_row_gap_filled:
            gap_count += 1
        data_rows.append(row_data)
    return (data_rows, gap_count)
