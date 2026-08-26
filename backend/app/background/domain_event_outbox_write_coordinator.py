"""SoAI - Domain event outbox transition persistence coordinator [backend/app/background/domain_event_outbox_write_coordinator.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.database.protocols import DatabaseWriterProtocol
from core.errors.exception_logging import log_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.protocols import LoggerProtocol
from database.repositories.event_outbox.sync_ops import (
    sync_mark_domain_event_failed_permanently,
    sync_mark_domain_event_published,
    sync_quarantine_domain_event_outbox_row,
    sync_record_domain_event_failure,
)

if TYPE_CHECKING:
    from core.types.json import JSONValue

__all__ = (
    "DomainEventOutboxWriteCoordinator",
    "DomainEventWriteLogContext",
)

OPERATION_APP_BACKGROUND_DOMAIN_EVENT_OUTBOX_WRITE_COORDINATOR_WRITE_OPERATION_SAFE = (
    "app.background.domain_event_outbox_write_coordinator.write_operation_safe"
)


@dataclass(frozen=True, slots=True)
class DomainEventWriteLogContext:
    operation: str
    details: dict[str, JSONValue]
    level: str
    message: str


class DomainEventOutboxWriteCoordinator:
    def __init__(self, writer: DatabaseWriterProtocol, *, logger: LoggerProtocol) -> None:
        self._writer = writer
        self._logger = logger

    async def mark_published(
        self,
        outbox_id: int,
        published_at_ms: int,
        *,
        log_context: DomainEventWriteLogContext,
    ) -> bool:
        try:
            await self._writer.queue_write_operation(
                sync_mark_domain_event_published,
                outbox_id,
                published_at_ms,
            )
            return True
        except RECOVERABLE_EXCEPTIONS as exception:
            details = dict(log_context.details)
            details["operation"] = log_context.operation
            log_exception(
                self._logger,
                exception,
                message=log_context.message,
                operation=OPERATION_APP_BACKGROUND_DOMAIN_EVENT_OUTBOX_WRITE_COORDINATOR_WRITE_OPERATION_SAFE,
                level=log_context.level,
                details=details,
            )
            return False

    async def mark_failed_permanently(
        self,
        outbox_id: int,
        attempts: int,
        error_message: str,
        *,
        log_context: DomainEventWriteLogContext,
    ) -> bool:
        try:
            await self._writer.queue_write_operation(
                sync_mark_domain_event_failed_permanently,
                outbox_id,
                attempts,
                error_message,
            )
            return True
        except RECOVERABLE_EXCEPTIONS as exception:
            details = dict(log_context.details)
            details["operation"] = log_context.operation
            log_exception(
                self._logger,
                exception,
                message=log_context.message,
                operation=OPERATION_APP_BACKGROUND_DOMAIN_EVENT_OUTBOX_WRITE_COORDINATOR_WRITE_OPERATION_SAFE,
                level=log_context.level,
                details=details,
            )
            return False

    async def record_failure(
        self,
        outbox_id: int,
        attempts: int,
        next_attempt_at_ms: int,
        error_message: str,
        *,
        log_context: DomainEventWriteLogContext,
    ) -> bool:
        try:
            await self._writer.queue_write_operation(
                sync_record_domain_event_failure,
                outbox_id,
                attempts,
                next_attempt_at_ms,
                error_message,
            )
            return True
        except RECOVERABLE_EXCEPTIONS as exception:
            details = dict(log_context.details)
            details["operation"] = log_context.operation
            log_exception(
                self._logger,
                exception,
                message=log_context.message,
                operation=OPERATION_APP_BACKGROUND_DOMAIN_EVENT_OUTBOX_WRITE_COORDINATOR_WRITE_OPERATION_SAFE,
                level=log_context.level,
                details=details,
            )
            return False

    async def quarantine_row(
        self,
        outbox_id: int,
        attempts: int,
        next_attempt_at_ms: int,
        error_message: str,
        *,
        log_context: DomainEventWriteLogContext,
    ) -> bool:
        try:
            await self._writer.queue_write_operation(
                sync_quarantine_domain_event_outbox_row,
                outbox_id,
                attempts,
                next_attempt_at_ms,
                error_message,
            )
            return True
        except RECOVERABLE_EXCEPTIONS as exception:
            details = dict(log_context.details)
            details["operation"] = log_context.operation
            log_exception(
                self._logger,
                exception,
                message=log_context.message,
                operation=OPERATION_APP_BACKGROUND_DOMAIN_EVENT_OUTBOX_WRITE_COORDINATOR_WRITE_OPERATION_SAFE,
                level=log_context.level,
                details=details,
            )
            return False
