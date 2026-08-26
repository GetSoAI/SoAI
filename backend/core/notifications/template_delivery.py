"""SoAI - Template notification delivery helpers [backend/core/notifications/template_delivery.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.notifications.notification_contracts import NotificationTemplateId, NotificationType
from core.notifications.notification_text_models import notification_text_from_template

if TYPE_CHECKING:
    from core.notifications.notification_record_models import NotificationLink, NotificationRecord
    from core.notifications.protocols_database import DatabaseNotificationsProtocol

__all__ = ("create_template_notification",)


async def create_template_notification(
    database_notifications: DatabaseNotificationsProtocol,
    *,
    user_id: int,
    notification_type: NotificationType,
    title_template: NotificationTemplateId,
    title_params: dict[str, str] | None,
    message_template: NotificationTemplateId,
    message_params: dict[str, str] | None,
    source: str | None,
    link: NotificationLink | None = None,
    notification_id: str | None = None,
) -> NotificationRecord:
    title = notification_text_from_template(title_template, title_params)
    message = notification_text_from_template(message_template, message_params)
    return await database_notifications.create_notification(
        user_id,
        notification_type,
        title,
        message,
        source=source,
        link=link,
        notification_id=notification_id,
    )
