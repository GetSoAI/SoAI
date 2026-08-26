"""SoAI - Metrics history query indexing and empty-result construction [backend/database/repositories/metrics/history/history_query_scaffold.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

import aiosqlite

from database.repositories.metrics.history.bucket_builder import metrics_bucket_builder
from database.repositories.metrics.history.row_mapping import build_row_map_by_timestamp
from database.repositories.metrics.history.rows_fetch import fetch_metric_history_rows

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from database.core.sqlite_values import SQLiteRowDict

__all__ = (
    "build_empty_metric_history_payload",
    "build_metric_history_index",
    "fetch_metric_history_index",
    "fetch_metric_history_index_or_empty_payload",
)


def build_empty_metric_history_payload(
    *,
    anchor_ts_ms: int,
    interval_ms: int,
    extra: JSONDict,
) -> JSONDict:
    return {
        "timestamps_ms": [],
        "values": [],
        **dict(extra),
        "interval_ms": interval_ms,
        "metadata": {
            "bucket_gap_count": 0,
            "bucket_count": 0,
            "aligned_start_ts_ms": anchor_ts_ms,
            "aligned_end_ts_ms": None,
        },
    }


def build_metric_history_index(
    rows: list[SQLiteRowDict],
    *,
    anchor_ts_ms: int,
    end_ts_ms: int,
    interval_ms: int,
    limit: int,
) -> tuple[list[int], dict[int, SQLiteRowDict], int]:
    expected_timestamps, bucket_count = metrics_bucket_builder(
        anchor_ts_ms,
        end_ts_ms,
        interval_ms,
        limit,
    )
    row_map = build_row_map_by_timestamp(rows)
    return expected_timestamps, row_map, bucket_count


async def fetch_metric_history_index(
    database: aiosqlite.Connection,
    sql: str,
    *,
    metric_key: str,
    anchor_ts_ms: int,
    start_ts_ms: int,
    end_ts_ms: int,
    sanitized_interval_ms: int,
    limit: int,
) -> tuple[list[int], dict[int, SQLiteRowDict], int] | None:
    rows = await fetch_metric_history_rows(
        database,
        sql,
        anchor_ts_ms=anchor_ts_ms,
        sanitized_interval_ms=sanitized_interval_ms,
        metric_key=metric_key,
        start_ts_ms=start_ts_ms,
        end_ts_ms=end_ts_ms,
        limit=limit,
    )
    if rows is None:
        return None
    return build_metric_history_index(
        rows,
        anchor_ts_ms=anchor_ts_ms,
        end_ts_ms=end_ts_ms,
        interval_ms=sanitized_interval_ms,
        limit=limit,
    )


async def fetch_metric_history_index_or_empty_payload(
    database: aiosqlite.Connection,
    sql: str,
    *,
    metric_key: str,
    anchor_ts_ms: int,
    start_ts_ms: int,
    end_ts_ms: int,
    sanitized_interval_ms: int,
    limit: int,
    empty_extra: JSONDict,
) -> tuple[list[int], dict[int, SQLiteRowDict], int] | JSONDict:
    index = await fetch_metric_history_index(
        database,
        sql,
        metric_key=metric_key,
        start_ts_ms=start_ts_ms,
        end_ts_ms=end_ts_ms,
        anchor_ts_ms=anchor_ts_ms,
        sanitized_interval_ms=sanitized_interval_ms,
        limit=limit,
    )
    if index is None:
        return build_empty_metric_history_payload(
            anchor_ts_ms=anchor_ts_ms,
            interval_ms=sanitized_interval_ms,
            extra=empty_extra,
        )
    return index
