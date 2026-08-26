"""SoAI - Disk speed test data types [backend/core/hardware/speed_test/disk_speed_test_types.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

__all__ = ("SpeedTestSnapshot",)


@dataclass(slots=True)
class SpeedTestSnapshot:
    cache_key: str
    storage_path: str
    observed_monotonic: float
    observed_unix: float
    duration_ms: int
    bytes_downloaded: int
    bytes_per_second: float
    sample_bytes: int | None = None
