"""SoAI - Hardware metrics OHLC post-processing [backend/hardware/manager/ohlc_post_processing.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from core.config.numeric import coerce_float_or_none
from core.logging.trace import get_logger
from core.metrics.ohlc_gap_fill import build_gap_fill_entry
from core.types.json import is_json_value
from core.validation.boolean_coercion import coerce_bool_flag
from core.validation.coercion import coerce_non_negative_int_from_numberish

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = ("post_process_ohlc_data",)

LOGGER_NAME = "SoAI.hardware.manager.ohlc_post_processing"


def post_process_ohlc_data(
    history_data: JSONDict,
    expected_timestamps: list[int],
) -> JSONDict:
    logger = get_logger(LOGGER_NAME)

    def _normalise_entry(entry: JSONValue) -> JSONDict | None:
        if not isinstance(entry, dict):
            return None
        open_val = coerce_float_or_none(entry.get("open"))
        high_val = coerce_float_or_none(entry.get("high"))
        low_val = coerce_float_or_none(entry.get("low"))
        close_val = coerce_float_or_none(entry.get("close"))
        avg_val = coerce_float_or_none(entry.get("avg")) or (
            close_val if close_val is not None else open_val
        )
        if all(value is None for value in (open_val, high_val, low_val, close_val)):
            return None
        count_val = coerce_non_negative_int_from_numberish(entry.get("count"))
        return {
            "open": open_val,
            "high": high_val,
            "low": low_val,
            "close": close_val,
            "avg": avg_val,
            "count": count_val,
            "gap_fill": coerce_bool_flag(
                entry.get("gap_fill"),
                logger=logger,
                operation="hardware.manager.ohlc_post_processing.coerce_bool_flag",
                default=False,
                recover_message="Failed to parse boolean flag (non-critical).",
            ),
            "interpolated": coerce_bool_flag(
                entry.get("interpolated"),
                logger=logger,
                operation="hardware.manager.ohlc_post_processing.coerce_bool_flag",
                default=False,
                recover_message="Failed to parse boolean flag (non-critical).",
            ),
        }

    raw_timestamps_value = history_data.get("timestamps_ms")
    raw_timestamps = raw_timestamps_value if isinstance(raw_timestamps_value, list) else []
    metrics_value = history_data.get("metrics")
    metrics = (
        [item for item in metrics_value if isinstance(item, str)]
        if isinstance(metrics_value, list)
        else []
    )
    data_rows_value = history_data.get("data")
    data_rows = data_rows_value if isinstance(data_rows_value, list) else []
    timestamp_to_row: dict[int, JSONValue] = {}
    for timestamp, row in zip(raw_timestamps, data_rows, strict=False):
        if isinstance(timestamp, bool):
            timestamp_int = int(timestamp)
        elif isinstance(timestamp, int | float | str):
            try:
                timestamp_int = int(timestamp)
            except (TypeError, ValueError):
                continue
        else:
            continue
        timestamp_to_row[timestamp_int] = row
    normalised_rows: list[JSONDict] = []
    last_closes: dict[str, float | None] = {}

    def _build_gap_row(
        metric_names: Sequence[str],
        last_close_vals: dict[str, float | None],
    ) -> JSONDict:
        row: JSONDict = {}
        for metric_name in metric_names:
            last_close = last_close_vals.get(metric_name)
            row[metric_name] = build_gap_fill_entry(last_close)
        return row

    for timestamp in expected_timestamps:
        existing_row = timestamp_to_row.get(timestamp)
        if isinstance(existing_row, dict):
            normalised_row: JSONDict = {}
            for metric_name in metrics:
                normalised_entry = _normalise_entry(existing_row.get(metric_name))
                if (
                    normalised_entry is not None
                    and (close_value := normalised_entry.get("close")) is not None
                ):
                    if isinstance(close_value, int | float):
                        last_closes[metric_name] = float(close_value)
                normalised_row[metric_name] = normalised_entry
            normalised_rows.append(normalised_row)
        else:
            normalised_rows.append(_build_gap_row(metrics, last_closes))
    history_data["timestamps_ms"] = expected_timestamps
    history_data["data"] = normalised_rows
    gap_count = 0
    for row in normalised_rows:
        if any(
            coerce_bool_flag(
                entry.get("gap_fill"),
                logger=logger,
                operation="hardware.manager.ohlc_post_processing.coerce_bool_flag",
                default=False,
                recover_message="Failed to parse boolean flag (non-critical).",
            )
            for entry in row.values()
            if isinstance(entry, dict)
        ):
            gap_count += 1
    metadata_value = history_data.get("metadata")
    metadata: JSONDict = {}
    if isinstance(metadata_value, dict):
        for key, value in metadata_value.items():
            if isinstance(key, str) and is_json_value(value):
                metadata[key] = value
    metadata["bucket_gap_count"] = gap_count
    history_data["metadata"] = metadata
    return history_data
