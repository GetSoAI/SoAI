"""SoAI - Calendar sync orchestration [backend/features/calendar/calendar_sync.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.logging.trace import get_logger
from core.types.json import JSONDict
from features.calendar.calendar_caldav_client import discover_calendar_account
from features.calendar.calendar_sync_cache_support import (
    sync_service_calendar_window_cache,
    upsert_discovered_calendars,
)
from features.calendar.calendar_sync_execution import (
    CalendarSyncExecutionConfig,
    execute_calendar_sync_operation,
)
from features.calendar.calendar_sync_notification_support import (
    notify_calendar_invite_updates,
)
from features.calendar.calendar_sync_notifications import (
    resolve_calendar_account_label,
)
from features.calendar.calendar_sync_range_support import (
    resolve_default_window,
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

__all__ = ("sync_calendar_account",)

OPERATION = "features.calendar.calendar_sync"
LOGGER_NAME = "SoAI.features.calendar.calendar_sync"


async def sync_calendar_account(
    service: CalendarSyncServiceProtocol,
    *,
    user_id: int,
    account_id: str,
) -> JSONDict:
    if service.runtime_flags.offline_mode:
        raise ValidationError("Calendar sync is unavailable while offline mode is enabled.")
    default_window_start_ms, default_window_end_ms = resolve_default_window(service.config)
    return await execute_calendar_sync_operation(
        service=service,
        user_id=user_id,
        account_id=account_id,
        config=CalendarSyncExecutionConfig(
            logger=get_logger(LOGGER_NAME),
            operation=OPERATION,
            success_warning_log_message="Failed to persist calendar sync metadata after successful sync.",
            failure_warning_log_message="Failed to persist calendar sync failure metadata.",
            warning_details={"user_id": user_id, "account_id": account_id},
        ),
        executor=lambda prepared, sync_started_at_ms: _execute_account_sync(
            service=service,
            user_id=user_id,
            account_id=account_id,
            prepared=prepared,
            sync_started_at_ms=sync_started_at_ms,
            default_window_start_ms=default_window_start_ms,
            default_window_end_ms=default_window_end_ms,
        ),
    )


async def _execute_account_sync(
    *,
    service: CalendarSyncServiceProtocol,
    user_id: int,
    account_id: str,
    prepared: PreparedCalendarTransportContext,
    sync_started_at_ms: int,
    default_window_start_ms: int,
    default_window_end_ms: int,
) -> tuple[JSONDict, list[str]]:
    prior_sync_exists = isinstance(
        prepared.runtime_state.account.get("last_sync_at_ms"),
        int,
    )
    discovery = await discover_calendar_account(
        http_client=service.http_client,
        prepared=prepared,
    )
    await service.database_calendar.update_account(
        user_id=user_id,
        account_id=account_id,
        updates={
            "discovered_principal": {
                "principal_url": discovery.get("principal_url"),
                "calendar_home_url": discovery.get("calendar_home_url"),
            },
        },
    )
    calendars = await upsert_discovered_calendars(
        database_calendar=service.database_calendar,
        user_id=user_id,
        account_id=account_id,
        discovery=discovery,
    )
    warnings: list[str] = []
    imported_events_count = 0
    updated_events_count = 0
    deleted_events_count = 0
    for calendar_row in calendars:
        sync_result = await sync_service_calendar_window_cache(
            service=service,
            prepared=prepared,
            user_id=user_id,
            account_id=account_id,
            calendar_row=calendar_row,
            window_start_ms=default_window_start_ms,
            window_end_ms=default_window_end_ms,
        )
        imported_events_count += read_sync_count(sync_result, "imported_events_count")
        updated_events_count += read_sync_count(sync_result, "updated_events_count")
        deleted_events_count += read_sync_count(sync_result, "deleted_events_count")
        if prior_sync_exists:
            await notify_calendar_invite_updates(
                database_notifications=service.database_notifications,
                user_id=user_id,
                account_label=resolve_calendar_account_label(
                    prepared.runtime_state.account,
                    prepared.runtime_state.external_account,
                ),
                sync_result=sync_result,
            )
        extend_sync_warnings(warnings, sync_result)
    result: JSONDict = {
        "calendars_synced_count": len(calendars),
        "imported_events_count": imported_events_count,
        "updated_events_count": updated_events_count,
        "deleted_events_count": deleted_events_count,
        "synced_window_start_ms": default_window_start_ms,
        "synced_window_end_ms": default_window_end_ms,
        "last_sync_at_ms": sync_started_at_ms,
        "last_sync_error": None,
    }
    return (result, warnings)
