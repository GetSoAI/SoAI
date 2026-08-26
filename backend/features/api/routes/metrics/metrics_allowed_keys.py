"""SoAI - Metrics route allowed key sets [backend/features/api/routes/metrics/metrics_allowed_keys.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

__all__ = ("METRICS_QUERY_ALLOWED_KEYS",)

METRICS_QUERY_ALLOWED_KEYS: frozenset[str] = frozenset(
    {
        "metric_key",
        "start_ts_ms",
        "end_ts_ms",
        "points",
        "interval_ms",
        "aggregation",
    },
)
