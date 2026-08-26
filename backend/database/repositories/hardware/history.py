"""SoAI - Hardware history queries with time aggregation [backend/database/repositories/hardware/history.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

import aiosqlite

from core.errors.exceptions import ValidationError
from core.hardware.constants import (
    CPU_METRIC_COLUMNS,
    GPU_METRIC_COLUMNS,
    NETWORK_INTERFACE_STAT_KEYS_WITH_SPEED,
)
from core.history.request.metadata import build_history_metadata
from database.core.history_queries import (
    build_history_resolution,
    normalize_historical_query,
)
from database.core.query_execution import query_to_dicts
from database.core.row_materialization import sqlite_row_dict_to_json_dict
from database.core.sql_builders import validate_sql_identifier
from database.repositories.hardware.history_row_processing import (
    process_ohlc_rows,
    process_standard_rows,
)

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from database.core.sqlite_values import SQLiteValue

__all__ = ("get_historical_hardware_data_aggregated",)


async def get_historical_hardware_data_aggregated(
    database: aiosqlite.Connection,
    component: str,
    start_ts_ms: int,
    end_ts_ms: int,
    interval_ms: int,
    aggregation: str,
    max_points: int,
    identifier: str | None = None,
) -> JSONDict:
    query_map: dict[str, dict[str, str | bool | list[str] | tuple[str, ...]]] = {
        "cpu": {
            "tbl": "hardware_cpu_history",
            "metric_cols": list(CPU_METRIC_COLUMNS),
            "identifier_column": "device_id",
            "identifier_required": False,
            "base_conditions": (),
        },
        "gpu": {
            "tbl": "hardware_gpu_history",
            "metric_cols": list(GPU_METRIC_COLUMNS),
            "identifier_column": "device_id",
            "identifier_required": True,
            "base_conditions": (),
        },
        "disk": {
            "tbl": "hardware_disk_history",
            "metric_cols": [
                "total_bytes",
                "used_bytes",
                "free_bytes",
                "percent_used",
            ],
            "identifier_column": "device_id",
            "identifier_required": False,
            "base_conditions": (),
        },
        "network": {
            "tbl": "hardware_network_history",
            "metric_cols": list(NETWORK_INTERFACE_STAT_KEYS_WITH_SPEED),
            "identifier_column": "device_id",
            "identifier_required": False,
            "base_conditions": (),
        },
    }
    if component not in query_map:
        raise ValidationError(
            f"Invalid component '{component}'. Must be one of: {', '.join(query_map.keys())}",
        )
    valid_aggregations = {"avg", "min", "max", "ohlc"}
    sanitized_interval, sanitized_max_points, agg_lower, anchor_ts = normalize_historical_query(
        start_ts_ms,
        end_ts_ms,
        interval_ms,
        aggregation,
        max_points,
        valid_aggregations,
    )
    config = query_map[component]
    table_name_value = config["tbl"]
    if not isinstance(table_name_value, str):
        raise ValidationError(f"Invalid table configuration for component '{component}'")
    table_name = validate_sql_identifier(table_name_value, label="table")
    params_whr: list[SQLiteValue] = []
    base_conditions = config.get("base_conditions", ())
    extra_conditions: list[str] = []
    if isinstance(base_conditions, list | tuple):
        extra_conditions.extend(
            str(condition) for condition in base_conditions if isinstance(condition, str)
        )
    identifier_column_raw = config.get("identifier_column")
    identifier_column = (
        validate_sql_identifier(identifier_column_raw, label="identifier column")
        if identifier_column_raw is not None and isinstance(identifier_column_raw, str)
        else None
    )
    normalized_identifier = str(identifier).strip() if identifier is not None else None
    if identifier_column:
        if config.get("identifier_required") and (not normalized_identifier):
            raise ValidationError(f"device_id is required for component '{component}'")
        if normalized_identifier:
            params_whr.append(normalized_identifier)
            extra_conditions.append(f"{identifier_column} = ?")
    where_clause = f" AND {' AND '.join(extra_conditions)}" if extra_conditions else ""
    bin_start_sql = (
        f"({anchor_ts} + (CAST(((observed_at_ms - {anchor_ts}) / {sanitized_interval}) AS INTEGER) "
        f"* {sanitized_interval}))"
    )
    metric_cols_raw = config["metric_cols"]
    if not isinstance(metric_cols_raw, list):
        raise ValidationError(f"Invalid metric_cols configuration for component '{component}'")
    if not all(isinstance(col, str) for col in metric_cols_raw):
        raise ValidationError(f"Invalid metric column configuration for component '{component}'")
    metric_cols = [validate_sql_identifier(col, label="metric column") for col in metric_cols_raw]
    if not metric_cols:
        raise ValidationError(f"No metrics configured for component '{component}'")
    metric_columns_sql = ", ".join(metric_cols)
    if agg_lower == "ohlc":
        aggregation_parts = [
            item
            for col in metric_cols
            for item in (
                f"MAX(CASE WHEN rn_open = 1 THEN {col} END) AS {col}_open",
                f"MAX({col}) AS {col}_high",
                f"MIN({col}) AS {col}_low",
                f"MAX(CASE WHEN rn_close = 1 THEN {col} END) AS {col}_close",
                f"AVG({col}) AS {col}_avg",
            )
        ]
        sql = (
            "WITH base AS ("
            f"SELECT {bin_start_sql} AS bin_start_ts, observed_at_ms, {metric_columns_sql} "
            f"FROM {table_name} "
            f"WHERE observed_at_ms BETWEEN ? AND ?{where_clause}"
            "), ranked AS ("
            "SELECT bin_start_ts, observed_at_ms, "
            f"{metric_columns_sql}, "
            "ROW_NUMBER() OVER (PARTITION BY bin_start_ts ORDER BY observed_at_ms ASC) "
            "AS rn_open, "
            "ROW_NUMBER() OVER (PARTITION BY bin_start_ts ORDER BY observed_at_ms DESC) "
            "AS rn_close "
            "FROM base"
            ") "
            "SELECT bin_start_ts, COUNT(*) AS sample_count, "
            f"{', '.join(aggregation_parts)} "
            "FROM ranked "
            "GROUP BY bin_start_ts "
            "ORDER BY bin_start_ts ASC "
            "LIMIT ?"
        )
    else:
        agg_func = {"avg": "AVG", "min": "MIN", "max": "MAX"}.get(agg_lower, "AVG")
        value_selects = ", ".join(
            [f"CAST({agg_func}({col}) AS REAL) AS {col}_value" for col in metric_cols],
        )
        sql = (
            "WITH base AS ("
            f"SELECT {bin_start_sql} AS bin_start_ts, {metric_columns_sql} "
            f"FROM {table_name} "
            f"WHERE observed_at_ms BETWEEN ? AND ?{where_clause}"
            ") "
            f"SELECT bin_start_ts, {value_selects} "
            "FROM base "
            "GROUP BY bin_start_ts "
            "ORDER BY bin_start_ts ASC "
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
    possible_buckets = span // sanitized_interval if sanitized_interval > 0 else 1
    bucket_count = (
        min(sanitized_max_points, possible_buckets)
        if sanitized_max_points > 0
        else possible_buckets
    )
    expected_timestamps = [
        anchor_ts + bucket_index * sanitized_interval for bucket_index in range(bucket_count)
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
    gap_count = 0
    if agg_lower == "ohlc":
        data_rows, gap_count = process_ohlc_rows(expected_timestamps, row_map, metric_cols)
    else:
        data_rows, gap_count = process_standard_rows(expected_timestamps, row_map, metric_cols)
    metadata: JSONDict = {
        "bucket_gap_count": gap_count,
        "bucket_count": len(expected_timestamps),
        "aligned_start_ts_ms": (expected_timestamps[0] if expected_timestamps else anchor_ts),
        "aligned_end_ts_ms": expected_timestamps[-1] if expected_timestamps else None,
        "component": component,
        "device_id": normalized_identifier,
    }
    return {
        "timestamps_ms": expected_timestamps,
        "data": data_rows,
        "interval_ms": sanitized_interval,
        "metrics": metric_cols,
        "aggregation": agg_lower,
        "metadata": metadata,
    }


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
    return {
        "timestamps_ms": [],
        "data": [],
        "interval_ms": sanitized_interval,
        "metrics": metric_cols,
        "aggregation": agg_lower,
        "metadata": empty_metadata,
    }
