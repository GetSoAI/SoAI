"""SoAI - Event bus publish exception path handlers [backend/core/events/bus_publish_error_paths.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.concurrency.queue_ops import QueueDropTracker
from core.errors.exception_logging import log_exception
from core.errors.exceptions import ServiceUnavailableError
from core.events.bus_queue_ops import send_error_to_reply_channel
from core.events.completion_signals import mark_completion_signal_not_enqueued
from core.events.protocols import EventCompletionSignal
from core.events.types_base import Event, EventDelivery, ReplyableCommand

if TYPE_CHECKING:
    from core.events.bus_backpressure import EventBusBackpressureTracker
    from core.logging.protocols import TraceLogger
    from core.metrics.protocols import MetricsManagerProtocol

__all__ = ("handle_publish_timeout_exception",)

OPERATION = "event_bus.publish"


def handle_publish_timeout_exception(
    *,
    exception: TimeoutError,
    event: Event,
    delivery: EventDelivery,
    wait_for_completion: EventCompletionSignal | None,
    queue_depth: int,
    aggregate_queue_max: int,
    publish_timeout: float | None,
    backpressure_tracker: EventBusBackpressureTracker,
    metrics_recorder: MetricsManagerProtocol | None,
    logger: TraceLogger,
    reply_channel_drop_tracker: QueueDropTracker,
) -> None:
    mark_completion_signal_not_enqueued(
        wait_for_completion,
        failure_message="Event bus publish timed out before enqueue completed.",
    )
    if delivery == EventDelivery.DROPPABLE:
        backpressure_tracker.record_publish_drop(
            event=event,
            reason="publish_timeout",
            queue_depth=queue_depth,
            metrics_recorder=metrics_recorder,
            logger=logger,
        )
        return
    if isinstance(event, ReplyableCommand):
        reply_status = send_error_to_reply_channel(
            event,
            message="Event bus publish timed out due to backpressure.",
            logger=logger,
            drop_tracker=reply_channel_drop_tracker,
        )
    else:
        reply_status = "no_channel"
    if reply_status == "queue_full":
        backpressure_tracker.record_publish_drop(
            event=event,
            reason="reply_channel_full",
            queue_depth=queue_depth,
            metrics_recorder=metrics_recorder,
            logger=logger,
        )
    message = (
        f"Event bus publish timed out after {publish_timeout:.3f}s "
        f"(depth={queue_depth}, max={aggregate_queue_max})."
    )
    log_exception(
        logger,
        exception,
        message=message,
        operation=OPERATION,
        details={"event_type": type(event).__name__, "delivery": str(delivery)},
    )
    raise ServiceUnavailableError(
        message,
        operation="event_bus.publish",
        details={
            "event_type": type(event).__name__,
            "delivery": str(delivery),
            "queue_depth": queue_depth,
            "queue_max": aggregate_queue_max,
        },
    ) from exception
