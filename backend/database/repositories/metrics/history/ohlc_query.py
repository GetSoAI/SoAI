"""SoAI - Metrics history OHLC query [backend/database/repositories/metrics/history/ohlc_query.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

import aiosqlite

from core.config.numeric import coerce_float_or_none
from core.metrics.ohlc_gap_fill import build_gap_fill_entry
from database.core.sqlite_numbers import coerce_non_negative_int_from_sqlite
from database.repositories.metrics.history.history_query_scaffold import (
    fetch_metric_history_index_or_empty_payload,
)
from database.repositories.metrics.history.sql_templates import ohlc_sql

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("get_ohlc_historical_data",)


async def get_ohlc_historical_data(
    database: aiosqlite.Connection,
    metric_key: str,
    start_ts_ms: int,
    end_ts_ms: int,
    sanitized_interval_ms: int,
    limit: int,
    anchor_ts_ms: int,
    aggregation: str,
) -> JSONDict:
    index_or_payload = await fetch_metric_history_index_or_empty_payload(
        database,
        ohlc_sql(aggregation),
        metric_key=metric_key,
        start_ts_ms=start_ts_ms,
        end_ts_ms=end_ts_ms,
        anchor_ts_ms=anchor_ts_ms,
        sanitized_interval_ms=sanitized_interval_ms,
        limit=limit,
        empty_extra={"ohlc": []},
    )
    if isinstance(index_or_payload, dict):
        return index_or_payload

    expected_timestamps, row_map, _bucket_count = index_or_payload

    ohlc_series: list[JSONDict | None] = []
    close_values: list[float | None] = []
    gap_count = 0
    last_close: float | None = None
    for timestamp in expected_timestamps:
        row = row_map.get(timestamp)
        if row:
            open_val = coerce_float_or_none(row.get("open_value"))
            high_val = coerce_float_or_none(row.get("high_value"))
            low_val = coerce_float_or_none(row.get("low_value"))
            close_val = coerce_float_or_none(row.get("close_value"))
            avg_val = coerce_float_or_none(row.get("avg_value"))
            sample_count = coerce_non_negative_int_from_sqlite(row.get("sample_count"))
            entry: JSONDict | None
            if all(value is None for value in (open_val, high_val, low_val, close_val)):
                entry = None
                close_values.append(None)
            else:
                if avg_val is None:
                    avg_val = close_val if close_val is not None else open_val
                entry = {
                    "open": open_val,
                    "high": high_val,
                    "low": low_val,
                    "close": close_val,
                    "avg": avg_val,
                    "count": sample_count,
                    "gap_fill": False,
                    "interpolated": False,
                }
                if close_val is not None:
                    last_close = close_val
                close_values.append(close_val)
            ohlc_series.append(entry)
        elif last_close is not None:
            gap_entry = build_gap_fill_entry(last_close)
            if gap_entry is None:
                ohlc_series.append(None)
                close_values.append(None)
                continue
            ohlc_series.append(gap_entry)
            close_values.append(last_close)
            gap_count += 1
        else:
            ohlc_series.append(None)
            close_values.append(None)

    metadata: JSONDict = {
        "bucket_gap_count": gap_count,
        "bucket_count": len(expected_timestamps),
        "aligned_start_ts_ms": (expected_timestamps[0] if expected_timestamps else anchor_ts_ms),
        "aligned_end_ts_ms": expected_timestamps[-1] if expected_timestamps else None,
    }
    return {
        "timestamps_ms": expected_timestamps,
        "values": close_values,
        "ohlc": ohlc_series,
        "interval_ms": sanitized_interval_ms,
        "metadata": metadata,
    }
