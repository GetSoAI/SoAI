"""SoAI - Hardware history queries with time aggregation [backend/database/repositories/hardware/history.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

import aiosqlite

from core.errors.exceptions import ValidationError
from core.hardware.constants import get_hardware_history_metric_columns
from core.hardware.history_selection import HARDWARE_HISTORY_COMPONENTS
from core.history.request.availability import HistoryAvailabilityQuery
from core.history.request.metadata import build_history_metadata
from database.core.history_availability import read_history_with_availability
from database.core.history_queries import (
    build_history_resolution,
    normalize_historical_query,
)
from database.core.query_execution import query_to_dicts
from database.core.row_materialization import sqlite_row_dict_to_json_dict
from database.core.sql_builders import validate_sql_identifier
from database.core.sqlite_row_scalars import require_sqlite_row_int
from database.repositories.hardware.history_row_processing import (
    process_ohlc_rows,
    process_standard_rows,
)
from database.repositories.hardware.history_tables import hardware_history_table_for_component

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from database.core.sqlite_values import SQLiteValue

__all__ = ("get_historical_hardware_data_aggregated",)

_IDENTIFIER_REQUIRED_COMPONENTS = frozenset({"gpu"})


async def get_historical_hardware_data_aggregated(
    database: aiosqlite.Connection,
    component: str,
    start_ts_ms: int,
    end_ts_ms: int,
    interval_ms: int,
    aggregation: str,
    max_points: int,
    identifier: str | None = None,
    availability: HistoryAvailabilityQuery | None = None,
) -> JSONDict:
    table_name = hardware_history_table_for_component(component)
    if table_name is None:
        components = ", ".join(HARDWARE_HISTORY_COMPONENTS)
        raise ValidationError(f"Invalid component '{component}'. Must be one of: {components}")
    normalized_identifier = str(identifier).strip() if identifier is not None else None
    if component in _IDENTIFIER_REQUIRED_COMPONENTS and not normalized_identifier:
        raise ValidationError(f"device_id is required for component '{component}'")
    if availability is not None and availability.metric not in get_hardware_history_metric_columns(
        component
    ):
        raise ValidationError(f"Invalid availability metric for component '{component}'")

    async def _query(connection: aiosqlite.Connection) -> JSONDict:
        return await _query_aggregated_history(
            connection,
            component,
            validate_sql_identifier(table_name, label="table"),
            start_ts_ms,
            end_ts_ms,
            interval_ms,
            aggregation,
            max_points,
            normalized_identifier,
        )

    if availability is None:
        return await _query(database)
    return await read_history_with_availability(
        database,
        _query,
        availability,
        table=table_name,
        value_column=availability.metric,
        filters=(("device_id", normalized_identifier),) if normalized_identifier else (),
    )


async def _query_aggregated_history(
    database: aiosqlite.Connection,
    component: str,
    table_name: str,
    start_ts_ms: int,
    end_ts_ms: int,
    interval_ms: int,
    aggregation: str,
    max_points: int,
    normalized_identifier: str | None,
) -> JSONDict:
    valid_aggregations = {"avg", "min", "max", "ohlc"}
    sanitized_interval, sanitized_max_points, agg_lower, anchor_ts = normalize_historical_query(
        start_ts_ms,
        end_ts_ms,
        interval_ms,
        aggregation,
        max_points,
        valid_aggregations,
    )
    params_whr: tuple[SQLiteValue, ...] = (normalized_identifier,) if normalized_identifier else ()
    where_clause = " AND device_id = ?" if normalized_identifier else ""
    bin_start_sql = (
        f"({anchor_ts} + (CAST(((observed_at_ms - {anchor_ts}) / {sanitized_interval}) AS INTEGER) "
        f"* {sanitized_interval}))"
    )
    metric_cols = [
        validate_sql_identifier(col, label="metric column")
        for col in get_hardware_history_metric_columns(component)
    ]
    if not metric_cols:
        raise ValidationError(f"No metrics configured for component '{component}'")
    metric_columns_sql = ", ".join(metric_cols)
    if agg_lower == "ohlc":
        aggregation_parts = [
            item
            for col in metric_cols
            for item in (
                f"MAX(CASE WHEN {col}_rn_open = 1 THEN {col} END) AS {col}_open",
                f"MAX({col}) AS {col}_high",
                f"MIN({col}) AS {col}_low",
                f"MAX(CASE WHEN {col}_rn_close = 1 THEN {col} END) AS {col}_close",
                f"AVG({col}) AS {col}_avg",
                f"COUNT({col}) AS {col}_count",
            )
        ]
        metric_rankings_sql = ", ".join(
            item
            for col in metric_cols
            for item in (
                f"ROW_NUMBER() OVER (PARTITION BY bin_start_ts ORDER BY ({col} IS NULL), observed_at_ms ASC) AS {col}_rn_open",
                f"ROW_NUMBER() OVER (PARTITION BY bin_start_ts ORDER BY ({col} IS NULL), observed_at_ms DESC) AS {col}_rn_close",
            )
        )
        sql = (
            "WITH base AS ("
            f"SELECT {bin_start_sql} AS bin_start_ts, observed_at_ms, {metric_columns_sql} "
            f"FROM {table_name} "
            f"WHERE observed_at_ms >= ? AND observed_at_ms < ?{where_clause}"
            "), ranked AS ("
            "SELECT bin_start_ts, observed_at_ms, "
            f"{metric_columns_sql}, "
            f"{metric_rankings_sql} "
            "FROM base"
            ") "
            "SELECT bin_start_ts, COUNT(*) AS sample_count, "
            f"{', '.join(aggregation_parts)} "
            "FROM ranked "
            "GROUP BY bin_start_ts "
            "ORDER BY bin_start_ts DESC "
            "LIMIT ?"
        )
    else:
        agg_func = {"avg": "AVG", "min": "MIN", "max": "MAX"}.get(agg_lower, "AVG")
        value_selects = ", ".join(
            [
                f"CAST({agg_func}({col}) AS REAL) AS {col}_value, COUNT({col}) AS {col}_count"
                for col in metric_cols
            ],
        )
        sql = (
            "WITH base AS ("
            f"SELECT {bin_start_sql} AS bin_start_ts, {metric_columns_sql} "
            f"FROM {table_name} "
            f"WHERE observed_at_ms >= ? AND observed_at_ms < ?{where_clause}"
            ") "
            f"SELECT bin_start_ts, {value_selects} "
            "FROM base "
            "GROUP BY bin_start_ts "
            "ORDER BY bin_start_ts DESC "
            "LIMIT ?"
        )
    rows = await query_to_dicts(
        database,
        sql,
        (start_ts_ms, end_ts_ms, *params_whr, sanitized_max_points),
    )
    if not rows:
        return _build_empty_history_response(
            component,
            normalized_identifier,
            start_ts_ms,
            end_ts_ms,
            sanitized_interval,
            sanitized_max_points,
            agg_lower,
            valid_aggregations,
            metric_cols,
        )
    span = max(0, end_ts_ms - anchor_ts)
    possible_buckets = (span + sanitized_interval - 1) // sanitized_interval
    bucket_count = (
        min(sanitized_max_points, possible_buckets)
        if sanitized_max_points > 0
        else possible_buckets
    )
    first_bucket_ts = anchor_ts + (possible_buckets - bucket_count) * sanitized_interval
    expected_timestamps = [
        first_bucket_ts + bucket_index * sanitized_interval for bucket_index in range(bucket_count)
    ]
    row_map: dict[int, JSONDict] = {}
    for row in rows:
        timestamp_value = row.get("bin_start_ts")
        if isinstance(timestamp_value, bool):
            timestamp = int(timestamp_value)
        elif isinstance(timestamp_value, int):
            timestamp = timestamp_value
        elif isinstance(timestamp_value, float):
            timestamp = int(timestamp_value)
        elif isinstance(timestamp_value, str):
            try:
                timestamp = int(timestamp_value)
            except ValueError:
                continue
        else:
            continue
        row_map[timestamp] = sqlite_row_dict_to_json_dict(row)
    data_rows: list[JSONDict] = []
    sample_counts: list[JSONDict] = []
    gap_count = 0
    if agg_lower == "ohlc":
        data_rows, gap_count = process_ohlc_rows(expected_timestamps, row_map, metric_cols)
    else:
        data_rows, gap_count = process_standard_rows(expected_timestamps, row_map, metric_cols)
        sample_counts = [
            {
                col: (
                    require_sqlite_row_int(
                        row_map[timestamp], f"{col}_count", label="hardware history bucket"
                    )
                    if timestamp in row_map
                    else 0
                )
                for col in metric_cols
            }
            for timestamp in expected_timestamps
        ]
    metadata: JSONDict = {
        "bucket_gap_count": gap_count,
        "bucket_count": len(expected_timestamps),
        "aligned_start_ts_ms": (expected_timestamps[0] if expected_timestamps else anchor_ts),
        "aligned_end_ts_ms": expected_timestamps[-1] if expected_timestamps else None,
        "component": component,
        "device_id": normalized_identifier,
    }
    result: JSONDict = {
        "timestamps_ms": expected_timestamps,
        "data": data_rows,
        "interval_ms": sanitized_interval,
        "metrics": metric_cols,
        "aggregation": agg_lower,
        "metadata": metadata,
    }
    if agg_lower != "ohlc":
        result["sample_counts"] = sample_counts
    return result


def _build_empty_history_response(
    component: str,
    normalized_identifier: str | None,
    start_ts_ms: int,
    end_ts_ms: int,
    sanitized_interval: int,
    sanitized_max_points: int,
    agg_lower: str,
    valid_aggregations: set[str],
    metric_cols: list[str],
) -> JSONDict:
    resolution = build_history_resolution(
        start_ts_ms=start_ts_ms,
        end_ts_ms=end_ts_ms,
        interval_ms=sanitized_interval,
        requested_points=sanitized_max_points,
        metrics_history_config=None,
    )
    empty_metadata = build_history_metadata(
        base_metadata={},
        extra_fields={
            "component": component,
            "device_id": normalized_identifier,
            "monitoring_interval_ms": None,
        },
        resolution=resolution,
        aggregation=agg_lower,
        requested_points=sanitized_max_points,
        start_ts_ms=start_ts_ms,
        end_ts_ms=end_ts_ms,
        logging_interval_ms=sanitized_interval,
        supported_aggregations=list(valid_aggregations),
        gap_count=0,
        resolved_points=0,
    )
    result: JSONDict = {
        "timestamps_ms": [],
        "data": [],
        "interval_ms": sanitized_interval,
        "metrics": metric_cols,
        "aggregation": agg_lower,
        "metadata": empty_metadata,
    }
    if agg_lower != "ohlc":
        result["sample_counts"] = []
    return result
