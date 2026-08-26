"""SoAI - Event bus backpressure tracking and publish-drop metrics [backend/core/events/bus_backpressure.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.concurrency.queue_ops import QueueDropTracker, log_queue_drop_with_tracker
from core.events.types_base import Event
from core.logging.protocols import LoggerProtocol
from core.metrics.keyspace_base import EVENT_BUS_COUNTER_EVENTS_DROPPED
from core.metrics.keyspace_paths_event_streaming import EVENT_BUS_GAUGE_QUEUE_DEPTH
from core.metrics.protocols import MetricsManagerProtocol

__all__ = ("EventBusBackpressureTracker",)

_PUBLISH_DROP_WARNING_INTERVAL_SECONDS: float = 5.0


class EventBusBackpressureTracker:
    def __init__(
        self,
        *,
        queue_size: int,
        backpressure_warning_depth: int | None,
    ) -> None:
        self._queue_size = queue_size
        self._backpressure_warning_depth = backpressure_warning_depth
        self._backpressure_warning_active = False
        self._publish_drop_tracker: QueueDropTracker = QueueDropTracker(
            _PUBLISH_DROP_WARNING_INTERVAL_SECONDS,
        )

    def record_backpressure_state(self, *, queue_depth: int, logger: LoggerProtocol) -> None:
        if self._backpressure_warning_depth is None:
            return
        if queue_depth >= self._backpressure_warning_depth:
            if not self._backpressure_warning_active:
                logger.warning(
                    "Event bus queue depth %s exceeded warning threshold %s (max %s).",
                    queue_depth,
                    self._backpressure_warning_depth,
                    self._queue_size or "unbounded",
                )
                self._backpressure_warning_active = True
        elif self._backpressure_warning_active:
            self._backpressure_warning_active = False

    def record_publish_drop(
        self,
        *,
        event: Event,
        reason: str,
        queue_depth: int,
        metrics_recorder: MetricsManagerProtocol | None,
        logger: LoggerProtocol,
    ) -> None:
        event_type_name = type(event).__name__
        queue_size = self._queue_size or "unbounded"
        drop_report = self._publish_drop_tracker.record_drop()
        if metrics_recorder:
            metrics_recorder.increment_counter(
                *EVENT_BUS_COUNTER_EVENTS_DROPPED,
                value=drop_report.dropped_count,
            )
            metrics_recorder.set_gauge(*EVENT_BUS_GAUGE_QUEUE_DEPTH, value=queue_depth)
        log_queue_drop_with_tracker(
            logger,
            self._publish_drop_tracker,
            1,
            (
                f"Dropped event publish for {event_type_name} ({reason}) "
                f"queue_depth={queue_depth} max={queue_size}"
            ),
            drop_report=drop_report,
        )
