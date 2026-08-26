"""SoAI - Metrics history payload validation [backend/metrics/manager/history_payloads.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ProcessError, StateError, ValidationError
from core.validation.numbers import coerce_int_from_json

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = (
    "process_ohlc_history",
    "process_standard_history",
)


def _coerce_timestamp(value: JSONValue) -> int:
    parsed = coerce_int_from_json(value, default=None, parse_float_strings=True)
    if parsed is None:
        raise ValidationError("Timestamp must be an integer.")
    return parsed


def _coerce_timestamps(
    history_data: JSONDict,
    metric_key: str,
    aggregation: str,
) -> list[int]:
    timestamps_raw = history_data.get("timestamps_ms", [])
    if not isinstance(timestamps_raw, list):
        raise ProcessError(
            "History timestamps payload must be a list.",
            details={"metric_key": metric_key, "aggregation": aggregation},
        )
    try:
        return [_coerce_timestamp(timestamp) for timestamp in timestamps_raw]
    except ValidationError as exception:
        raise ProcessError(
            "History timestamps contain invalid values.",
            details={"metric_key": metric_key, "aggregation": aggregation},
        ) from exception


def _require_aligned_timestamps(
    timestamps: list[int],
    expected_timestamps: list[int],
    metric_key: str,
    aggregation: str,
) -> None:
    if not timestamps or timestamps == expected_timestamps:
        return
    expected_start = expected_timestamps[0] if expected_timestamps else None
    expected_end = expected_timestamps[-1] if expected_timestamps else None
    raise StateError(
        "History timestamps are misaligned with the resolved bucket resolution.",
        details={
            "metric_key": metric_key,
            "aggregation": aggregation,
            "expected_start": expected_start,
            "expected_end": expected_end,
            "returned_start": timestamps[0],
            "returned_end": timestamps[-1],
            "expected_count": len(expected_timestamps),
            "returned_count": len(timestamps),
        },
    )


def process_ohlc_history(
    history_data: JSONDict,
    expected_timestamps: list[int],
    metric_key: str,
) -> int:
    aggregation = "ohlc"
    timestamps = _coerce_timestamps(history_data, metric_key, aggregation)
    _require_aligned_timestamps(timestamps, expected_timestamps, metric_key, aggregation)
    ohlc_rows = history_data.get("ohlc", [])
    values = history_data.get("values", [])
    if not isinstance(ohlc_rows, list) or not isinstance(values, list):
        raise ProcessError(
            "History OHLC payload must contain list fields.",
            details={"metric_key": metric_key, "aggregation": aggregation},
        )
    if len(timestamps) != len(ohlc_rows) or len(timestamps) != len(values):
        raise ProcessError(
            "History OHLC payload length mismatch.",
            details={
                "metric_key": metric_key,
                "aggregation": aggregation,
                "timestamps": len(timestamps),
                "ohlc": len(ohlc_rows),
                "values": len(values),
            },
        )
    gap_count = sum(
        1 for entry in ohlc_rows if isinstance(entry, dict) and entry.get("gap_fill") is True
    )
    history_data["timestamps_ms"] = timestamps
    return gap_count


def process_standard_history(
    history_data: JSONDict,
    expected_timestamps: list[int],
    metric_key: str,
    aggregation: str,
) -> int:
    timestamps = _coerce_timestamps(history_data, metric_key, aggregation)
    _require_aligned_timestamps(timestamps, expected_timestamps, metric_key, aggregation)
    values = history_data.get("values", [])
    if not isinstance(values, list):
        raise ProcessError(
            "History values payload must be a list.",
            details={"metric_key": metric_key, "aggregation": aggregation},
        )
    if len(timestamps) != len(values):
        raise ProcessError(
            "History values payload length mismatch.",
            details={
                "metric_key": metric_key,
                "aggregation": aggregation,
                "timestamps": len(timestamps),
                "values": len(values),
            },
        )
    gap_count = sum(1 for value in values if value is None)
    history_data["timestamps_ms"] = timestamps
    return gap_count
