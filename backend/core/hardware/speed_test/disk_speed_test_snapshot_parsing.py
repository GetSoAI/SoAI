"""SoAI - Disk speed test snapshot parsing [backend/core/hardware/speed_test/disk_speed_test_snapshot_parsing.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from core.hardware.speed_test.disk_speed_test_types import SpeedTestSnapshot
from core.timing.epoch import epoch_ms
from core.validation.coercion import coerce_float_with_bool, coerce_int_from_scalar

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = (
    "build_snapshot_from_db_record",
    "is_record_fresh",
)


def build_snapshot_from_db_record(
    record: JSONDict,
    *,
    cache_key: str,
    storage_path: str,
    observed_monotonic: float,
) -> SpeedTestSnapshot | None:
    sample_bytes = record.get("sample_bytes") or record.get("bytes_processed")
    duration_ms_value = coerce_int_from_scalar(record.get("duration_ms"))
    if duration_ms_value is None:
        return None
    processed = coerce_int_from_scalar(record.get("bytes_processed"))
    if processed is None:
        return None
    throughput = coerce_float_with_bool(record.get("bytes_per_second"))
    if throughput is None:
        return None
    if (
        duration_ms_value <= 0
        or processed <= 0
        or (not math.isfinite(throughput))
        or throughput <= 0
    ):
        return None
    observed_at_ms_value = coerce_int_from_scalar(record.get("observed_at_ms"))
    observed_at_ms = (
        int(observed_at_ms_value) if observed_at_ms_value is not None else int(epoch_ms())
    )
    observed_unix = float(observed_at_ms) / 1000.0
    sample_bytes_int = coerce_int_from_scalar(sample_bytes)
    bytes_downloaded = int(
        sample_bytes_int if sample_bytes_int and sample_bytes_int > 0 else processed,
    )
    return SpeedTestSnapshot(
        cache_key=cache_key,
        storage_path=storage_path,
        observed_monotonic=observed_monotonic,
        observed_unix=observed_unix,
        duration_ms=int(duration_ms_value),
        bytes_downloaded=bytes_downloaded,
        bytes_per_second=float(throughput),
        sample_bytes=int(sample_bytes_int) if sample_bytes_int and sample_bytes_int > 0 else None,
    )


def is_record_fresh(*, now_ms: int, observed_at_ms: int, cache_seconds: float) -> bool:
    if observed_at_ms <= 0:
        return False
    return (now_ms - observed_at_ms) < int(cache_seconds * 1000)
