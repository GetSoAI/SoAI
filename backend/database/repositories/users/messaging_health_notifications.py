"""SoAI - Messaging account health notification persistence [backend/database/repositories/users/messaging_health_notifications.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from core.errors.exceptions import StateError
from core.messaging.account_validation import (
    require_messaging_account_fence,
    require_messaging_account_label,
)
from core.notifications.notification_contracts import (
    MESSAGING_ACCOUNT_HEALTH_NOTIFICATION_SOURCE,
    NotificationLinkType,
    NotificationTemplateId,
    NotificationType,
)
from core.notifications.notification_record_models import NotificationLink
from core.notifications.notification_text_models import notification_text_from_template
from database.repositories.users.notifications_creation_payloads import (
    build_notification_create_payload,
)
from database.repositories.users.notifications_sync_creation import (
    sync_create_notification,
)

if TYPE_CHECKING:
    from core.conversations.conversation_source import MessagingPlatform
    from core.types.json import JSONDict

__all__ = ("sync_create_messaging_health_notification",)


def _provider_label(platform: MessagingPlatform) -> str:
    if platform == "whatsapp":
        return "WhatsApp"
    if platform == "telegram":
        return "Telegram"
    return "Discord"


def sync_create_messaging_health_notification(
    conn: sqlite3.Connection,
    *,
    account: JSONDict,
    recovered: bool,
    created_at_ms: int,
    max_per_user: int,
) -> bool:
    account_fence = require_messaging_account_fence(account)
    account_label_value = account.get("label")
    if not isinstance(account_label_value, str):
        raise StateError("Messaging account health notification label is invalid.")
    account_label = require_messaging_account_label(account_label_value)
    provider_label = _provider_label(account_fence.platform)
    title_template = (
        NotificationTemplateId.MESSAGING_ACCOUNT_RECOVERED_TITLE
        if recovered
        else NotificationTemplateId.MESSAGING_ACCOUNT_DEGRADED_TITLE
    )
    message_template = (
        NotificationTemplateId.MESSAGING_ACCOUNT_RECOVERED_MESSAGE
        if recovered
        else NotificationTemplateId.MESSAGING_ACCOUNT_DEGRADED_MESSAGE
    )
    payload = build_notification_create_payload(
        title=notification_text_from_template(title_template),
        message=notification_text_from_template(
            message_template,
            {
                "accountLabel": account_label,
                "providerLabel": provider_label,
            },
        ),
        source=MESSAGING_ACCOUNT_HEALTH_NOTIFICATION_SOURCE,
        link=NotificationLink(
            link_type=NotificationLinkType.URL,
            value="settings?tab=messaging",
        ),
        notification_id=None,
    )
    _, inserted = sync_create_notification(
        conn,
        payload.notification_id,
        account_fence.user_id,
        (NotificationType.SUCCESS.value if recovered else NotificationType.ERROR.value),
        payload.title,
        payload.message,
        payload.source,
        payload.link_json,
        created_at_ms,
        max_per_user,
    )
    if not inserted:
        raise StateError("Messaging account health notification id collided.")
    return True
