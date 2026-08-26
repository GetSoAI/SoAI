"""SoAI - Metrics history bucket generation [backend/database/repositories/metrics/history/bucket_builder.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

__all__ = ("metrics_bucket_builder",)


def metrics_bucket_builder(
    anchor_ts_ms: int,
    end_ts_ms: int,
    interval_ms: int,
    limit: int,
) -> tuple[list[int], int]:
    span = max(0, end_ts_ms - anchor_ts_ms)
    possible_buckets = (span + interval_ms - 1) // interval_ms if interval_ms > 0 else 0
    if possible_buckets <= 0:
        possible_buckets = 1
    bucket_count = min(limit, possible_buckets) if limit > 0 else possible_buckets
    expected_timestamps = [anchor_ts_ms + (index * interval_ms) for index in range(bucket_count)]
    return expected_timestamps, bucket_count
