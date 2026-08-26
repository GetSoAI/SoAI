"""SoAI - Metrics history SQL templates [backend/database/repositories/metrics/history/sql_templates.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

__all__ = ("aggregation_sql", "ohlc_sql")

OHLC_SQL = """
        WITH base AS (
            SELECT
                (? + (CAST(((observed_at_ms - ?) / ?) AS INTEGER) * ?)) AS bin_start_ts,
                observed_at_ms,
                value
            FROM metrics_history
            WHERE metric_key = ? AND observed_at_ms >= ? AND observed_at_ms < ?
        ),
        bucketed AS (
            SELECT
                bin_start_ts,
                value,
                ROW_NUMBER() OVER (PARTITION BY bin_start_ts ORDER BY observed_at_ms ASC) AS rn_open,
                ROW_NUMBER() OVER (PARTITION BY bin_start_ts ORDER BY observed_at_ms DESC) AS rn_close
            FROM base
        )
        SELECT
            bin_start_ts,
            CAST(MAX(CASE WHEN rn_open = 1 THEN value END) AS REAL) AS open_value,
            CAST(MAX(value) AS REAL) AS high_value,
            CAST(MIN(value) AS REAL) AS low_value,
            CAST(MAX(CASE WHEN rn_close = 1 THEN value END) AS REAL) AS close_value,
            CAST(AVG(value) AS REAL) AS avg_value,
            COUNT(*) AS sample_count
        FROM bucketed
        GROUP BY bin_start_ts
        ORDER BY bin_start_ts ASC
        LIMIT ?
    """


AVG_SQL = """
        WITH base AS (
            SELECT
                (? + (CAST(((observed_at_ms - ?) / ?) AS INTEGER) * ?)) AS bin_start_ts,
                value
            FROM metrics_history
            WHERE metric_key = ? AND observed_at_ms >= ? AND observed_at_ms < ?
        )
        SELECT
            bin_start_ts,
            AVG(CAST(value AS REAL)) AS agg_value,
            COUNT(*) AS sample_count
        FROM base
        GROUP BY bin_start_ts
        ORDER BY bin_start_ts ASC
        LIMIT ?
    """

MIN_SQL = """
        WITH base AS (
            SELECT
                (? + (CAST(((observed_at_ms - ?) / ?) AS INTEGER) * ?)) AS bin_start_ts,
                value
            FROM metrics_history
            WHERE metric_key = ? AND observed_at_ms >= ? AND observed_at_ms < ?
        )
        SELECT
            bin_start_ts,
            MIN(CAST(value AS REAL)) AS agg_value,
            COUNT(*) AS sample_count
        FROM base
        GROUP BY bin_start_ts
        ORDER BY bin_start_ts ASC
        LIMIT ?
    """

MAX_SQL = """
        WITH base AS (
            SELECT
                (? + (CAST(((observed_at_ms - ?) / ?) AS INTEGER) * ?)) AS bin_start_ts,
                value
            FROM metrics_history
            WHERE metric_key = ? AND observed_at_ms >= ? AND observed_at_ms < ?
        )
        SELECT
            bin_start_ts,
            MAX(CAST(value AS REAL)) AS agg_value,
            COUNT(*) AS sample_count
        FROM base
        GROUP BY bin_start_ts
        ORDER BY bin_start_ts ASC
        LIMIT ?
    """

COUNT_SQL = """
        WITH base AS (
            SELECT
                (? + (CAST(((observed_at_ms - ?) / ?) AS INTEGER) * ?)) AS bin_start_ts,
                value
            FROM metrics_history
            WHERE metric_key = ? AND observed_at_ms >= ? AND observed_at_ms < ?
        )
        SELECT
            bin_start_ts,
            CAST(COUNT(*) AS REAL) AS agg_value,
            COUNT(*) AS sample_count
        FROM base
        GROUP BY bin_start_ts
        ORDER BY bin_start_ts ASC
        LIMIT ?
    """

DELTA_SQL = """
        WITH baseline AS (
            SELECT
                observed_at_ms,
                CAST(value AS REAL) AS value
            FROM metrics_history
            WHERE metric_key = ?5 AND observed_at_ms < ?6
            ORDER BY observed_at_ms DESC
            LIMIT 1
        ),
        raw AS (
            SELECT observed_at_ms, value FROM baseline
            UNION ALL
            SELECT
                observed_at_ms,
                CAST(value AS REAL) AS value
            FROM metrics_history
            WHERE metric_key = ?5 AND observed_at_ms >= ?6 AND observed_at_ms < ?7
        ),
        base AS (
            SELECT
                (?1 + (CAST(((observed_at_ms - ?2) / ?3) AS INTEGER) * ?4)) AS bin_start_ts,
                observed_at_ms,
                value
            FROM raw
        ),
        sequenced AS (
            SELECT
                bin_start_ts,
                observed_at_ms,
                value,
                LAG(value) OVER (ORDER BY observed_at_ms ASC) AS previous_value
            FROM base
        ),
        deltas AS (
            SELECT
                bin_start_ts,
                CASE
                    WHEN previous_value IS NULL THEN NULL
                    WHEN value >= previous_value THEN value - previous_value
                    ELSE value
                END AS delta_value
            FROM sequenced
            WHERE observed_at_ms >= ?6
        )
        SELECT
            bin_start_ts,
            SUM(delta_value) AS agg_value,
            COUNT(delta_value) AS sample_count
        FROM deltas
        GROUP BY bin_start_ts
        ORDER BY bin_start_ts ASC
        LIMIT ?8
    """

DELTA_OHLC_SQL = """
        WITH baseline AS (
            SELECT
                observed_at_ms,
                CAST(value AS REAL) AS value
            FROM metrics_history
            WHERE metric_key = ?5 AND observed_at_ms < ?6
            ORDER BY observed_at_ms DESC
            LIMIT 1
        ),
        raw AS (
            SELECT observed_at_ms, value FROM baseline
            UNION ALL
            SELECT
                observed_at_ms,
                CAST(value AS REAL) AS value
            FROM metrics_history
            WHERE metric_key = ?5 AND observed_at_ms >= ?6 AND observed_at_ms < ?7
        ),
        base AS (
            SELECT
                (?1 + (CAST(((observed_at_ms - ?2) / ?3) AS INTEGER) * ?4)) AS bin_start_ts,
                observed_at_ms,
                value
            FROM raw
        ),
        sequenced AS (
            SELECT
                bin_start_ts,
                observed_at_ms,
                value,
                LAG(value) OVER (ORDER BY observed_at_ms ASC) AS previous_value
            FROM base
        ),
        deltas AS (
            SELECT
                bin_start_ts,
                observed_at_ms,
                CASE
                    WHEN previous_value IS NULL THEN NULL
                    WHEN value >= previous_value THEN value - previous_value
                    ELSE value
                END AS delta_value
            FROM sequenced
            WHERE observed_at_ms >= ?6
        ),
        bucketed AS (
            SELECT
                bin_start_ts,
                delta_value AS value,
                ROW_NUMBER() OVER (PARTITION BY bin_start_ts ORDER BY observed_at_ms ASC) AS rn_open,
                ROW_NUMBER() OVER (PARTITION BY bin_start_ts ORDER BY observed_at_ms DESC) AS rn_close
            FROM deltas
            WHERE delta_value IS NOT NULL
        )
        SELECT
            bin_start_ts,
            CAST(MAX(CASE WHEN rn_open = 1 THEN value END) AS REAL) AS open_value,
            CAST(MAX(value) AS REAL) AS high_value,
            CAST(MIN(value) AS REAL) AS low_value,
            CAST(MAX(CASE WHEN rn_close = 1 THEN value END) AS REAL) AS close_value,
            CAST(AVG(value) AS REAL) AS avg_value,
            COUNT(*) AS sample_count
        FROM bucketed
        GROUP BY bin_start_ts
        ORDER BY bin_start_ts ASC
        LIMIT ?8
    """


def aggregation_sql(aggregation: str) -> str:
    if aggregation == "delta":
        return DELTA_SQL
    if aggregation == "min":
        return MIN_SQL
    if aggregation == "max":
        return MAX_SQL
    if aggregation == "count":
        return COUNT_SQL
    return AVG_SQL


def ohlc_sql(aggregation: str) -> str:
    if aggregation == "delta_ohlc":
        return DELTA_OHLC_SQL
    return OHLC_SQL
