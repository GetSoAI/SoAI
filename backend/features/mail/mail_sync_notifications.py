"""SoAI - Mail sync notification helpers [backend/features/mail/mail_sync_notifications.py]"""
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
from features.external_accounts.notification_links import (
    build_external_accounts_settings_link,
)

if TYPE_CHECKING:
    from core.notifications.protocols_database import DatabaseNotificationsProtocol
    from core.types.json import JSONDict

__all__ = (
    "create_mail_new_message_notification",
    "create_mail_sync_failure_notification",
    "resolve_mail_account_label",
    "resolve_mail_sender_label",
    "resolve_mail_subject",
)


async def create_mail_sync_failure_notification(
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
        title_template=NotificationTemplateId.MAIL_SYNC_FAILURE_TITLE,
        title_params={"accountLabel": account_label},
        message_template=NotificationTemplateId.MAIL_SYNC_FAILURE_MESSAGE,
        message_params={"reason": reason},
        source="mail",
        link=build_external_accounts_settings_link(),
    )


async def create_mail_new_message_notification(
    *,
    database_notifications: DatabaseNotificationsProtocol,
    user_id: int,
    account_label: str,
    from_label: str,
    subject: str,
) -> None:
    await create_template_notification(
        database_notifications,
        user_id=user_id,
        notification_type=NotificationType.INFO,
        title_template=NotificationTemplateId.MAIL_NEW_TITLE,
        title_params={"accountLabel": account_label},
        message_template=NotificationTemplateId.MAIL_NEW_MESSAGE,
        message_params={"from": from_label, "subject": subject},
        source="mail",
        link=build_external_accounts_settings_link(),
    )


def resolve_mail_account_label(account: JSONDict, external_account: JSONDict) -> str:
    return resolve_external_account_display_label(
        account,
        external_account,
        unavailable_message="Mail account label is unavailable.",
    )


def resolve_mail_sender_label(message: JSONDict) -> str:
    from_value = message.get("from")
    if not isinstance(from_value, list) or not from_value:
        raise StateError("Mail message sender is unavailable.")
    first = from_value[0]
    if not isinstance(first, dict):
        raise StateError("Mail message sender is invalid.")
    name_value = first.get("name")
    if isinstance(name_value, str) and name_value.strip():
        return name_value.strip()
    email_value = first.get("email")
    if isinstance(email_value, str) and email_value.strip():
        return email_value.strip()
    raise StateError("Mail message sender is unavailable.")


def resolve_mail_subject(message: JSONDict) -> str:
    subject_value = message.get("subject")
    if isinstance(subject_value, str) and subject_value.strip():
        return subject_value.strip()
    raise StateError("Mail message subject is unavailable.")
