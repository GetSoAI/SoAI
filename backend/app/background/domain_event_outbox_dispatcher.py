"""SoAI - Transactional outbox dispatcher for domain events [backend/app/background/domain_event_outbox_dispatcher.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from app.background.domain_event_outbox_decoding import decode_outbox_event
from app.background.domain_event_outbox_settings import (
    load_domain_event_outbox_dispatcher_settings,
    load_domain_event_outbox_quarantine_delay_ms,
)
from app.background.domain_event_outbox_transitions import (
    DomainEventOutboxTransitionController,
)
from app.background.domain_event_outbox_wait import wait_for_outbox_dispatch_signal
from core.config.protocols import ConfigProtocol
from core.database.protocols import DatabaseCoreProtocol
from core.di.validation import require_dependencies
from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.exceptions import StateError
from core.errors.messages import resolve_exception_error_message
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.protocols import DurableEventDeliveryProtocol, EventBusProtocol
from core.events.types_base import Event
from core.events.types_system import DomainEventOutboxDispatchRequestedEvent
from core.logging.trace import get_logger
from core.runtime.soai_identifiers import create_system_id
from core.tasks.progress import await_background_task_shutdown
from core.tasks.protocols import (
    TaskCancellationBinderProtocol,
    TaskFinalizerTrackerProtocol,
)
from core.tasks.supervised_task_spawner import spawn_supervised_tracked_task
from core.timing.epoch import epoch_ms
from database.repositories.event_outbox.sync_ops import sync_claim_pending_domain_events

__all__ = (
    "DomainEventOutboxDispatcher",
    "DomainEventOutboxDispatcherDependencies",
)

LOGGER_NAME = "SoAI.app.background.domain_event_outbox_dispatcher"
OPERATION_DOMAIN_EVENT_OUTBOX_DISPATCHER_CLAIM = "domain_event_outbox_dispatcher.claim"
OPERATION_DOMAIN_EVENT_OUTBOX_DISPATCHER_DECODE = "domain_event_outbox_dispatcher.decode"
OPERATION_DOMAIN_EVENT_OUTBOX_DISPATCHER_DELIVER = "domain_event_outbox_dispatcher.deliver"
OPERATION_DOMAIN_EVENT_OUTBOX_DISPATCHER_PUBLISH_OBSERVER = (
    "domain_event_outbox_dispatcher.publish_observer"
)
OPERATION_DOMAIN_EVENT_OUTBOX_DISPATCHER_SHUTDOWN = "domain_event_outbox_dispatcher.shutdown"


@dataclass(frozen=True, slots=True)
class DomainEventOutboxDispatcherDependencies:
    config: ConfigProtocol
    database_core: DatabaseCoreProtocol
    event_bus: EventBusProtocol
    domain_event_delivery: DurableEventDeliveryProtocol
    cancellation_binder: TaskCancellationBinderProtocol
    finalizer_tracker: TaskFinalizerTrackerProtocol

    def __post_init__(self) -> None:
        require_dependencies(
            owner="DomainEventOutboxDispatcherDependencies",
            cancellation_binder=self.cancellation_binder,
            config=self.config,
            database_core=self.database_core,
            event_bus=self.event_bus,
            domain_event_delivery=self.domain_event_delivery,
            finalizer_tracker=self.finalizer_tracker,
        )


class DomainEventOutboxDispatcher:
    def __init__(self, deps: DomainEventOutboxDispatcherDependencies) -> None:
        self._deps = deps
        self._logger = get_logger(LOGGER_NAME)
        self._shutdown_event = asyncio.Event()
        self._dispatch_requested_event = asyncio.Event()
        self._dispatch_requested_handler: Callable[[Event], Awaitable[None]] = (
            self._handle_dispatch_requested
        )
        self._subscribed = False
        self._task: asyncio.Task[None] | None = None
        self._transition_controller = DomainEventOutboxTransitionController(
            self._deps.database_core.writer,
            logger=self._logger,
        )

    async def _handle_dispatch_requested(self, event: Event) -> None:
        if not isinstance(event, DomainEventOutboxDispatchRequestedEvent):
            return
        self._dispatch_requested_event.set()

    async def _drain_available_events(
        self,
        *,
        batch_limit: int,
        processing_timeout_ms: int,
    ) -> None:
        quarantine_delay_ms = load_domain_event_outbox_quarantine_delay_ms(self._deps.config)
        delivery_timeout_sec = max(0.1, float(processing_timeout_ms) / 1000.0 - 0.25)
        while not self._shutdown_event.is_set():
            now_ms = epoch_ms()
            await self._transition_controller.flush_pending_terminal_transitions(
                now_ms=now_ms,
                quarantine_delay_ms=quarantine_delay_ms,
            )
            try:
                claimed = await self._deps.database_core.writer.queue_write_operation(
                    sync_claim_pending_domain_events,
                    now_ms,
                    batch_limit,
                    processing_timeout_ms,
                )
            except RECOVERABLE_EXCEPTIONS as exception:
                log_exception(
                    self._logger,
                    exception,
                    message="Failed to claim domain outbox events.",
                    operation=OPERATION_DOMAIN_EVENT_OUTBOX_DISPATCHER_CLAIM,
                    level="warning",
                )
                return
            if not claimed:
                return
            for row in claimed:
                outbox_id_value = row.get("id")
                if not isinstance(outbox_id_value, int):
                    raise StateError("Outbox row id is invalid.")
                outbox_id = int(outbox_id_value)
                event_type_value = row.get("event_type")
                payload_value = row.get("payload_json")
                attempts_value = row.get("attempts")
                if not isinstance(attempts_value, int):
                    raise StateError("Outbox row attempts is invalid.")
                attempts = int(attempts_value)
                if self._transition_controller.should_skip_processing(outbox_id, now_ms=now_ms):
                    continue
                if not isinstance(event_type_value, str):
                    raise StateError("Outbox row event_type is invalid.")
                if not isinstance(payload_value, str):
                    raise StateError("Outbox row payload_json is invalid.")
                try:
                    event = decode_outbox_event(event_type_value, payload_value)
                except RECOVERABLE_EXCEPTIONS as exception:
                    await self._transition_controller.handle_decode_failure(
                        outbox_id=outbox_id,
                        attempts=attempts,
                        event_type=str(event_type_value),
                        error_message=resolve_exception_error_message(exception),
                        now_ms=now_ms,
                        quarantine_delay_ms=quarantine_delay_ms,
                    )
                    log_exception(
                        self._logger,
                        exception,
                        message="Dropping invalid outbox event (permanently failed).",
                        operation=OPERATION_DOMAIN_EVENT_OUTBOX_DISPATCHER_DECODE,
                        level="error",
                        details={"outbox_id": outbox_id, "event_type": str(event_type_value)},
                    )
                    continue
                try:
                    await self._deps.domain_event_delivery.deliver(
                        event,
                        timeout_sec=delivery_timeout_sec,
                    )
                except RECOVERABLE_EXCEPTIONS as exception:
                    await self._transition_controller.handle_delivery_failure(
                        outbox_id=outbox_id,
                        attempts=attempts,
                        event_type=str(event_type_value),
                        error_message=resolve_exception_error_message(exception),
                        now_ms=now_ms,
                    )
                    log_exception(
                        self._logger,
                        exception,
                        message="Failed durable delivery of outbox event; will retry.",
                        operation=OPERATION_DOMAIN_EVENT_OUTBOX_DISPATCHER_DELIVER,
                        level="warning",
                        details={"outbox_id": outbox_id, "event_type": str(event_type_value)},
                    )
                    continue
                try:
                    await self._deps.event_bus.publish(event)
                except RECOVERABLE_EXCEPTIONS as exception:
                    log_exception(
                        self._logger,
                        exception,
                        message="Failed to publish outbox event to observer bus (non-durable).",
                        operation=OPERATION_DOMAIN_EVENT_OUTBOX_DISPATCHER_PUBLISH_OBSERVER,
                        level="warning",
                        details={"outbox_id": outbox_id, "event_type": str(event_type_value)},
                    )
                await self._transition_controller.mark_published(
                    outbox_id=outbox_id,
                    attempts=attempts,
                    event_type=str(event_type_value),
                    published_at_ms=epoch_ms(),
                    now_ms=now_ms,
                    quarantine_delay_ms=quarantine_delay_ms,
                )

    async def start(self) -> None:
        if self._task is not None and (not self._task.done()):
            return
        if not self._subscribed:
            self._deps.event_bus.subscribe(
                DomainEventOutboxDispatchRequestedEvent,
                self._dispatch_requested_handler,
            )
            self._subscribed = True
        self._shutdown_event = asyncio.Event()
        self._dispatch_requested_event = asyncio.Event()
        self._transition_controller.reset()
        settings = load_domain_event_outbox_dispatcher_settings(self._deps.config)
        interval_sec = float(settings.poll_interval_sec)
        batch_limit = int(settings.batch_limit)
        processing_timeout_ms = int(settings.processing_timeout_ms)

        async def _run_loop() -> None:
            await self._drain_available_events(
                batch_limit=batch_limit,
                processing_timeout_ms=processing_timeout_ms,
            )
            while await wait_for_outbox_dispatch_signal(
                shutdown_event=self._shutdown_event,
                dispatch_requested_event=self._dispatch_requested_event,
                interval_sec=interval_sec,
            ):
                await self._drain_available_events(
                    batch_limit=batch_limit,
                    processing_timeout_ms=processing_timeout_ms,
                )

        self._task = spawn_supervised_tracked_task(
            _run_loop,
            cancellation_binder=self._deps.cancellation_binder,
            finalizer_tracker=self._deps.finalizer_tracker,
            cancellation_id=create_system_id(
                subsystem="domain_events_outbox",
                owner="dispatch",
                include_random_suffix=False,
            ),
            owner="domain_event_outbox_dispatcher",
            name="domain-event-outbox-dispatcher",
            logger=self._logger,
            metadata={
                "interval_ms": int(interval_sec * 1000.0),
                "batch_limit": int(batch_limit),
                "processing_timeout_ms": int(processing_timeout_ms),
            },
            restart_initial_delay_sec=float(settings.supervisor_restart_initial_sec),
            restart_max_delay_sec=float(settings.supervisor_restart_max_sec),
            restart_jitter_sec=float(settings.supervisor_restart_jitter_sec),
        )

    async def shutdown(self) -> None:
        self._shutdown_event.set()
        task = self._task
        self._task = None
        shutdown_message = "Domain outbox dispatcher failed during shutdown (non-critical)."
        await await_background_task_shutdown(
            task,
            logger=self._logger,
            operation="domain_event_outbox_dispatcher.shutdown",
            message=shutdown_message,
            level="debug",
        )
        if not self._subscribed:
            return
        try:
            self._deps.event_bus.unsubscribe(
                DomainEventOutboxDispatchRequestedEvent,
                self._dispatch_requested_handler,
            )
        except RECOVERABLE_EXCEPTIONS as exception:
            log_handled_exception(
                self._logger,
                exception,
                message="Failed to unsubscribe domain outbox dispatcher event handler (non-critical).",
                operation=OPERATION_DOMAIN_EVENT_OUTBOX_DISPATCHER_SHUTDOWN,
                level="warning",
            )
            return
        self._subscribed = False
