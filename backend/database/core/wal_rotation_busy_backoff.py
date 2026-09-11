"""SoAI - WAL rotation busy retry backoff state [backend/database/core/wal_rotation_busy_backoff.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.logging.rate_limited_logger import RateLimitedLogger
from core.timing.retry_backoff import compute_exponential_backoff_seconds

__all__ = (
    "WalRotationBusyBackoff",
    "WalRotationBusyRecovery",
    "WalRotationBusyRetry",
)

_ROTATION_BUSY_RETRY_JITTER_RATIO = 0.2


@dataclass(frozen=True, slots=True)
class WalRotationBusyRetry:
    delay_seconds: float
    busy_rotations: int
    elapsed_seconds: float
    should_report: bool
    suppressed_reports: int


@dataclass(frozen=True, slots=True)
class WalRotationBusyRecovery:
    busy_rotations: int
    elapsed_seconds: float


class WalRotationBusyBackoff:
    def __init__(self, *, base_interval_sec: float, maximum_interval_sec: float) -> None:
        self._base_interval_sec = base_interval_sec
        self._maximum_interval_sec = max(base_interval_sec, maximum_interval_sec)
        self._reporter = self._build_reporter(last_report_monotonic=0.0)
        self._busy_rotations = 0
        self._first_busy_monotonic = 0.0

    def _build_reporter(self, *, last_report_monotonic: float) -> RateLimitedLogger:
        return RateLimitedLogger(
            interval_seconds=self._maximum_interval_sec,
            _last_warning_monotonic=last_report_monotonic,
        )

    def record_busy(self, *, now: float) -> WalRotationBusyRetry:
        previous_rotations = self._busy_rotations
        self._busy_rotations = previous_rotations + 1
        delay_seconds = compute_exponential_backoff_seconds(
            previous_rotations,
            base_seconds=self._base_interval_sec,
            maximum_seconds=self._maximum_interval_sec,
            jitter_ratio=_ROTATION_BUSY_RETRY_JITTER_RATIO,
        )
        if previous_rotations == 0:
            self._first_busy_monotonic = now
            self._reporter = self._build_reporter(last_report_monotonic=now)
            should_report = True
            suppressed_reports = 0
        else:
            should_report, suppressed_reports = self._reporter.should_emit(now=now)
        return WalRotationBusyRetry(
            delay_seconds=delay_seconds,
            busy_rotations=self._busy_rotations,
            elapsed_seconds=max(0.0, now - self._first_busy_monotonic),
            should_report=should_report,
            suppressed_reports=suppressed_reports,
        )

    def record_healthy(self, *, now: float) -> WalRotationBusyRecovery | None:
        busy_rotations = self._busy_rotations
        if busy_rotations == 0:
            return None
        elapsed_seconds = max(0.0, now - self._first_busy_monotonic)
        self._busy_rotations = 0
        self._first_busy_monotonic = 0.0
        self._reporter = self._build_reporter(last_report_monotonic=0.0)
        return WalRotationBusyRecovery(
            busy_rotations=busy_rotations,
            elapsed_seconds=elapsed_seconds,
        )
