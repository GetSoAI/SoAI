"""SoAI - DatabaseNotifications admin alert async methods [backend/database/repositories/users/notifications_admin_alert_methods.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.config.clamped_numeric import read_config_nonnegative_int
from core.notifications.notification_contracts import NotificationTemplateId, NotificationType
from core.timing.epoch import epoch_ms
from database.core.flags import FEATURE_AUTH
from database.repositories.users.domain_event_outbox_dispatch_signal import (
    notify_domain_event_outbox_dispatch_requested,
)
from database.repositories.users.notification_admin_alerts import (
    sync_create_template_admin_alert_if_due,
)
from database.repositories.users.notifications_value_validation import (
    coerce_notification_count,
    read_max_notifications_per_user,
)
from database.repositories.users.security_login_notifications import (
    sync_create_login_throttle_admin_alert_if_due,
)

if TYPE_CHECKING:
    from core.config.protocols import ConfigProtocol
    from core.database.protocols import DatabaseCoreProtocol
    from core.events.protocols import EventBusProtocol

__all__ = (
    "create_login_throttle_admin_alert_if_due_method",
    "create_template_admin_alert_if_due_method",
)

MS_PER_SECOND = 1000


async def create_login_throttle_admin_alert_if_due_method(
    *,
    core: DatabaseCoreProtocol,
    config: ConfigProtocol,
    event_bus: EventBusProtocol | None,
) -> int:
    core.features.ensure_feature_enabled(FEATURE_AUTH)
    alerts_enabled = config.get(
        "SERVER.WEBUI.LOGIN_SECURITY.ADMIN_ALERTS.ENABLED",
        True,
    )
    if alerts_enabled is False:
        return 0
    cooldown_seconds = read_config_nonnegative_int(
        config,
        "SERVER.WEBUI.LOGIN_SECURITY.ADMIN_ALERTS.COOLDOWN_SECONDS",
        900,
    )
    created_count = await core.writer.queue_write_operation(
        sync_create_login_throttle_admin_alert_if_due,
        int(epoch_ms()),
        max(int(cooldown_seconds), 1) * MS_PER_SECOND,
        read_max_notifications_per_user(config),
    )
    notification_count = coerce_notification_count(created_count)
    if notification_count > 0:
        notify_domain_event_outbox_dispatch_requested(event_bus)
    return notification_count


async def create_template_admin_alert_if_due_method(
    *,
    core: DatabaseCoreProtocol,
    config: ConfigProtocol,
    event_bus: EventBusProtocol | None,
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
    core.features.ensure_feature_enabled(FEATURE_AUTH)
    created_count = await core.writer.queue_write_operation(
        sync_create_template_admin_alert_if_due,
        alert_id,
        notification_type.value,
        title_template.value,
        title_params,
        message_template.value,
        message_params,
        aggregate_param_name,
        source,
        int(epoch_ms()),
        max(int(cooldown_seconds), 1) * MS_PER_SECOND,
        read_max_notifications_per_user(config),
    )
    notification_count = coerce_notification_count(created_count)
    if notification_count > 0:
        notify_domain_event_outbox_dispatch_requested(event_bus)
    return notification_count
