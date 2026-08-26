"""SoAI - Authoritative plugin state outbox retryable failure persistence [backend/app/background/authoritative_plugin_state/outbox/failures.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.database.protocols import DatabaseWriterProtocol
from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.protocols import LoggerProtocol
from database.repositories.plugins.authoritative_state_outbox import (
    compute_authoritative_state_retry_at,
    sync_record_authoritative_state_enqueue_failure,
    sync_record_authoritative_state_processing_failure,
)

__all__ = ("AuthoritativePluginStateOutboxFailureRecorder",)

OPERATION_APP_BACKGROUND_AUTHORITATIVE_PLUGIN_STATE_OUTBOX_FAILURES_WRITE_OPERATION_SAFE = (
    "app.background.authoritative_plugin_state_outbox_failures.write_operation_safe"
)


_DISPATCHER_RETRY_BASE_DELAY_MS = 500


class AuthoritativePluginStateOutboxFailureRecorder:
    def __init__(self, writer: DatabaseWriterProtocol, *, logger: LoggerProtocol) -> None:
        self._writer = writer
        self._logger = logger

    async def record_enqueue_failure(
        self,
        *,
        outbox_id: int,
        attempts: int,
        message: str,
    ) -> bool:
        next_attempt_at_ms = compute_authoritative_state_retry_at(
            attempts=attempts,
            base_delay_ms=_DISPATCHER_RETRY_BASE_DELAY_MS,
        )
        return await self._record_enqueue_failure_safe(
            outbox_id,
            attempts,
            next_attempt_at_ms,
            message,
            operation="authoritative_plugin_state_dispatcher.record_enqueue_failure",
            log_message="Failed to persist authoritative state enqueue failure.",
        )

    async def record_processing_failure(
        self,
        *,
        outbox_id: int,
        attempts: int,
        message: str,
    ) -> bool:
        return await self._record_processing_failure_safe(
            outbox_id,
            attempts,
            message,
            operation="authoritative_plugin_state_dispatcher.record_processing_failure",
            log_message="Failed to persist authoritative state processing failure.",
        )

    async def _record_enqueue_failure_safe(
        self,
        outbox_id: int,
        attempts: int,
        next_attempt_at_ms: int,
        message: str,
        *,
        operation: str,
        log_message: str,
    ) -> bool:
        try:
            await self._writer.queue_write_operation(
                sync_record_authoritative_state_enqueue_failure,
                outbox_id,
                attempts,
                next_attempt_at_ms,
                message,
            )
            return True
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                self._logger,
                exception,
                message=log_message,
                operation=OPERATION_APP_BACKGROUND_AUTHORITATIVE_PLUGIN_STATE_OUTBOX_FAILURES_WRITE_OPERATION_SAFE,
                level="warning",
                details={"outbox_id": outbox_id, "operation": operation},
            )
            return False

    async def _record_processing_failure_safe(
        self,
        outbox_id: int,
        attempts: int,
        message: str,
        *,
        operation: str,
        log_message: str,
    ) -> bool:
        try:
            await self._writer.queue_write_operation(
                sync_record_authoritative_state_processing_failure,
                outbox_id,
                attempts,
                message,
            )
            return True
        except RECOVERABLE_EXCEPTIONS as exception:
            log_exception(
                self._logger,
                exception,
                message=log_message,
                operation=OPERATION_APP_BACKGROUND_AUTHORITATIVE_PLUGIN_STATE_OUTBOX_FAILURES_WRITE_OPERATION_SAFE,
                level="warning",
                details={"outbox_id": outbox_id, "operation": operation},
            )
            return False
