"""SoAI - Calendar sync notification support [backend/features/calendar/calendar_sync_notification_support.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from core.errors.exception_logging import log_exception
from core.errors.messages import resolve_exception_error_message
from core.errors.public_projection import project_public_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.validation.strings import coerce_trimmed_str_or_empty
from features.calendar.calendar_sync_notifications import (
    create_calendar_invite_update_notification,
    create_calendar_sync_failure_notification,
    resolve_calendar_account_label,
    resolve_calendar_event_start,
    resolve_calendar_event_summary,
)
from features.calendar.calendar_sync_warning_support import append_sync_warning

if TYPE_CHECKING:
    from core.calendar.protocols import DatabaseCalendarProtocol
    from core.external_accounts.protocols import ExternalAccountsServiceProtocol
    from core.notifications.protocols_database import DatabaseNotificationsProtocol
    from core.types.json import JSONDict
    from features.calendar.calendar_caldav_context import (
        PreparedCalendarTransportContext,
    )

__all__ = (
    "notify_calendar_invite_updates",
    "notify_calendar_sync_failure",
)

OPERATION = "features.calendar.calendar_sync_notification_support"
LOGGER_NAME = "SoAI.features.calendar.calendar_sync_notification_support"


async def notify_calendar_sync_failure(
    *,
    database_calendar: DatabaseCalendarProtocol,
    database_notifications: DatabaseNotificationsProtocol,
    external_accounts: ExternalAccountsServiceProtocol,
    user_id: int,
    account_id: str,
    reason: str,
    prepared: PreparedCalendarTransportContext | None,
    original_exception: Exception,
) -> None:
    account = (
        prepared.runtime_state.account
        if prepared is not None
        else await database_calendar.get_account(user_id=user_id, account_id=account_id)
    )
    if account is None:
        return
    external_account = prepared.runtime_state.external_account if prepared is not None else None
    if external_account is None:
        external_account = await _load_external_account(
            external_accounts=external_accounts,
            user_id=user_id,
            account=account,
        )
    try:
        await create_calendar_sync_failure_notification(
            database_notifications=database_notifications,
            user_id=user_id,
            account_label=resolve_calendar_account_label(account, external_account or {}),
            reason=reason,
        )
    except RECOVERABLE_EXCEPTIONS as notification_exception:
        log_exception(
            _calendar_sync_support_logger(),
            notification_exception,
            message="Failed to create calendar sync failure notification.",
            operation=OPERATION,
            level="warning",
            details={"user_id": user_id, "account_id": account_id},
        )
        notification_reason = resolve_exception_error_message(notification_exception)
        original_exception.add_note(
            f"Also failed to create the calendar sync failure notification: {notification_reason}",
        )


async def notify_calendar_invite_updates(
    *,
    database_notifications: DatabaseNotificationsProtocol,
    user_id: int,
    account_label: str,
    sync_result: JSONDict,
) -> None:
    for key in ("imported_events", "updated_events"):
        events_value = sync_result.get(key)
        events = events_value if isinstance(events_value, list) else []
        for event in events:
            if not isinstance(event, dict):
                continue
            attendee_count = event.get("attendee_count")
            if not isinstance(attendee_count, int) or attendee_count < 1:
                continue
            try:
                await create_calendar_invite_update_notification(
                    database_notifications=database_notifications,
                    user_id=user_id,
                    account_label=account_label,
                    summary=resolve_calendar_event_summary(event),
                    start=resolve_calendar_event_start(event),
                )
            except RECOVERABLE_EXCEPTIONS as exception:
                log_exception(
                    _calendar_sync_support_logger(),
                    exception,
                    message="Failed to create calendar invite update notification during sync.",
                    operation=OPERATION,
                    level="warning",
                    details={"user_id": user_id},
                )
                warning_reason = project_public_exception(exception).message
                append_sync_warning(
                    sync_result,
                    f"Calendar sync imported or updated an invite event, but SoAI could not create its notification: {warning_reason}",
                )


async def _load_external_account(
    *,
    external_accounts: ExternalAccountsServiceProtocol,
    user_id: int,
    account: JSONDict,
) -> JSONDict | None:
    external_account_id_value = account.get("external_account_id")
    external_account_id = coerce_trimmed_str_or_empty(external_account_id_value)
    if not external_account_id:
        return None
    return await external_accounts.get_account(
        user_id,
        external_account_id,
        decrypt_secrets=False,
    )


def _calendar_sync_support_logger() -> logging.Logger:
    return get_logger(LOGGER_NAME)
