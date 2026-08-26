"""SoAI - Domain event outbox transition controller (quarantine and retries) [backend/app/background/domain_event_outbox_transitions.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from app.background.domain_event_outbox_write_coordinator import (
    DomainEventOutboxWriteCoordinator,
    DomainEventWriteLogContext,
)
from app.background.outbox_transition_state import (
    OutboxTransitionState,
    PendingOutboxTerminalTransition,
    compute_next_attempt_at_ms,
)
from core.database.protocols import DatabaseWriterProtocol
from core.logging.protocols import LoggerProtocol

__all__ = ("DomainEventOutboxTransitionController",)


class DomainEventOutboxTransitionController:
    def __init__(self, writer: DatabaseWriterProtocol, *, logger: LoggerProtocol) -> None:
        self._writer = writer
        self._logger = logger
        self._write_coordinator = DomainEventOutboxWriteCoordinator(writer, logger=logger)
        self._state = OutboxTransitionState()

    def reset(self) -> None:
        self._state.reset()

    def _quarantine_in_memory(self, outbox_id: int, *, now_ms: int, delay_ms: int) -> None:
        self._state.quarantine(outbox_id, now_ms=now_ms, delay_ms=delay_ms)

    def should_skip_processing(self, outbox_id: int, *, now_ms: int) -> bool:
        return self._state.should_skip_processing(outbox_id, now_ms=now_ms)

    async def _quarantine_row_best_effort(
        self,
        *,
        outbox_id: int,
        attempts: int,
        next_attempt_at_ms: int,
        error_message: str,
        now_ms: int,
        quarantine_delay_ms: int,
        source: str,
    ) -> None:
        self._quarantine_in_memory(outbox_id, now_ms=now_ms, delay_ms=quarantine_delay_ms)
        await self._write_coordinator.quarantine_row(
            outbox_id,
            attempts,
            next_attempt_at_ms,
            error_message,
            log_context=DomainEventWriteLogContext(
                operation="domain_event_outbox_dispatcher.quarantine",
                details={"outbox_id": int(outbox_id), "source": str(source)},
                level="warning",
                message="Failed to quarantine domain outbox event row.",
            ),
        )

    async def flush_pending_terminal_transitions(
        self,
        *,
        now_ms: int,
        quarantine_delay_ms: int,
    ) -> None:
        pending_items = self._state.pending_items()
        if not pending_items:
            return
        for outbox_id, pending in pending_items:
            if now_ms < pending.next_attempt_at_ms:
                continue
            if pending.transition_type == "mark_published":
                published_at_ms = pending.published_at_ms
                if published_at_ms is None:
                    self._logger.error(
                        "Pending outbox mark_published transition missing published_at_ms; using now_ms.",
                        extra={"outbox_id": int(outbox_id)},
                    )
                    published_at_ms = int(now_ms)
                success = await self._write_coordinator.mark_published(
                    outbox_id,
                    int(published_at_ms),
                    log_context=DomainEventWriteLogContext(
                        operation="domain_event_outbox_dispatcher.flush_mark_published",
                        details={"outbox_id": int(outbox_id)},
                        level="warning",
                        message="Failed to flush pending outbox mark_published transition.",
                    ),
                )
                if success:
                    self._state.clear_processing_delays(outbox_id)
                    continue
            if pending.transition_type == "mark_failed_permanently":
                success = await self._write_coordinator.mark_failed_permanently(
                    outbox_id,
                    pending.attempts,
                    pending.error_message,
                    log_context=DomainEventWriteLogContext(
                        operation="domain_event_outbox_dispatcher.flush_mark_failed_permanently",
                        details={"outbox_id": int(outbox_id)},
                        level="warning",
                        message=(
                            "Failed to flush pending outbox mark_failed_permanently transition."
                        ),
                    ),
                )
                if success:
                    self._state.clear_processing_delays(outbox_id)
                    continue
            next_attempt_at = compute_next_attempt_at_ms(pending.attempts + 1, now_ms=now_ms)
            self._state.set_pending_transition(
                outbox_id,
                PendingOutboxTerminalTransition(
                    transition_type=pending.transition_type,
                    attempts=int(pending.attempts) + 1,
                    next_attempt_at_ms=int(next_attempt_at),
                    error_message=pending.error_message,
                    published_at_ms=pending.published_at_ms,
                ),
            )
            self._quarantine_in_memory(outbox_id, now_ms=now_ms, delay_ms=quarantine_delay_ms)

    async def handle_decode_failure(
        self,
        *,
        outbox_id: int,
        attempts: int,
        event_type: str,
        error_message: str,
        now_ms: int,
        quarantine_delay_ms: int,
    ) -> None:
        mark_failed_success = await self._write_coordinator.mark_failed_permanently(
            outbox_id,
            attempts + 1,
            error_message,
            log_context=DomainEventWriteLogContext(
                operation="domain_event_outbox_dispatcher.decode_mark_failed",
                details={"outbox_id": int(outbox_id), "event_type": str(event_type)},
                level="error",
                message="Failed to mark invalid outbox event as permanently failed.",
            ),
        )
        if mark_failed_success:
            return
        next_attempt_at_ms = int(now_ms) + int(quarantine_delay_ms)
        self._state.set_pending_transition(
            outbox_id,
            PendingOutboxTerminalTransition(
                transition_type="mark_failed_permanently",
                attempts=int(attempts) + 1,
                next_attempt_at_ms=compute_next_attempt_at_ms(attempts + 1, now_ms=now_ms),
                error_message=str(error_message),
            ),
        )
        await self._quarantine_row_best_effort(
            outbox_id=outbox_id,
            attempts=attempts + 1,
            next_attempt_at_ms=next_attempt_at_ms,
            error_message=f"Quarantined after failed mark_failed_permanently: {error_message}",
            now_ms=now_ms,
            quarantine_delay_ms=quarantine_delay_ms,
            source="decode_mark_failed",
        )

    async def handle_delivery_failure(
        self,
        *,
        outbox_id: int,
        attempts: int,
        event_type: str,
        error_message: str,
        now_ms: int,
    ) -> None:
        next_attempt_at = compute_next_attempt_at_ms(attempts + 1, now_ms=now_ms)
        failure_recorded = await self._write_coordinator.record_failure(
            outbox_id,
            attempts + 1,
            int(next_attempt_at),
            str(error_message),
            log_context=DomainEventWriteLogContext(
                operation="domain_event_outbox_dispatcher.deliver_record_failure",
                details={"outbox_id": int(outbox_id), "event_type": str(event_type)},
                level="warning",
                message="Failed to record domain outbox delivery failure; will quarantine with backoff.",
            ),
        )
        if failure_recorded:
            return
        await self._quarantine_row_best_effort(
            outbox_id=outbox_id,
            attempts=attempts + 1,
            next_attempt_at_ms=int(next_attempt_at),
            error_message=f"Quarantined after failed record_failure: {error_message}",
            now_ms=now_ms,
            quarantine_delay_ms=int(next_attempt_at) - int(now_ms),
            source="deliver_record_failure",
        )

    async def mark_published(
        self,
        *,
        outbox_id: int,
        attempts: int,
        event_type: str,
        published_at_ms: int,
        now_ms: int,
        quarantine_delay_ms: int,
    ) -> bool:
        mark_published_success = await self._write_coordinator.mark_published(
            outbox_id,
            int(published_at_ms),
            log_context=DomainEventWriteLogContext(
                operation="domain_event_outbox_dispatcher.mark_published",
                details={"outbox_id": int(outbox_id), "event_type": str(event_type)},
                level="warning",
                message="Failed to mark outbox event as published; quarantining row.",
            ),
        )
        if mark_published_success:
            return True
        next_attempt_at_ms = int(now_ms) + int(quarantine_delay_ms)
        self._state.set_pending_transition(
            outbox_id,
            PendingOutboxTerminalTransition(
                transition_type="mark_published",
                attempts=int(attempts) + 1,
                next_attempt_at_ms=compute_next_attempt_at_ms(attempts + 1, now_ms=now_ms),
                error_message="",
                published_at_ms=int(published_at_ms),
            ),
        )
        await self._quarantine_row_best_effort(
            outbox_id=outbox_id,
            attempts=attempts + 1,
            next_attempt_at_ms=next_attempt_at_ms,
            error_message="Quarantined after failed mark_published.",
            now_ms=now_ms,
            quarantine_delay_ms=quarantine_delay_ms,
            source="mark_published",
        )
        return False
