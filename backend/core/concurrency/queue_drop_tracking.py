"""SoAI - Queue drop tracking and warning helpers [backend/core/concurrency/queue_drop_tracking.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.logging.protocols import LoggerProtocol
from core.logging.rate_limited_logger import RateLimitedLogger

__all__ = (
    "QueueDropReport",
    "QueueDropTracker",
    "log_queue_drop_with_tracker",
)


@dataclass(frozen=True, slots=True)
class QueueDropReport:
    should_log: bool
    suppressed_count: int
    dropped_count: int
    total_dropped: int


class QueueDropTracker:
    __slots__ = ("_total_dropped", "_warning_limiter")

    def __init__(self, warning_interval_seconds: float = 30.0) -> None:
        self._total_dropped = 0
        self._warning_limiter = RateLimitedLogger(warning_interval_seconds)

    @property
    def total_dropped(self) -> int:
        return self._total_dropped

    def record_drop(self, dropped_count: int = 1) -> QueueDropReport:
        normalized_drop_count = max(1, int(dropped_count))
        self._total_dropped += normalized_drop_count
        should_log, suppressed_count = self._warning_limiter.should_emit()
        return QueueDropReport(
            should_log=should_log,
            suppressed_count=suppressed_count,
            dropped_count=normalized_drop_count,
            total_dropped=self._total_dropped,
        )


def log_queue_drop_with_tracker(
    logger: LoggerProtocol,
    drop_tracker: QueueDropTracker,
    dropped_count: int,
    context: str,
    *,
    drop_report: QueueDropReport | None = None,
) -> QueueDropReport:
    report = drop_report or drop_tracker.record_drop(dropped_count)
    if not report.should_log:
        return report
    if report.suppressed_count > 0:
        logger.warning(
            "%s (%d dropped updates). (%d warning(s) suppressed since last report, %d total dropped).",
            context,
            report.dropped_count,
            report.suppressed_count,
            report.total_dropped,
        )
    else:
        logger.warning(
            "%s (%d dropped updates). (%d total dropped).",
            context,
            report.dropped_count,
            report.total_dropped,
        )
    return report
