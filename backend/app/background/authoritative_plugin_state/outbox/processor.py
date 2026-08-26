"""SoAI - Authoritative plugin state outbox row processing [backend/app/background/authoritative_plugin_state/outbox/processor.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from app.background.authoritative_plugin_state.codec import (
    decode_authoritative_plugin_state_event,
)
from app.background.authoritative_plugin_state.outbox.failures import (
    AuthoritativePluginStateOutboxFailureRecorder,
)
from app.background.authoritative_plugin_state.outbox.rows import (
    parse_claimed_authoritative_plugin_state_outbox_row,
)
from app.background.authoritative_plugin_state.outbox.transitions import (
    AuthoritativePluginStateOutboxTransitionController,
)
from app.background.authoritative_plugin_state.processing_failures import (
    AuthoritativePluginStateProcessingFailures,
)
from app.background.authoritative_plugin_state.waiters import (
    AuthoritativePluginStateWaiters,
)
from core.errors.exception_logging import log_exception
from core.errors.messages import resolve_exception_error_message
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.events.completion_signals import EventDispatchCompletion
from core.events.protocols import EventBusProtocol
from core.logging.protocols import LoggerProtocol
from core.timing.epoch import epoch_ms

if TYPE_CHECKING:
    from database.core.sqlite_values import SQLiteRowDict

__all__ = ("AuthoritativePluginStateOutboxProcessor",)

OPERATION_AUTHORITATIVE_PLUGIN_STATE_DISPATCHER_DECODE = (
    "authoritative_plugin_state_dispatcher.decode"
)
OPERATION_AUTHORITATIVE_PLUGIN_STATE_DISPATCHER_PUBLISH = (
    "authoritative_plugin_state_dispatcher.publish"
)


class AuthoritativePluginStateOutboxProcessor:
    def __init__(
        self,
        *,
        event_bus: EventBusProtocol,
        waiters: AuthoritativePluginStateWaiters,
        failure_recorder: AuthoritativePluginStateOutboxFailureRecorder,
        transition_controller: AuthoritativePluginStateOutboxTransitionController,
        logger: LoggerProtocol,
    ) -> None:
        self._event_bus = event_bus
        self._waiters = waiters
        self._failure_recorder = failure_recorder
        self._transition_controller = transition_controller
        self._logger = logger
        self._processing_failures = AuthoritativePluginStateProcessingFailures(failure_recorder)

    def reset(self) -> None:
        self._processing_failures.reset()
        self._transition_controller.reset()

    def should_skip_processing(self, outbox_id: int) -> bool:
        return self._processing_failures.should_skip_processing(
            outbox_id,
        ) or self._transition_controller.should_skip_processing(outbox_id)

    async def flush_pending_updates(self, *, now_ms: int) -> None:
        flushed = await self._transition_controller.flush_pending_terminal_transitions(
            now_ms=now_ms,
        )
        for pending in flushed:
            if pending.transition_type == "mark_published" and pending.event_id is not None:
                await self._waiters.resolve_success(pending.event_id)
        await self._processing_failures.flush_pending_updates(now_ms=now_ms)

    async def process_row(self, row: SQLiteRowDict) -> None:
        claimed_row = parse_claimed_authoritative_plugin_state_outbox_row(row)
        if self.should_skip_processing(claimed_row.outbox_id):
            return
        try:
            event = decode_authoritative_plugin_state_event(
                event_type=claimed_row.event_type,
                payload_json=claimed_row.payload_json,
            )
        except RECOVERABLE_EXCEPTIONS as exception:
            await self._mark_failed_permanently(
                outbox_id=claimed_row.outbox_id,
                attempts=claimed_row.attempts + 1,
                event_id=claimed_row.event_id,
                message=resolve_exception_error_message(exception),
            )
            log_exception(
                self._logger,
                exception,
                message="Dropping invalid authoritative plugin state outbox row.",
                operation=OPERATION_AUTHORITATIVE_PLUGIN_STATE_DISPATCHER_DECODE,
                level="error",
                details={"outbox_id": claimed_row.outbox_id, "event_type": claimed_row.event_type},
            )
            return
        completion = EventDispatchCompletion()
        try:
            await self._event_bus.publish(event, wait_for_completion=completion)
        except RECOVERABLE_EXCEPTIONS as exception:
            await self._failure_recorder.record_enqueue_failure(
                outbox_id=claimed_row.outbox_id,
                attempts=claimed_row.attempts + 1,
                message=resolve_exception_error_message(exception),
            )
            log_exception(
                self._logger,
                exception,
                message="Failed to enqueue authoritative plugin state event; will retry.",
                operation=OPERATION_AUTHORITATIVE_PLUGIN_STATE_DISPATCHER_PUBLISH,
                level="warning",
                details={"outbox_id": claimed_row.outbox_id, "event_type": claimed_row.event_type},
            )
            return
        await completion.wait()
        snapshot = completion.snapshot()
        if snapshot.succeeded:
            await self._mark_published(
                outbox_id=claimed_row.outbox_id,
                attempts=claimed_row.attempts + 1,
                event_id=claimed_row.event_id,
            )
            return
        self._processing_failures.block_processing_row(claimed_row.outbox_id)
        await self._record_processing_failure(
            outbox_id=claimed_row.outbox_id,
            attempts=claimed_row.attempts + 1,
            event_id=claimed_row.event_id,
            message=snapshot.failure_message or "Authoritative state dispatch failed.",
        )

    async def _record_processing_failure(
        self,
        *,
        outbox_id: int,
        event_id: str,
        attempts: int,
        message: str,
    ) -> None:
        persisted = await self._failure_recorder.record_processing_failure(
            outbox_id=outbox_id,
            attempts=attempts,
            message=message,
        )
        if not persisted:
            self._processing_failures.schedule_persistence_retry(
                outbox_id=outbox_id,
                attempts=attempts,
                event_id=event_id,
                error_message=message,
            )

    async def _mark_published(self, *, outbox_id: int, attempts: int, event_id: str) -> None:
        marked_published = await self._transition_controller.mark_published_or_defer(
            outbox_id=outbox_id,
            attempts=attempts,
            event_id=event_id,
            published_at_ms=epoch_ms(),
        )
        if marked_published:
            await self._waiters.resolve_success(event_id)

    async def _mark_failed_permanently(
        self,
        *,
        outbox_id: int,
        attempts: int,
        event_id: str,
        message: str,
    ) -> None:
        await self._transition_controller.mark_failed_or_defer(
            outbox_id=outbox_id,
            attempts=attempts,
            event_id=event_id,
            error_message=message,
        )
        await self._waiters.resolve_failure(event_id, message)
