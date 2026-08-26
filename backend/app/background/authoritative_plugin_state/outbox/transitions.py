"""SoAI - Authoritative plugin state outbox terminal transition controller [backend/app/background/authoritative_plugin_state/outbox/transitions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from app.background.outbox_transition_state import (
    OutboxTransitionState,
    PendingOutboxTerminalTransition,
)
from core.database.protocols import DatabaseWriterProtocol
from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.protocols import LoggerProtocol
from core.types.json import JSONValue
from database.repositories.plugins.authoritative_state_outbox import (
    compute_authoritative_state_retry_at,
    sync_mark_authoritative_state_event_failed,
    sync_mark_authoritative_state_event_published,
)

__all__ = ("AuthoritativePluginStateOutboxTransitionController",)

OUTBOX_TRANSITIONS_WRITE_OPERATION_SAFE = (
    "app.background.authoritative_plugin_state_outbox_transitions.write_operation_safe"
)


class AuthoritativePluginStateOutboxTransitionController:
    def __init__(self, writer: DatabaseWriterProtocol, *, logger: LoggerProtocol) -> None:
        self._writer = writer
        self._logger = logger
        self._state = OutboxTransitionState()

    def reset(self) -> None:
        self._state.reset()

    def should_skip_processing(self, outbox_id: int) -> bool:
        return self._state.should_skip_processing(outbox_id)

    async def flush_pending_terminal_transitions(
        self,
        *,
        now_ms: int,
    ) -> list[PendingOutboxTerminalTransition]:
        flushed_transitions: list[PendingOutboxTerminalTransition] = []
        for outbox_id, pending in self._state.pending_items():
            if now_ms < pending.next_attempt_at_ms:
                continue
            if pending.transition_type == "mark_published":
                published_at_ms = pending.published_at_ms or now_ms
                success = await self._mark_published_safe(
                    outbox_id,
                    published_at_ms,
                    operation="authoritative_plugin_state_dispatcher.flush_mark_published",
                    message="Failed to flush authoritative state outbox publish transition.",
                    details={"outbox_id": outbox_id},
                )
            else:
                success = await self._mark_failed_safe(
                    outbox_id,
                    pending.attempts,
                    pending.error_message,
                    operation="authoritative_plugin_state_dispatcher.flush_mark_failed",
                    message="Failed to flush authoritative state outbox failure transition.",
                    details={"outbox_id": outbox_id},
                )
            if success:
                self._state.clear_processing_delays(outbox_id)
                flushed_transitions.append(pending)
                continue
            next_attempt_at_ms = compute_authoritative_state_retry_at(
                attempts=pending.attempts + 1,
                base_delay_ms=500,
            )
            self._state.set_pending_transition(
                outbox_id,
                PendingOutboxTerminalTransition(
                    transition_type=pending.transition_type,
                    attempts=pending.attempts + 1,
                    next_attempt_at_ms=next_attempt_at_ms,
                    error_message=pending.error_message,
                    published_at_ms=pending.published_at_ms,
                    event_id=pending.event_id,
                ),
            )
        return flushed_transitions

    async def mark_published_or_defer(
        self,
        *,
        outbox_id: int,
        attempts: int,
        event_id: str,
        published_at_ms: int,
    ) -> bool:
        success = await self._mark_published_safe(
            outbox_id,
            published_at_ms,
            operation="authoritative_plugin_state_dispatcher.mark_published",
            message=(
                "Failed to mark authoritative state outbox row as published; "
                "deferring terminal transition."
            ),
            details={"outbox_id": outbox_id},
        )
        if success:
            return True
        self._state.set_pending_transition(
            outbox_id,
            PendingOutboxTerminalTransition(
                transition_type="mark_published",
                attempts=attempts,
                next_attempt_at_ms=compute_authoritative_state_retry_at(
                    attempts=attempts,
                    base_delay_ms=500,
                ),
                error_message="",
                published_at_ms=published_at_ms,
                event_id=event_id,
            ),
        )
        return False

    async def mark_failed_or_defer(
        self,
        *,
        outbox_id: int,
        attempts: int,
        event_id: str,
        error_message: str,
    ) -> bool:
        success = await self._mark_failed_safe(
            outbox_id,
            attempts,
            error_message,
            operation="authoritative_plugin_state_dispatcher.mark_failed",
            message=(
                "Failed to mark authoritative state outbox row as failed; "
                "deferring terminal transition."
            ),
            details={"outbox_id": outbox_id},
        )
        if success:
            return True
        self._state.set_pending_transition(
            outbox_id,
            PendingOutboxTerminalTransition(
                transition_type="mark_failed",
                attempts=attempts,
                next_attempt_at_ms=compute_authoritative_state_retry_at(
                    attempts=attempts,
                    base_delay_ms=500,
                ),
                error_message=error_message,
                published_at_ms=None,
                event_id=event_id,
            ),
        )
        return False

    async def _mark_published_safe(
        self,
        outbox_id: int,
        published_at_ms: int,
        *,
        operation: str,
        message: str,
        details: dict[str, JSONValue],
    ) -> bool:
        try:
            await self._writer.queue_write_operation(
                sync_mark_authoritative_state_event_published,
                outbox_id,
                published_at_ms,
            )
            return True
        except RECOVERABLE_EXCEPTIONS as exception:
            merged_details = dict(details)
            merged_details["operation"] = operation
            log_exception(
                self._logger,
                exception,
                message=message,
                operation=OUTBOX_TRANSITIONS_WRITE_OPERATION_SAFE,
                level="warning",
                details=merged_details,
            )
            return False

    async def _mark_failed_safe(
        self,
        outbox_id: int,
        attempts: int,
        error_message: str,
        *,
        operation: str,
        message: str,
        details: dict[str, JSONValue],
    ) -> bool:
        try:
            await self._writer.queue_write_operation(
                sync_mark_authoritative_state_event_failed,
                outbox_id,
                attempts,
                error_message,
            )
            return True
        except RECOVERABLE_EXCEPTIONS as exception:
            merged_details = dict(details)
            merged_details["operation"] = operation
            log_exception(
                self._logger,
                exception,
                message=message,
                operation=OUTBOX_TRANSITIONS_WRITE_OPERATION_SAFE,
                level="warning",
                details=merged_details,
            )
            return False
