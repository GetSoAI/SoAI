"""SoAI - Metrics history synchronous logging [backend/database/repositories/metrics/history/sync_logging.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3

from core.timing.epoch import epoch_ms

__all__ = ("sync_log_historical_metric", "sync_log_historical_metrics")


def sync_log_historical_metric(
    conn: sqlite3.Connection,
    metric_key: str,
    metric_value: float,
    observed_at_ms: int,
) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO metrics_history (observed_at_ms, metric_key, value) VALUES (?, ?, ?)",
        (observed_at_ms, metric_key, metric_value),
    )


def sync_log_historical_metrics(
    conn: sqlite3.Connection,
    metrics_snapshot: dict[str, int | float],
) -> None:
    if not metrics_snapshot:
        return
    now = epoch_ms()
    conn.executemany(
        "INSERT OR IGNORE INTO metrics_history (observed_at_ms, metric_key, value) VALUES (?, ?, ?)",
        [(now, metric_key, metric_value) for metric_key, metric_value in metrics_snapshot.items()],
    )
