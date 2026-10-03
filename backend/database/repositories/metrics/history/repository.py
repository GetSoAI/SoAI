"""SoAI - Metrics history repository API [backend/database/repositories/metrics/history/repository.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

import aiosqlite

from core.errors.exceptions import ValidationError
from core.history.request.availability import HistoryAvailabilityQuery
from database.core.history_availability import read_history_with_availability
from database.core.history_queries import normalize_historical_query
from database.repositories.metrics.history.aggregated_query import (
    get_aggregated_historical_data,
)
from database.repositories.metrics.history.metric_key_validation import (
    require_metric_key_exists,
)
from database.repositories.metrics.history.ohlc_query import get_ohlc_historical_data

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("get_historical_metrics_data_aggregated",)


async def get_historical_metrics_data_aggregated(
    database: aiosqlite.Connection,
    metric_key: str,
    start_ts_ms: int,
    end_ts_ms: int,
    interval_ms: int,
    aggregation: str,
    max_points: int,
    metric_key_known: bool = False,
    availability: HistoryAvailabilityQuery | None = None,
) -> JSONDict:
    if not metric_key:
        raise ValidationError("metric_key must be a non-empty string")

    valid_aggregations = {"avg", "min", "max", "count", "delta", "ohlc", "delta_ohlc"}
    sanitized_interval, limit, agg_lower, anchor_ts = normalize_historical_query(
        start_ts_ms,
        end_ts_ms,
        interval_ms,
        aggregation,
        max_points,
        valid_aggregations,
    )
    query_payload = (
        get_ohlc_historical_data
        if agg_lower in ("ohlc", "delta_ohlc")
        else get_aggregated_historical_data
    )

    async def _query(connection: aiosqlite.Connection) -> JSONDict:
        history = await query_payload(
            connection,
            metric_key,
            start_ts_ms,
            end_ts_ms,
            sanitized_interval,
            limit,
            anchor_ts,
            agg_lower,
        )
        if not metric_key_known and not history.get("timestamps_ms"):
            await require_metric_key_exists(connection, metric_key)
        return history

    if availability is None:
        return await _query(database)
    return await read_history_with_availability(
        database,
        _query,
        availability,
        table="metrics_history",
        value_column="value",
        filters=(("metric_key", metric_key),),
    )
