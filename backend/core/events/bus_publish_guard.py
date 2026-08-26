"""SoAI - Event bus publish preflight guard checks [backend/core/events/bus_publish_guard.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio

from core.concurrency.queue_ops import QueueDropTracker
from core.errors.exceptions import StateError
from core.events.bus_partitions import prune_inactive_worker_tasks
from core.events.bus_queue_ops import send_error_to_reply_channel
from core.events.completion_signals import mark_completion_signal_not_enqueued
from core.events.protocols import EventCompletionSignal
from core.events.types_base import Event, EventDelivery, ReplyableCommand
from core.logging.protocols import TraceLogger

__all__ = ("prepare_publish_worker_state",)


def prepare_publish_worker_state(
    *,
    event: Event,
    wait_for_completion: EventCompletionSignal | None,
    shutdown_event: asyncio.Event,
    worker_tasks: list[asyncio.Task[None]],
    logger: TraceLogger,
    reply_channel_drop_tracker: QueueDropTracker,
    raise_when_not_running: bool = True,
    notify_reply_channel: bool = True,
) -> list[asyncio.Task[None]]:
    if shutdown_event.is_set():
        logger.warning(
            "Publish attempt on %s after shutdown. Event dropped.",
            type(event).__name__,
        )
        if notify_reply_channel:
            if isinstance(event, ReplyableCommand):
                send_error_to_reply_channel(
                    event,
                    message="System is shutting down.",
                    logger=logger,
                    drop_tracker=reply_channel_drop_tracker,
                )
        mark_completion_signal_not_enqueued(
            wait_for_completion,
            failure_message="Event bus is shutting down.",
        )
        return []
    active_worker_tasks = prune_inactive_worker_tasks(worker_tasks)
    if not active_worker_tasks:
        mark_completion_signal_not_enqueued(
            wait_for_completion,
            failure_message="Event bus workers are not running.",
        )
        if shutdown_event.is_set():
            logger.warning(
                "Publish attempt on %s during shutdown (workers stopped). Event dropped.",
                type(event).__name__,
            )
            return []
        delivery = (
            event.delivery if isinstance(event, ReplyableCommand) else EventDelivery.MUST_DELIVER
        )
        if delivery == EventDelivery.DROPPABLE:
            logger.warning(
                "Dropping %s because EventBus workers are not running.",
                type(event).__name__,
            )
            return []
        message = (
            f"Event '{type(event).__name__}' published but EventBus is not running. Event dropped."
        )
        if not raise_when_not_running:
            logger.warning(message)
            return []
        logger.critical(message)
        raise StateError(message)
    return active_worker_tasks
