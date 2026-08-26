"""SoAI - Conversation attention notification delivery policy [backend/core/notifications/conversation_attention_delivery.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.notifications.notification_contracts import NotificationType
from core.notifications.notification_record_models import NotificationLink
from core.tasks.enums import TaskStatus

if TYPE_CHECKING:
    from core.notifications.notification_text_models import (
        NotificationTextPlain,
        NotificationTextTemplate,
    )
    from core.notifications.protocols import ConversationAttentionCoordinatorProtocol
    from core.notifications.protocols_database import DatabaseNotificationsProtocol
    from core.tasks.protocols_registry import TaskRegistryProtocol

__all__ = ("deliver_conversation_attention_notification",)


async def deliver_conversation_attention_notification(
    *,
    attention: ConversationAttentionCoordinatorProtocol,
    task_registry: TaskRegistryProtocol,
    database_notifications: DatabaseNotificationsProtocol,
    user_id: int,
    conversation_id: str,
    interaction_type: str,
    task_id: str,
    notification_id: str,
    title: NotificationTextPlain | NotificationTextTemplate,
    message: NotificationTextPlain | NotificationTextTemplate,
    source: str | None,
    link: NotificationLink,
) -> bool:
    if attention.has_active_conversation_presence(
        user_id=int(user_id),
        conversation_id=conversation_id,
    ):
        return False
    if attention.has_render_ack(
        user_id=int(user_id),
        conversation_id=conversation_id,
        interaction_type=interaction_type,
        task_id=task_id,
        notification_id=notification_id,
    ):
        return False
    task = await task_registry.get(task_id)
    if task is None or task.status != TaskStatus.INPUT_REQUIRED:
        return False
    await database_notifications.create_notification(
        int(user_id),
        NotificationType.WARNING,
        title,
        message,
        source=source,
        link=link,
        notification_id=notification_id,
    )
    refreshed_task = await task_registry.get(task_id)
    if refreshed_task is None or refreshed_task.status != TaskStatus.INPUT_REQUIRED:
        await database_notifications.delete_notification(
            int(user_id),
            notification_id=notification_id,
        )
        return True
    if attention.has_render_ack(
        user_id=int(user_id),
        conversation_id=conversation_id,
        interaction_type=interaction_type,
        task_id=task_id,
        notification_id=notification_id,
    ):
        await database_notifications.delete_notification(
            int(user_id),
            notification_id=notification_id,
        )
        return True
    return True
