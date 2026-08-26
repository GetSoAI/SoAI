"""SoAI - Metrics history repository API [backend/database/repositories/metrics/history/repository.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

import aiosqlite

from core.errors.exceptions import ValidationError
from database.core.history_queries import normalize_historical_query
from database.repositories.metrics.history.aggregated_query import (
    get_aggregated_historical_data,
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
    if agg_lower in ("ohlc", "delta_ohlc"):
        return await get_ohlc_historical_data(
            database,
            metric_key,
            start_ts_ms,
            end_ts_ms,
            sanitized_interval,
            limit,
            anchor_ts,
            agg_lower,
        )
    return await get_aggregated_historical_data(
        database,
        metric_key,
        start_ts_ms,
        end_ts_ms,
        sanitized_interval,
        limit,
        anchor_ts,
        agg_lower,
    )
