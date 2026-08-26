"""SoAI - History request data models [backend/core/history/request/models.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    type NumericInput = int | float | str

__all__ = (
    "HistoryRequestResolution",
    "PreparedHistoryRequest",
)


@dataclass(frozen=True, slots=True)
class HistoryRequestResolution:
    original_start_ts_ms: int
    start_ts_ms: int
    end_ts_ms: int
    interval_ms: int
    requested_points: int
    effective_points: int
    max_points: int
    bucket_count: int
    aligned_start_ts_ms: int
    aligned_end_ts_ms: int
    retention_applied: bool
    retention_start_ts_ms: int | None
    requested_interval_ms: int | None
    supported_intervals_ms: tuple[int, ...]
    duration_ms: int
    interval_source: Literal["auto", "explicit"]

    def generate_timestamps_ms(self) -> list[int]:
        return [
            self.aligned_start_ts_ms + index * self.interval_ms
            for index in range(self.bucket_count)
        ]


@dataclass(frozen=True, slots=True)
class PreparedHistoryRequest:
    start_ts_ms: int
    end_ts_ms: int
    requested_points: int
    aggregation: str
    logging_interval_ms: int
    resolution: HistoryRequestResolution
