"""SoAI - System admin notification alert builders [backend/core/notifications/system_admin_alerts.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors.exceptions import InsufficientDiskSpaceError
from core.formatting.bytes import format_bytes
from core.notifications.admin_alert_identity import (
    build_admin_alert_id,
    normalize_admin_alert_label,
)
from core.notifications.notification_contracts import (
    API_RATE_LIMIT_NOTIFICATION_SOURCE,
    BACKUP_NOTIFICATION_SOURCE,
    LOW_DISK_SPACE_NOTIFICATION_SOURCE,
    OPENAI_QUOTA_NOTIFICATION_SOURCE,
    NotificationTemplateId,
    NotificationType,
)

if TYPE_CHECKING:
    from core.notifications.protocols_database import DatabaseNotificationsProtocol

__all__ = (
    "create_api_rate_limit_admin_alert",
    "create_backup_failure_admin_alert",
    "create_low_disk_space_admin_alert",
    "create_openai_quota_admin_alert",
)

DEFAULT_ADMIN_ALERT_COOLDOWN_SECONDS = 900


async def create_backup_failure_admin_alert(
    database_notifications: DatabaseNotificationsProtocol,
    *,
    operation_label: str,
) -> int:
    label = normalize_admin_alert_label(operation_label, "Backup operation")
    return await database_notifications.create_template_admin_alert_if_due(
        alert_id=build_admin_alert_id("backup.failure", (label,)),
        notification_type=NotificationType.ERROR,
        title_template=NotificationTemplateId.BACKUP_OPERATION_FAILED_TITLE,
        title_params={"operationLabel": label},
        message_template=NotificationTemplateId.BACKUP_OPERATION_FAILED_MESSAGE,
        message_params={"operationLabel": label},
        aggregate_param_name="failureCount",
        source=BACKUP_NOTIFICATION_SOURCE,
        cooldown_seconds=DEFAULT_ADMIN_ALERT_COOLDOWN_SECONDS,
    )


async def create_low_disk_space_admin_alert(
    database_notifications: DatabaseNotificationsProtocol,
    *,
    exception: InsufficientDiskSpaceError,
    fallback_operation_label: str,
) -> int:
    details = exception.details if isinstance(exception.details, dict) else {}
    operation_value = details.get("operation")
    operation_label = (
        operation_value if isinstance(operation_value, str) else fallback_operation_label
    )
    label = normalize_admin_alert_label(operation_label, "Disk space operation")
    deficit_value = details.get("deficit_bytes")
    deficit = format_bytes(deficit_value) if isinstance(deficit_value, int) else "unknown"
    path_value = details.get("disk_usage_path")
    if not isinstance(path_value, str) or not path_value.strip():
        path_value = (
            details.get("check_path") if isinstance(details.get("check_path"), str) else label
        )
    return await database_notifications.create_template_admin_alert_if_due(
        alert_id=build_admin_alert_id("storage.low_disk", (label, str(path_value))),
        notification_type=NotificationType.ERROR,
        title_template=NotificationTemplateId.LOW_DISK_SPACE_TITLE,
        title_params={"operationLabel": label},
        message_template=NotificationTemplateId.LOW_DISK_SPACE_MESSAGE,
        message_params={"operationLabel": label, "deficit": deficit},
        aggregate_param_name=None,
        source=LOW_DISK_SPACE_NOTIFICATION_SOURCE,
        cooldown_seconds=DEFAULT_ADMIN_ALERT_COOLDOWN_SECONDS,
    )


async def create_api_rate_limit_admin_alert(
    database_notifications: DatabaseNotificationsProtocol,
    *,
    client_key: str,
    scope_key: str,
    rule_label: str,
) -> int:
    scope_label = normalize_admin_alert_label(scope_key, "API route")
    return await database_notifications.create_template_admin_alert_if_due(
        alert_id=build_admin_alert_id("api.rate_limit", (client_key, scope_key, rule_label)),
        notification_type=NotificationType.WARNING,
        title_template=NotificationTemplateId.API_RATE_LIMIT_APPLIED_TITLE,
        title_params={"scopeLabel": scope_label},
        message_template=NotificationTemplateId.API_RATE_LIMIT_APPLIED_MESSAGE,
        message_params={"scopeLabel": scope_label},
        aggregate_param_name="failureCount",
        source=API_RATE_LIMIT_NOTIFICATION_SOURCE,
        cooldown_seconds=DEFAULT_ADMIN_ALERT_COOLDOWN_SECONDS,
    )


async def create_openai_quota_admin_alert(
    database_notifications: DatabaseNotificationsProtocol,
    *,
    key_id: str,
    key_label: str,
    window_label: str,
) -> int:
    resolved_key_label = normalize_admin_alert_label(key_label, "OpenAI API key")
    resolved_window_label = normalize_admin_alert_label(window_label, "quota")
    return await database_notifications.create_template_admin_alert_if_due(
        alert_id=build_admin_alert_id("openai.quota", (key_id, resolved_window_label)),
        notification_type=NotificationType.WARNING,
        title_template=NotificationTemplateId.OPENAI_QUOTA_EXHAUSTED_TITLE,
        title_params={"keyLabel": resolved_key_label},
        message_template=NotificationTemplateId.OPENAI_QUOTA_EXHAUSTED_MESSAGE,
        message_params={
            "keyLabel": resolved_key_label,
            "windowLabel": resolved_window_label,
        },
        aggregate_param_name=None,
        source=OPENAI_QUOTA_NOTIFICATION_SOURCE,
        cooldown_seconds=DEFAULT_ADMIN_ALERT_COOLDOWN_SECONDS,
    )
