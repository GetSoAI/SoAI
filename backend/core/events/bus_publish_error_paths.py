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
    from core.events.bus_partitions import EventBusQueuePressure
    from core.logging.protocols import TraceLogger
    from core.metrics.protocols import MetricsManagerProtocol

__all__ = (
    "handle_publish_timeout_exception",
    "is_event_bus_owned_publication_failure",
    "reject_unavailable_partition",
)

OPERATION = "event_bus.publish"


def is_event_bus_owned_publication_failure(exception: BaseException) -> bool:
    return isinstance(exception, ServiceUnavailableError) and exception.operation == OPERATION


def _reject_publication(
    *,
    event: Event,
    delivery: EventDelivery,
    wait_for_completion: EventCompletionSignal | None,
    reason: str,
    failure_message: str,
    reply_message: str,
    message: str,
    raise_when_rejected: bool,
    pressure: EventBusQueuePressure,
    cause: BaseException | None,
    backpressure_tracker: EventBusBackpressureTracker,
    metrics_recorder: MetricsManagerProtocol | None,
    logger: TraceLogger,
    reply_channel_drop_tracker: QueueDropTracker,
) -> None:
    mark_completion_signal_not_enqueued(wait_for_completion, failure_message=failure_message)
    if delivery == EventDelivery.DROPPABLE or not raise_when_rejected:
        backpressure_tracker.record_publish_drop(
            event=event,
            reason=reason,
            pressure=pressure,
            metrics_recorder=metrics_recorder,
            logger=logger,
        )
        return
    if isinstance(event, ReplyableCommand):
        reply_status = send_error_to_reply_channel(
            event,
            message=reply_message,
            logger=logger,
            drop_tracker=reply_channel_drop_tracker,
        )
        if reply_status == "queue_full":
            backpressure_tracker.record_publish_drop(
                event=event,
                reason="reply_channel_full",
                pressure=pressure,
                metrics_recorder=metrics_recorder,
                logger=logger,
            )
    error = ServiceUnavailableError(
        message,
        operation=OPERATION,
        details={
            "event_type": type(event).__name__,
            "delivery": str(delivery),
            **pressure.details(),
        },
        cause=cause,
    )
    log_exception(
        logger,
        cause or error,
        message=message,
        operation=OPERATION,
        details={"event_type": type(event).__name__, "delivery": str(delivery)},
    )
    raise error from cause


def handle_publish_timeout_exception(
    *,
    exception: TimeoutError,
    event: Event,
    delivery: EventDelivery,
    wait_for_completion: EventCompletionSignal | None,
    pressure: EventBusQueuePressure,
    publish_timeout: float | None,
    backpressure_tracker: EventBusBackpressureTracker,
    metrics_recorder: MetricsManagerProtocol | None,
    logger: TraceLogger,
    reply_channel_drop_tracker: QueueDropTracker,
) -> None:
    _reject_publication(
        event=event,
        delivery=delivery,
        wait_for_completion=wait_for_completion,
        reason="publish_timeout",
        failure_message="Event bus publish timed out before enqueue completed.",
        reply_message="Event bus publish timed out due to backpressure.",
        message=(
            f"Event bus publish timed out after {publish_timeout:.3f}s ({pressure.describe()})."
        ),
        raise_when_rejected=True,
        pressure=pressure,
        cause=exception,
        backpressure_tracker=backpressure_tracker,
        metrics_recorder=metrics_recorder,
        logger=logger,
        reply_channel_drop_tracker=reply_channel_drop_tracker,
    )


def reject_unavailable_partition(
    *,
    event: Event,
    delivery: EventDelivery,
    wait_for_completion: EventCompletionSignal | None,
    pressure: EventBusQueuePressure,
    raise_when_rejected: bool,
    cause: BaseException | None,
    backpressure_tracker: EventBusBackpressureTracker,
    metrics_recorder: MetricsManagerProtocol | None,
    logger: TraceLogger,
    reply_channel_drop_tracker: QueueDropTracker,
) -> None:
    failure_message = f"Event bus partition {pressure.partition_index} is unavailable."
    _reject_publication(
        event=event,
        delivery=delivery,
        wait_for_completion=wait_for_completion,
        reason="partition_unavailable",
        failure_message=failure_message,
        reply_message=failure_message,
        message=(
            f"Event '{type(event).__name__}' was rejected because its event bus partition "
            f"has no running worker ({pressure.describe()})."
        ),
        raise_when_rejected=raise_when_rejected,
        pressure=pressure,
        cause=cause,
        backpressure_tracker=backpressure_tracker,
        metrics_recorder=metrics_recorder,
        logger=logger,
        reply_channel_drop_tracker=reply_channel_drop_tracker,
    )
