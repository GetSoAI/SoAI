"""SoAI - Metrics history aggregated query [backend/database/repositories/metrics/history/aggregated_query.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

import aiosqlite

from core.config.numeric import coerce_float_or_none
from database.repositories.metrics.history.history_query_scaffold import (
    fetch_metric_history_index_or_empty_payload,
)
from database.repositories.metrics.history.sql_templates import aggregation_sql

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("get_aggregated_historical_data",)


async def get_aggregated_historical_data(
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
        aggregation_sql(aggregation),
        metric_key=metric_key,
        start_ts_ms=start_ts_ms,
        end_ts_ms=end_ts_ms,
        anchor_ts_ms=anchor_ts_ms,
        sanitized_interval_ms=sanitized_interval_ms,
        limit=limit,
        empty_extra={"aggregation": aggregation},
    )
    if isinstance(index_or_payload, dict):
        return index_or_payload

    expected_timestamps, row_map, bucket_count = index_or_payload

    values: list[float | None] = []
    gap_count = 0
    for timestamp in expected_timestamps:
        row = row_map.get(timestamp)
        if row:
            agg_value = coerce_float_or_none(row.get("agg_value"))
            values.append(agg_value)
        else:
            values.append(None)
            gap_count += 1

    metadata: JSONDict = {
        "bucket_gap_count": gap_count,
        "bucket_count": bucket_count,
        "aligned_start_ts_ms": (expected_timestamps[0] if expected_timestamps else anchor_ts_ms),
        "aligned_end_ts_ms": expected_timestamps[-1] if expected_timestamps else None,
    }
    return {
        "timestamps_ms": expected_timestamps,
        "values": values,
        "interval_ms": sanitized_interval_ms,
        "aggregation": aggregation,
        "metadata": metadata,
    }
