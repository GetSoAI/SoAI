"""SoAI - Calendar notification helpers [backend/features/calendar/calendar_sync_notifications.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.external_accounts.account_labels import resolve_external_account_display_label
from core.notifications.notification_contracts import (
    NotificationTemplateId,
    NotificationType,
)
from core.notifications.template_delivery import create_template_notification
from core.timing.formatting import timestamp_ms_to_utc_datetime
from core.validation.integers import is_strict_int
from features.external_accounts.notification_links import (
    build_external_accounts_settings_link,
)

if TYPE_CHECKING:
    from core.notifications.protocols_database import DatabaseNotificationsProtocol
    from core.types.json import JSONDict

__all__ = (
    "create_calendar_invite_update_notification",
    "create_calendar_reminder_due_notification",
    "create_calendar_reminder_missed_notification",
    "create_calendar_sync_failure_notification",
    "resolve_calendar_account_label",
    "resolve_calendar_event_start",
    "resolve_calendar_event_summary",
)


async def create_calendar_sync_failure_notification(
    *,
    database_notifications: DatabaseNotificationsProtocol,
    user_id: int,
    account_label: str,
    reason: str,
) -> None:
    await create_template_notification(
        database_notifications,
        user_id=user_id,
        notification_type=NotificationType.ERROR,
        title_template=NotificationTemplateId.CALENDAR_SYNC_FAILURE_TITLE,
        title_params={"accountLabel": account_label},
        message_template=NotificationTemplateId.CALENDAR_SYNC_FAILURE_MESSAGE,
        message_params={"reason": reason},
        source="calendar",
        link=build_external_accounts_settings_link(),
    )


async def create_calendar_invite_update_notification(
    *,
    database_notifications: DatabaseNotificationsProtocol,
    user_id: int,
    account_label: str,
    summary: str,
    start: str,
) -> None:
    await create_template_notification(
        database_notifications,
        user_id=user_id,
        notification_type=NotificationType.INFO,
        title_template=NotificationTemplateId.CALENDAR_INVITE_UPDATE_TITLE,
        title_params={"accountLabel": account_label},
        message_template=NotificationTemplateId.CALENDAR_INVITE_UPDATE_MESSAGE,
        message_params={"summary": summary, "start": start},
        source="calendar",
        link=build_external_accounts_settings_link(),
    )


async def create_calendar_reminder_due_notification(
    *,
    database_notifications: DatabaseNotificationsProtocol,
    user_id: int,
    account_label: str,
    summary: str,
    start: str,
    notification_id: str | None = None,
) -> None:
    await create_template_notification(
        database_notifications,
        user_id=user_id,
        notification_type=NotificationType.INFO,
        title_template=NotificationTemplateId.CALENDAR_REMINDER_DUE_TITLE,
        title_params={"accountLabel": account_label},
        message_template=NotificationTemplateId.CALENDAR_REMINDER_DUE_MESSAGE,
        message_params={"summary": summary, "start": start},
        source="calendar",
        link=build_external_accounts_settings_link(),
        notification_id=notification_id,
    )


async def create_calendar_reminder_missed_notification(
    *,
    database_notifications: DatabaseNotificationsProtocol,
    user_id: int,
    account_label: str,
    summary: str,
    start: str,
    notification_id: str | None = None,
) -> None:
    await create_template_notification(
        database_notifications,
        user_id=user_id,
        notification_type=NotificationType.WARNING,
        title_template=NotificationTemplateId.CALENDAR_REMINDER_MISSED_TITLE,
        title_params={"accountLabel": account_label},
        message_template=NotificationTemplateId.CALENDAR_REMINDER_MISSED_MESSAGE,
        message_params={"summary": summary, "start": start},
        source="calendar",
        link=build_external_accounts_settings_link(),
        notification_id=notification_id,
    )


def resolve_calendar_account_label(account: JSONDict, external_account: JSONDict) -> str:
    return resolve_external_account_display_label(
        account,
        external_account,
        unavailable_message="Calendar account label is unavailable.",
    )


def resolve_calendar_event_summary(event: JSONDict) -> str:
    summary_value = event.get("summary")
    if isinstance(summary_value, str) and summary_value.strip():
        return summary_value.strip()
    raise StateError("Calendar event summary is unavailable.")


def resolve_calendar_event_start(event: JSONDict) -> str:
    start_value = event.get("start_at_ms")
    if not is_strict_int(start_value):
        raise StateError("Calendar event start is unavailable.")
    return timestamp_ms_to_utc_datetime(start_value).isoformat()
