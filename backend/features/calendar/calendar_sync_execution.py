"""SoAI - Shared calendar sync execution flow [backend/features/calendar/calendar_sync_execution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.timing.epoch import epoch_ms
from core.types.json import JSONDict
from features.calendar.calendar_sync_status_support import (
    handle_calendar_sync_failure,
    persist_calendar_sync_success_status,
)
from features.calendar.calendar_transport_preparation import (
    prepare_service_calendar_transport_context,
)

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from features.calendar.calendar_caldav_context import (
        PreparedCalendarTransportContext,
    )
    from features.calendar.internal_protocols import CalendarSyncServiceProtocol

__all__ = (
    "CalendarSyncExecutionConfig",
    "execute_calendar_sync_operation",
)


@dataclass(frozen=True, slots=True)
class CalendarSyncExecutionConfig:
    logger: LoggerProtocol
    operation: str
    success_warning_log_message: str
    failure_warning_log_message: str
    warning_details: JSONDict


async def execute_calendar_sync_operation(
    *,
    service: CalendarSyncServiceProtocol,
    user_id: int,
    account_id: str,
    config: CalendarSyncExecutionConfig,
    executor: Callable[
        [PreparedCalendarTransportContext, int],
        Awaitable[tuple[JSONDict, list[str]]],
    ],
) -> JSONDict:
    sync_started_at_ms = epoch_ms()
    prepared: PreparedCalendarTransportContext | None = None
    try:
        prepared = await prepare_service_calendar_transport_context(
            service,
            user_id=user_id,
            account_id=account_id,
        )
        result, warnings = await executor(prepared, sync_started_at_ms)
        await persist_calendar_sync_success_status(
            service=service,
            user_id=user_id,
            account_id=account_id,
            sync_started_at_ms=sync_started_at_ms,
            logger=config.logger,
            operation=config.operation,
            warning_log_message=config.success_warning_log_message,
            warning_details=config.warning_details,
            warnings=warnings,
        )
        if warnings:
            result["warnings"] = warnings
        return result
    except RECOVERABLE_EXCEPTIONS as exception:
        await handle_calendar_sync_failure(
            service=service,
            user_id=user_id,
            account_id=account_id,
            sync_started_at_ms=sync_started_at_ms,
            logger=config.logger,
            operation=config.operation,
            warning_log_message=config.failure_warning_log_message,
            warning_details=config.warning_details,
            prepared=prepared,
            exception=exception,
        )
        raise
