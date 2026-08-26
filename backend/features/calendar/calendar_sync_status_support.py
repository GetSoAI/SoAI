"""SoAI - Calendar sync status persistence helpers [backend/features/calendar/calendar_sync_status_support.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception
from core.errors.messages import resolve_exception_error_message
from core.errors.public_projection import project_public_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.external_accounts.sync_error_dedup import resolve_previous_sync_error
from features.calendar.calendar_sync_cache_support import update_account_sync_status
from features.calendar.calendar_sync_notification_support import (
    notify_calendar_sync_failure,
)

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from core.types.json import JSONDict
    from features.calendar.calendar_caldav_context import (
        PreparedCalendarTransportContext,
    )
    from features.calendar.internal_protocols import CalendarSyncServiceProtocol

__all__ = (
    "handle_calendar_sync_failure",
    "persist_calendar_sync_failure_status",
    "persist_calendar_sync_success_status",
    "read_sync_count",
)


async def persist_calendar_sync_success_status(
    *,
    service: CalendarSyncServiceProtocol,
    user_id: int,
    account_id: str,
    sync_started_at_ms: int,
    logger: LoggerProtocol,
    operation: str,
    warning_log_message: str,
    warning_details: JSONDict,
    warnings: list[str],
) -> None:
    try:
        await update_account_sync_status(
            database_calendar=service.database_calendar,
            user_id=user_id,
            account_id=account_id,
            sync_started_at_ms=sync_started_at_ms,
            error_message=None,
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        log_exception(
            logger,
            exception,
            message=warning_log_message,
            operation=operation,
            level="warning",
            details=warning_details,
        )
        warning_reason = project_public_exception(exception).message
        warnings.append(
            f"Calendar sync completed, but SoAI could not persist the sync metadata: {warning_reason}",
        )


async def persist_calendar_sync_failure_status(
    *,
    service: CalendarSyncServiceProtocol,
    user_id: int,
    account_id: str,
    sync_started_at_ms: int,
    error_message: str,
    logger: LoggerProtocol,
    operation: str,
    warning_log_message: str,
    warning_details: JSONDict,
    original_exception: Exception,
) -> None:
    try:
        await update_account_sync_status(
            database_calendar=service.database_calendar,
            user_id=user_id,
            account_id=account_id,
            sync_started_at_ms=sync_started_at_ms,
            error_message=error_message,
        )
    except RECOVERABLE_EXCEPTIONS as status_exception:
        log_exception(
            logger,
            status_exception,
            message=warning_log_message,
            operation=operation,
            level="warning",
            details=warning_details,
        )
        status_reason = resolve_exception_error_message(status_exception)
        original_exception.add_note(
            f"Also failed to persist the calendar sync failure metadata: {status_reason}",
        )


async def handle_calendar_sync_failure(
    *,
    service: CalendarSyncServiceProtocol,
    user_id: int,
    account_id: str,
    sync_started_at_ms: int,
    logger: LoggerProtocol,
    operation: str,
    warning_log_message: str,
    warning_details: JSONDict,
    prepared: PreparedCalendarTransportContext | None,
    exception: Exception,
) -> None:
    error_message = project_public_exception(exception).message
    previous_error = await _resolve_previous_sync_error(
        service=service,
        user_id=user_id,
        account_id=account_id,
        prepared=prepared,
        logger=logger,
        operation=operation,
    )
    await persist_calendar_sync_failure_status(
        service=service,
        user_id=user_id,
        account_id=account_id,
        sync_started_at_ms=sync_started_at_ms,
        error_message=error_message,
        logger=logger,
        operation=operation,
        warning_log_message=warning_log_message,
        warning_details=warning_details,
        original_exception=exception,
    )
    if previous_error != error_message:
        await notify_calendar_sync_failure(
            database_calendar=service.database_calendar,
            database_notifications=service.database_notifications,
            external_accounts=service.external_accounts,
            user_id=user_id,
            account_id=account_id,
            reason=error_message,
            prepared=prepared,
            original_exception=exception,
        )


def read_sync_count(sync_result: JSONDict, key: str) -> int:
    value = sync_result.get(key)
    if isinstance(value, int):
        return value
    return 0


async def _resolve_previous_sync_error(
    *,
    service: CalendarSyncServiceProtocol,
    user_id: int,
    account_id: str,
    prepared: PreparedCalendarTransportContext | None,
    logger: LoggerProtocol,
    operation: str,
) -> str | None:
    return await resolve_previous_sync_error(
        prepared_account=prepared.runtime_state.account if prepared is not None else None,
        fetch_account=lambda: service.database_calendar.get_account(
            user_id=user_id,
            account_id=account_id,
        ),
        logger=logger,
        operation=operation,
        sync_label="calendar",
        details={"user_id": user_id, "account_id": account_id},
    )
