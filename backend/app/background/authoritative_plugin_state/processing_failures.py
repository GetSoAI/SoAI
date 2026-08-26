"""SoAI - Authoritative plugin state processing failure tracking [backend/app/background/authoritative_plugin_state/processing_failures.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from app.background.authoritative_plugin_state.outbox.failures import (
    AuthoritativePluginStateOutboxFailureRecorder,
)
from database.repositories.plugins.authoritative_state_outbox import (
    compute_authoritative_state_retry_at,
)

__all__ = (
    "AuthoritativePluginStateProcessingFailures",
    "PendingAuthoritativeProcessingFailure",
)


@dataclass(frozen=True, slots=True)
class PendingAuthoritativeProcessingFailure:
    attempts: int
    retry_attempts: int
    event_id: str
    error_message: str
    next_attempt_at_ms: int


class AuthoritativePluginStateProcessingFailures:
    def __init__(self, failure_recorder: AuthoritativePluginStateOutboxFailureRecorder) -> None:
        self._failure_recorder = failure_recorder
        self._blocked_processing_rows: set[int] = set()
        self._pending_processing_failures: dict[int, PendingAuthoritativeProcessingFailure] = {}

    def reset(self) -> None:
        self._blocked_processing_rows.clear()
        self._pending_processing_failures.clear()

    def should_skip_processing(self, outbox_id: int) -> bool:
        return (
            outbox_id in self._blocked_processing_rows
            or outbox_id in self._pending_processing_failures
        )

    def block_processing_row(self, outbox_id: int) -> None:
        self._blocked_processing_rows.add(outbox_id)

    async def flush_pending_updates(self, *, now_ms: int) -> None:
        for outbox_id, pending in list(self._pending_processing_failures.items()):
            if now_ms < pending.next_attempt_at_ms:
                continue
            persisted = await self._failure_recorder.record_processing_failure(
                outbox_id=outbox_id,
                attempts=pending.attempts,
                message=pending.error_message,
            )
            if persisted:
                self._pending_processing_failures.pop(outbox_id, None)
                continue
            self._pending_processing_failures[outbox_id] = PendingAuthoritativeProcessingFailure(
                attempts=pending.attempts,
                retry_attempts=pending.retry_attempts + 1,
                event_id=pending.event_id,
                error_message=pending.error_message,
                next_attempt_at_ms=compute_authoritative_state_retry_at(
                    attempts=pending.retry_attempts + 1,
                    base_delay_ms=500,
                ),
            )

    def schedule_persistence_retry(
        self,
        *,
        outbox_id: int,
        attempts: int,
        event_id: str,
        error_message: str,
    ) -> None:
        self._pending_processing_failures[outbox_id] = PendingAuthoritativeProcessingFailure(
            attempts=attempts,
            retry_attempts=1,
            event_id=event_id,
            error_message=error_message,
            next_attempt_at_ms=compute_authoritative_state_retry_at(
                attempts=1,
                base_delay_ms=500,
            ),
        )
