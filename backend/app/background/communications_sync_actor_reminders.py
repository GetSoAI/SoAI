"""SoAI - Communications sync actor reminder delivery [backend/app/background/communications_sync_actor_reminders.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from app.background.communications_sync_actor_support import (
    build_calendar_account_labels,
    extract_accounts,
    notify_resource_updated,
)
from core.errors.exception_logging import log_exception
from core.errors.exceptions import StateError
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.timing.epoch import epoch_ms
from database.core.sqlite_errors import parse_sqlite_integrity_error
from features.calendar.calendar_sync_notifications import (
    create_calendar_reminder_due_notification,
    create_calendar_reminder_missed_notification,
    resolve_calendar_event_start,
    resolve_calendar_event_summary,
)
from mcp.calendar.resource_uris import (
    CALENDAR_RESOURCE_URI,
    build_calendar_event_resource_uri,
)

if TYPE_CHECKING:
    from core.calendar.protocols import DatabaseCalendarProtocol
    from core.external_accounts.protocols import LinkedAccountQueryProtocol
    from core.logging.protocols import LoggerProtocol
    from core.mcp.protocols_main import MCPServerProtocol
    from core.notifications.protocols_database import DatabaseNotificationsProtocol
    from core.types.json import JSONValue

__all__ = ("run_calendar_reminder_iteration",)

OPERATION = "app.background.communications_sync_actor.run"
REMINDER_RECOVERABLE_EXCEPTIONS: tuple[type[Exception], ...] = (
    *RECOVERABLE_EXCEPTIONS,
    sqlite3.Error,
)


async def run_calendar_reminder_iteration(
    *,
    database_calendar: DatabaseCalendarProtocol,
    database_notifications: DatabaseNotificationsProtocol,
    account_queries: LinkedAccountQueryProtocol,
    logger: LoggerProtocol,
    mcp_server: MCPServerProtocol | None,
) -> None:
    delivered_event_ids: list[str] = []
    now_ms = epoch_ms()
    account_labels_by_user: dict[int, dict[str, str]] = {}
    skipped_user_ids: set[int] = set()
    reminders = await database_calendar.list_due_reminders(due_at_ms=now_ms)
    for reminder in reminders:
        reminder_id = reminder.get("id")
        user_id = reminder.get("user_id")
        event_id = reminder.get("event_id")
        account_id = reminder.get("calendar_account_id")
        if (
            not isinstance(reminder_id, str)
            or not isinstance(user_id, int)
            or not isinstance(event_id, str)
        ):
            log_exception(
                logger,
                StateError("Calendar reminder row is invalid."),
                message="Calendar reminder delivery skipped invalid reminder row.",
                operation=OPERATION,
                level="warning",
                details={
                    "reminder_id": (reminder_id if isinstance(reminder_id, str) else None),
                    "user_id": user_id if isinstance(user_id, int) else None,
                    "event_id": event_id if isinstance(event_id, str) else None,
                },
            )
            continue
        if user_id in skipped_user_ids:
            continue
        account_labels = account_labels_by_user.get(user_id)
        if account_labels is None:
            try:
                account_labels = build_calendar_account_labels(
                    extract_accounts(await account_queries.list_accounts(user_id)),
                )
            except RECOVERABLE_EXCEPTIONS as exception:
                skipped_user_ids.add(user_id)
                log_exception(
                    logger,
                    exception,
                    message="Calendar reminder delivery skipped user account listing.",
                    operation=OPERATION,
                    level="warning",
                    details={"user_id": user_id},
                )
                continue
            account_labels_by_user[user_id] = account_labels
        try:
            event = await database_calendar.get_event(user_id=user_id, event_id=event_id)
            if event is None:
                await database_calendar.mark_reminder_delivered(
                    reminder_id=reminder_id,
                    delivered_at_ms=now_ms,
                )
                continue
            if not isinstance(account_id, str) or not account_id.strip():
                raise StateError("Calendar reminder account_id is invalid.")
            account_label = account_labels.get(account_id.strip())
            if not isinstance(account_label, str) or not account_label.strip():
                raise StateError("Calendar reminder account label is unavailable.")
            summary = resolve_calendar_event_summary(event)
            start = resolve_calendar_event_start(event)
            due_at_ms = reminder.get("due_at_ms")
            await _create_calendar_reminder_notification(
                database_notifications=database_notifications,
                reminder_id=reminder_id,
                user_id=user_id,
                account_label=account_label,
                summary=summary,
                start=start,
                due_at_ms=due_at_ms,
                now_ms=now_ms,
            )
            if await database_calendar.mark_reminder_delivered(
                reminder_id=reminder_id,
                delivered_at_ms=now_ms,
            ):
                delivered_event_ids.append(event_id)
        except REMINDER_RECOVERABLE_EXCEPTIONS as exception:
            _log_reminder_failure(
                logger=logger,
                reminder_id=reminder_id,
                user_id=user_id,
                event_id=event_id,
                exception=exception,
            )
    if delivered_event_ids:
        await notify_resource_updated(logger=logger, server=mcp_server, uri=CALENDAR_RESOURCE_URI)
        for event_id in delivered_event_ids:
            await notify_resource_updated(
                logger=logger,
                server=mcp_server,
                uri=build_calendar_event_resource_uri(event_id),
            )


def _log_reminder_failure(
    *,
    logger: LoggerProtocol,
    reminder_id: str,
    user_id: int,
    event_id: str,
    exception: Exception,
) -> None:
    log_exception(
        logger,
        exception,
        message="Calendar reminder delivery failed.",
        operation=OPERATION,
        level="warning",
        details={"reminder_id": reminder_id, "user_id": user_id, "event_id": event_id},
    )


async def _create_calendar_reminder_notification(
    *,
    database_notifications: DatabaseNotificationsProtocol,
    reminder_id: str,
    user_id: int,
    account_label: str,
    summary: str,
    start: str,
    due_at_ms: JSONValue,
    now_ms: int,
) -> None:
    notification_id = _build_calendar_reminder_notification_id(reminder_id=reminder_id)
    try:
        if isinstance(due_at_ms, int) and now_ms >= due_at_ms:
            await create_calendar_reminder_missed_notification(
                database_notifications=database_notifications,
                user_id=user_id,
                account_label=account_label,
                summary=summary,
                start=start,
                notification_id=notification_id,
            )
            return
        await create_calendar_reminder_due_notification(
            database_notifications=database_notifications,
            user_id=user_id,
            account_label=account_label,
            summary=summary,
            start=start,
            notification_id=notification_id,
        )
    except sqlite3.IntegrityError as exception:
        constraint_type, detail = parse_sqlite_integrity_error(exception)
        if constraint_type == "primary_key" or (
            constraint_type == "unique" and detail == "webui_notifications.id"
        ):
            return
        raise


def _build_calendar_reminder_notification_id(
    *,
    reminder_id: str,
) -> str:
    return f"notif_{reminder_id}"
