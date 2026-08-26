"""SoAI - User notifications repository [backend/database/repositories/users/notifications.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import StateError, ValidationError
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
from core.timing.epoch import epoch_ms
from database.core.flags import FEATURE_AUTH
from database.repositories.users.domain_event_outbox_dispatch_signal import (
    notify_domain_event_outbox_dispatch_requested,
)
from database.repositories.users.notifications_admin_alert_methods import (
    create_login_throttle_admin_alert_if_due_method,
    create_template_admin_alert_if_due_method,
)
from database.repositories.users.notifications_creation_payloads import (
    build_notification_create_payload,
)
from database.repositories.users.notifications_read_queries import (
    get_notification_counts_query,
    list_notifications_query,
)
from database.repositories.users.notifications_row_normalization import (
    normalize_notification_row,
)
from database.repositories.users.notifications_sync_creation import (
    sync_create_notification,
)
from database.repositories.users.notifications_sync_updates import (
    sync_clear_notifications,
    sync_delete_notification,
    sync_mark_notifications_read,
    sync_open_notification,
)
from database.repositories.users.notifications_value_validation import (
    coerce_notification_count,
    read_max_notifications_per_user,
    require_notification_user_id,
)

if TYPE_CHECKING:
    from database.repositories.dependencies import DatabaseRepositoryDependencies

__all__ = ("DatabaseNotifications",)


class DatabaseNotifications:
    def __init__(self, deps: DatabaseRepositoryDependencies) -> None:
        self._deps = deps
        self.core = deps.core
        self.config = deps.config

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
    ) -> NotificationRecord:
        self.core.features.ensure_feature_enabled(FEATURE_AUTH)
        resolved_user_id = require_notification_user_id(user_id)
        payload = build_notification_create_payload(
            title=title,
            message=message,
            source=source,
            link=link,
            notification_id=notification_id,
        )
        created_at_ms = epoch_ms()
        row = await self.core.writer.queue_write_operation(
            sync_create_notification,
            payload.notification_id,
            resolved_user_id,
            notification_type.value,
            payload.title,
            payload.message,
            payload.source,
            payload.link_json,
            int(created_at_ms),
            read_max_notifications_per_user(self.config),
        )
        if not isinstance(row, tuple) or len(row) != 2:
            raise StateError("Created notification payload is invalid.")
        notification_row = row[0] if isinstance(row[0], dict) else None
        inserted = row[1] if isinstance(row[1], bool) else False
        notification = normalize_notification_row(notification_row)
        if notification is None:
            raise StateError("Created notification payload is invalid.")
        if inserted:
            notify_domain_event_outbox_dispatch_requested(self._deps.event_bus)
        return notification

    async def create_login_throttle_admin_alert_if_due(self) -> int:
        return await create_login_throttle_admin_alert_if_due_method(
            core=self.core,
            config=self.config,
            event_bus=self._deps.event_bus,
        )

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
    ) -> int:
        return await create_template_admin_alert_if_due_method(
            core=self.core,
            config=self.config,
            event_bus=self._deps.event_bus,
            alert_id=alert_id,
            notification_type=notification_type,
            title_template=title_template,
            title_params=title_params,
            message_template=message_template,
            message_params=message_params,
            aggregate_param_name=aggregate_param_name,
            source=source,
            cooldown_seconds=cooldown_seconds,
        )

    async def open_notification(
        self,
        user_id: int,
        *,
        notification_id: str,
        excluded_sources: frozenset[str] = frozenset(),
    ) -> NotificationRecord | None:
        self.core.features.ensure_feature_enabled(FEATURE_AUTH)
        resolved_user_id = require_notification_user_id(user_id)
        normalized_notification_id = str(notification_id or "").strip()
        if not normalized_notification_id:
            raise ValidationError("notification_id is invalid.")
        row = await self.core.writer.queue_write_operation(
            sync_open_notification,
            resolved_user_id,
            normalized_notification_id,
            excluded_sources,
        )
        notification_row = row if isinstance(row, dict) else None
        notification = normalize_notification_row(notification_row)
        if notification is not None:
            notify_domain_event_outbox_dispatch_requested(self._deps.event_bus)
        return notification

    async def list_notifications(
        self,
        user_id: int,
        *,
        limit: int,
        before_created_at_ms: int | None,
        before_id: str | None,
        unread_only: bool,
        excluded_sources: frozenset[str] = frozenset(),
    ) -> NotificationsListPage:
        self.core.features.ensure_feature_enabled(FEATURE_AUTH)
        return await list_notifications_query(
            self.core.reader,
            user_id,
            limit=limit,
            before_created_at_ms=before_created_at_ms,
            before_id=before_id,
            unread_only=unread_only,
            excluded_sources=excluded_sources,
        )

    async def get_notification_counts(
        self,
        user_id: int,
        *,
        excluded_sources: frozenset[str] = frozenset(),
    ) -> tuple[int, int]:
        self.core.features.ensure_feature_enabled(FEATURE_AUTH)
        return await get_notification_counts_query(
            self.core.reader,
            user_id,
            excluded_sources=excluded_sources,
        )

    async def mark_notifications_read(self, user_id: int, *, notification_ids: list[str]) -> int:
        self.core.features.ensure_feature_enabled(FEATURE_AUTH)
        resolved_user_id = require_notification_user_id(user_id)
        normalized_ids: list[str] = []
        seen_ids: set[str] = set()
        for notification_id in notification_ids:
            normalized_id = str(notification_id or "").strip()
            if not normalized_id:
                raise ValidationError("notification_ids contains an invalid notification id.")
            if normalized_id in seen_ids:
                continue
            seen_ids.add(normalized_id)
            normalized_ids.append(normalized_id)
        if not normalized_ids:
            raise ValidationError("notification_ids must contain at least one notification id.")
        updated = await self.core.writer.queue_write_operation(
            sync_mark_notifications_read,
            resolved_user_id,
            normalized_ids,
        )
        updated_count = coerce_notification_count(updated)
        if updated_count > 0:
            notify_domain_event_outbox_dispatch_requested(self._deps.event_bus)
        return updated_count

    async def delete_notification(self, user_id: int, *, notification_id: str) -> bool:
        self.core.features.ensure_feature_enabled(FEATURE_AUTH)
        resolved_user_id = require_notification_user_id(user_id)
        normalized_notification_id = str(notification_id or "").strip()
        if not normalized_notification_id:
            raise ValidationError("notification_id is invalid.")
        deleted = await self.core.writer.queue_write_operation(
            sync_delete_notification,
            resolved_user_id,
            normalized_notification_id,
        )
        if deleted is True:
            notify_domain_event_outbox_dispatch_requested(self._deps.event_bus)
            return True
        return False

    async def clear_notifications(self, user_id: int) -> int:
        self.core.features.ensure_feature_enabled(FEATURE_AUTH)
        resolved_user_id = require_notification_user_id(user_id)
        deleted = await self.core.writer.queue_write_operation(
            sync_clear_notifications,
            resolved_user_id,
        )
        deleted_count = coerce_notification_count(deleted)
        if deleted_count > 0:
            notify_domain_event_outbox_dispatch_requested(self._deps.event_bus)
        return deleted_count
