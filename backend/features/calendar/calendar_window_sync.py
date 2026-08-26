"""SoAI - Calendar explicit window sync operations [backend/features/calendar/calendar_window_sync.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.logging.trace import get_logger
from core.types.json import JSONDict
from features.calendar.calendar_record_context import (
    load_calendar_row,
    require_calendar_account_id_from_row,
)
from features.calendar.calendar_sync_cache_support import (
    sync_service_calendar_window_cache,
)
from features.calendar.calendar_sync_execution import (
    CalendarSyncExecutionConfig,
    execute_calendar_sync_operation,
)
from features.calendar.calendar_sync_range_support import (
    validate_window_range,
)
from features.calendar.calendar_sync_status_support import read_sync_count
from features.calendar.calendar_sync_warning_support import (
    extend_sync_warnings,
)

if TYPE_CHECKING:
    from features.calendar.calendar_caldav_context import (
        PreparedCalendarTransportContext,
    )
    from features.calendar.internal_protocols import CalendarSyncServiceProtocol

__all__ = ("sync_calendar_window",)

OPERATION = "features.calendar.calendar_window_sync"
LOGGER_NAME = "SoAI.features.calendar.calendar_window_sync"


async def sync_calendar_window(
    service: CalendarSyncServiceProtocol,
    *,
    user_id: int,
    calendar_id: str,
    window_start_ms: int,
    window_end_ms: int,
) -> JSONDict:
    if service.runtime_flags.offline_mode:
        raise ValidationError("Calendar sync is unavailable while offline mode is enabled.")
    validate_window_range(
        config=service.config,
        window_start_ms=window_start_ms,
        window_end_ms=window_end_ms,
    )
    calendar_row = await load_calendar_row(
        service.database_calendar,
        user_id=user_id,
        calendar_id=calendar_id,
        missing_error=ValidationError,
        missing_message="Calendar not found.",
    )
    account_id = require_calendar_account_id_from_row(calendar_row)
    execution_config = CalendarSyncExecutionConfig(
        logger=get_logger(LOGGER_NAME),
        operation=OPERATION,
        success_warning_log_message="Failed to persist calendar window sync metadata after successful sync.",
        failure_warning_log_message="Failed to persist calendar window sync failure metadata.",
        warning_details={
            "user_id": user_id,
            "account_id": account_id,
            "calendar_id": calendar_id,
        },
    )
    return await execute_calendar_sync_operation(
        service=service,
        user_id=user_id,
        account_id=account_id,
        config=execution_config,
        executor=lambda prepared, sync_started_at_ms: _execute_window_sync(
            service=service,
            prepared=prepared,
            sync_started_at_ms=sync_started_at_ms,
            user_id=user_id,
            account_id=account_id,
            calendar_row=calendar_row,
            window_start_ms=window_start_ms,
            window_end_ms=window_end_ms,
        ),
    )


async def _execute_window_sync(
    *,
    service: CalendarSyncServiceProtocol,
    prepared: PreparedCalendarTransportContext,
    sync_started_at_ms: int,
    user_id: int,
    account_id: str,
    calendar_row: JSONDict,
    window_start_ms: int,
    window_end_ms: int,
) -> tuple[JSONDict, list[str]]:
    _ = sync_started_at_ms
    sync_result = await sync_service_calendar_window_cache(
        service=service,
        prepared=prepared,
        user_id=user_id,
        account_id=account_id,
        calendar_row=calendar_row,
        window_start_ms=window_start_ms,
        window_end_ms=window_end_ms,
    )
    warnings: list[str] = []
    extend_sync_warnings(warnings, sync_result)
    result: JSONDict = {
        "imported_events_count": read_sync_count(sync_result, "imported_events_count"),
        "updated_events_count": read_sync_count(sync_result, "updated_events_count"),
        "deleted_events_count": read_sync_count(sync_result, "deleted_events_count"),
        "synced_window_start_ms": window_start_ms,
        "synced_window_end_ms": window_end_ms,
    }
    return (result, warnings)
