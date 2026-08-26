"""SoAI - WebUI database notification protocol definitions [backend/core/notifications/protocols_database.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import Protocol

from core.notifications.notification_contracts import NotificationTemplateId, NotificationType
from core.notifications.notification_record_models import (
    NotificationLink,
    NotificationRecord,
    NotificationsListPage,
)
from core.notifications.notification_text_models import (
    NotificationTextPlain,
    NotificationTextTemplate,
)

__all__ = ("DatabaseNotificationsProtocol",)


class DatabaseNotificationsProtocol(Protocol):
    async def create_notification(
        self,
        user_id: int,
        notification_type: NotificationType,
        title: NotificationTextPlain | NotificationTextTemplate,
        message: NotificationTextPlain | NotificationTextTemplate,
        *,
        source: str | None = None,
        link: NotificationLink | None = None,
        notification_id: str | None = None,
    ) -> NotificationRecord: ...

    async def create_login_throttle_admin_alert_if_due(self) -> int: ...

    async def create_template_admin_alert_if_due(
        self,
        *,
        alert_id: str,
        notification_type: NotificationType,
        title_template: NotificationTemplateId,
        title_params: dict[str, str],
        message_template: NotificationTemplateId,
        message_params: dict[str, str],
        aggregate_param_name: str | None,
        source: str | None,
        cooldown_seconds: int,
    ) -> int: ...

    async def open_notification(
        self,
        user_id: int,
        *,
        notification_id: str,
        excluded_sources: frozenset[str] = frozenset(),
    ) -> NotificationRecord | None: ...

    async def list_notifications(
        self,
        user_id: int,
        *,
        limit: int,
        before_created_at_ms: int | None,
        before_id: str | None,
        unread_only: bool,
        excluded_sources: frozenset[str] = frozenset(),
    ) -> NotificationsListPage: ...

    async def get_notification_counts(
        self,
        user_id: int,
        *,
        excluded_sources: frozenset[str] = frozenset(),
    ) -> tuple[int, int]: ...

    async def mark_notifications_read(
        self,
        user_id: int,
        *,
        notification_ids: list[str],
    ) -> int: ...

    async def delete_notification(self, user_id: int, *, notification_id: str) -> bool: ...

    async def clear_notifications(self, user_id: int) -> int: ...
