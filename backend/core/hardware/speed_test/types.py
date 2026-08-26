"""SoAI - Disk and network speed test shared types [backend/core/hardware/speed_test/types.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

__all__ = ("NetworkSpeedTestSnapshot",)


@dataclass(frozen=True, slots=True)
class NetworkSpeedTestSnapshot:
    observed_monotonic: float
    observed_unix: float
    duration_ms: int
    bytes_downloaded: int
    bytes_per_second: float
    sample_bytes: int
    url: str
