"""SoAI - WebUI notification contract enums and SQL constants [backend/core/notifications/notification_contracts.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from enum import Enum

from core.errors.exceptions import StateError

__all__ = (
    "API_RATE_LIMIT_NOTIFICATION_SOURCE",
    "BACKUP_NOTIFICATION_SOURCE",
    "LOW_DISK_SPACE_NOTIFICATION_SOURCE",
    "MESSAGING_ACCOUNT_HEALTH_NOTIFICATION_SOURCE",
    "NOTIFICATION_TEMPLATE_SQL_VALUES",
    "NOTIFICATION_TEXT_TYPE_SQL_VALUES",
    "NOTIFICATION_TYPE_SQL_VALUES",
    "OPENAI_QUOTA_NOTIFICATION_SOURCE",
    "PLUGIN_CIRCUIT_BREAKER_NOTIFICATION_SOURCE",
    "SECURITY_LOGIN_NOTIFICATION_SOURCE",
    "NotificationLinkType",
    "NotificationTemplateId",
    "NotificationType",
    "resolve_notification_template_required_params",
    "validate_notifications_sql_contract",
)

NOTIFICATION_TEXT_TYPE_SQL_VALUES: tuple[str, ...] = ("text", "template")
NOTIFICATION_TYPE_SQL_VALUES: tuple[str, ...] = ("info", "success", "warning", "error")
PLUGIN_CIRCUIT_BREAKER_NOTIFICATION_SOURCE = "plugins.circuit_breaker"
SECURITY_LOGIN_NOTIFICATION_SOURCE = "security.login"
BACKUP_NOTIFICATION_SOURCE = "backup"
LOW_DISK_SPACE_NOTIFICATION_SOURCE = "storage.low_disk"
MESSAGING_ACCOUNT_HEALTH_NOTIFICATION_SOURCE = "messaging.account_health"
API_RATE_LIMIT_NOTIFICATION_SOURCE = "api.rate_limit"
OPENAI_QUOTA_NOTIFICATION_SOURCE = "openai.quota"

NOTIFICATION_TEMPLATE_SQL_VALUES: tuple[str, ...] = (
    "api_rate_limit_applied_message",
    "api_rate_limit_applied_title",
    "ask_user_required_message",
    "ask_user_required_title",
    "automation_completed_message",
    "automation_completed_message_generic",
    "automation_completed_title",
    "automation_failed_message",
    "automation_failed_message_generic",
    "automation_failed_message_with_status",
    "automation_failed_message_with_status_generic",
    "automation_failed_title",
    "backup_operation_failed_message",
    "backup_operation_failed_title",
    "calendar_invite_update_message",
    "calendar_invite_update_title",
    "calendar_reminder_due_message",
    "calendar_reminder_due_title",
    "calendar_reminder_missed_message",
    "calendar_reminder_missed_title",
    "calendar_sync_failure_message",
    "calendar_sync_failure_title",
    "low_disk_space_message",
    "low_disk_space_title",
    "mail_new_message",
    "mail_new_title",
    "openai_quota_exhausted_message",
    "openai_quota_exhausted_title",
    "mail_sync_failure_message",
    "mail_sync_failure_title",
    "messaging_account_degraded_message",
    "messaging_account_degraded_title",
    "messaging_account_recovered_message",
    "messaging_account_recovered_title",
    "plugin_circuit_breaker_tripped_message",
    "plugin_circuit_breaker_tripped_title",
    "vault_secret_request_required_message",
    "vault_secret_request_required_title",
    "security_login_throttle_message",
    "security_login_throttle_title",
    "tool_approval_required_message",
    "tool_approval_required_title",
)


class NotificationTemplateId(str, Enum):
    API_RATE_LIMIT_APPLIED_MESSAGE = "api_rate_limit_applied_message"
    API_RATE_LIMIT_APPLIED_TITLE = "api_rate_limit_applied_title"
    ASK_USER_REQUIRED_MESSAGE = "ask_user_required_message"
    ASK_USER_REQUIRED_TITLE = "ask_user_required_title"
    AUTOMATION_COMPLETED_MESSAGE = "automation_completed_message"
    AUTOMATION_COMPLETED_MESSAGE_GENERIC = "automation_completed_message_generic"
    AUTOMATION_COMPLETED_TITLE = "automation_completed_title"
    AUTOMATION_FAILED_MESSAGE = "automation_failed_message"
    AUTOMATION_FAILED_MESSAGE_GENERIC = "automation_failed_message_generic"
    AUTOMATION_FAILED_MESSAGE_WITH_STATUS = "automation_failed_message_with_status"
    AUTOMATION_FAILED_MESSAGE_WITH_STATUS_GENERIC = "automation_failed_message_with_status_generic"
    AUTOMATION_FAILED_TITLE = "automation_failed_title"
    BACKUP_OPERATION_FAILED_MESSAGE = "backup_operation_failed_message"
    BACKUP_OPERATION_FAILED_TITLE = "backup_operation_failed_title"
    CALENDAR_INVITE_UPDATE_MESSAGE = "calendar_invite_update_message"
    CALENDAR_INVITE_UPDATE_TITLE = "calendar_invite_update_title"
    CALENDAR_REMINDER_DUE_MESSAGE = "calendar_reminder_due_message"
    CALENDAR_REMINDER_DUE_TITLE = "calendar_reminder_due_title"
    CALENDAR_REMINDER_MISSED_MESSAGE = "calendar_reminder_missed_message"
    CALENDAR_REMINDER_MISSED_TITLE = "calendar_reminder_missed_title"
    CALENDAR_SYNC_FAILURE_MESSAGE = "calendar_sync_failure_message"
    CALENDAR_SYNC_FAILURE_TITLE = "calendar_sync_failure_title"
    LOW_DISK_SPACE_MESSAGE = "low_disk_space_message"
    LOW_DISK_SPACE_TITLE = "low_disk_space_title"
    MAIL_NEW_MESSAGE = "mail_new_message"
    MAIL_NEW_TITLE = "mail_new_title"
    OPENAI_QUOTA_EXHAUSTED_MESSAGE = "openai_quota_exhausted_message"
    OPENAI_QUOTA_EXHAUSTED_TITLE = "openai_quota_exhausted_title"
    MAIL_SYNC_FAILURE_MESSAGE = "mail_sync_failure_message"
    MAIL_SYNC_FAILURE_TITLE = "mail_sync_failure_title"
    MESSAGING_ACCOUNT_DEGRADED_MESSAGE = "messaging_account_degraded_message"
    MESSAGING_ACCOUNT_DEGRADED_TITLE = "messaging_account_degraded_title"
    MESSAGING_ACCOUNT_RECOVERED_MESSAGE = "messaging_account_recovered_message"
    MESSAGING_ACCOUNT_RECOVERED_TITLE = "messaging_account_recovered_title"
    PLUGIN_CIRCUIT_BREAKER_TRIPPED_MESSAGE = "plugin_circuit_breaker_tripped_message"
    PLUGIN_CIRCUIT_BREAKER_TRIPPED_TITLE = "plugin_circuit_breaker_tripped_title"
    CREDENTIAL_REQUEST_REQUIRED_MESSAGE = "vault_secret_request_required_message"
    CREDENTIAL_REQUEST_REQUIRED_TITLE = "vault_secret_request_required_title"
    SECURITY_LOGIN_THROTTLE_MESSAGE = "security_login_throttle_message"
    SECURITY_LOGIN_THROTTLE_TITLE = "security_login_throttle_title"
    TOOL_APPROVAL_REQUIRED_MESSAGE = "tool_approval_required_message"
    TOOL_APPROVAL_REQUIRED_TITLE = "tool_approval_required_title"


class NotificationType(str, Enum):
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"


class NotificationLinkType(str, Enum):
    URL = "url"
    CONVERSATION = "conversation"
    AUTOMATION_RUN = "automation_run"


def validate_notifications_sql_contract() -> None:
    template_values = {item.value for item in NotificationTemplateId}
    sql_values = set(NOTIFICATION_TEMPLATE_SQL_VALUES)
    if template_values != sql_values:
        raise StateError("Notification template SQL contract is invalid.")
    text_type_values = set(NOTIFICATION_TEXT_TYPE_SQL_VALUES)
    if text_type_values != {"text", "template"}:
        raise StateError("Notification text_type SQL contract is invalid.")
    for template_id in NotificationTemplateId:
        resolve_notification_template_required_params(template_id)


def resolve_notification_template_required_params(
    template: NotificationTemplateId,
) -> frozenset[str]:
    match template:
        case NotificationTemplateId.OPENAI_QUOTA_EXHAUSTED_MESSAGE:
            return frozenset({"keyLabel", "windowLabel"})
        case NotificationTemplateId.OPENAI_QUOTA_EXHAUSTED_TITLE:
            return frozenset({"keyLabel"})
        case NotificationTemplateId.API_RATE_LIMIT_APPLIED_MESSAGE:
            return frozenset({"scopeLabel", "failureCount"})
        case NotificationTemplateId.API_RATE_LIMIT_APPLIED_TITLE:
            return frozenset({"scopeLabel"})
        case NotificationTemplateId.ASK_USER_REQUIRED_MESSAGE:
            return frozenset()
        case NotificationTemplateId.ASK_USER_REQUIRED_TITLE:
            return frozenset()
        case NotificationTemplateId.AUTOMATION_COMPLETED_MESSAGE:
            return frozenset({"automationTitle"})
        case NotificationTemplateId.AUTOMATION_COMPLETED_MESSAGE_GENERIC:
            return frozenset()
        case NotificationTemplateId.AUTOMATION_COMPLETED_TITLE:
            return frozenset()
        case NotificationTemplateId.AUTOMATION_FAILED_MESSAGE:
            return frozenset({"automationTitle"})
        case NotificationTemplateId.AUTOMATION_FAILED_MESSAGE_GENERIC:
            return frozenset()
        case NotificationTemplateId.AUTOMATION_FAILED_MESSAGE_WITH_STATUS:
            return frozenset({"automationTitle", "statusMessage"})
        case NotificationTemplateId.AUTOMATION_FAILED_MESSAGE_WITH_STATUS_GENERIC:
            return frozenset({"statusMessage"})
        case NotificationTemplateId.AUTOMATION_FAILED_TITLE:
            return frozenset()
        case NotificationTemplateId.BACKUP_OPERATION_FAILED_MESSAGE:
            return frozenset({"operationLabel", "failureCount"})
        case NotificationTemplateId.BACKUP_OPERATION_FAILED_TITLE:
            return frozenset({"operationLabel"})
        case NotificationTemplateId.CALENDAR_INVITE_UPDATE_MESSAGE:
            return frozenset({"summary", "start"})
        case NotificationTemplateId.CALENDAR_INVITE_UPDATE_TITLE:
            return frozenset({"accountLabel"})
        case NotificationTemplateId.CALENDAR_REMINDER_DUE_MESSAGE:
            return frozenset({"summary", "start"})
        case NotificationTemplateId.CALENDAR_REMINDER_DUE_TITLE:
            return frozenset({"accountLabel"})
        case NotificationTemplateId.CALENDAR_REMINDER_MISSED_MESSAGE:
            return frozenset({"summary", "start"})
        case NotificationTemplateId.CALENDAR_REMINDER_MISSED_TITLE:
            return frozenset({"accountLabel"})
        case NotificationTemplateId.CALENDAR_SYNC_FAILURE_MESSAGE:
            return frozenset({"reason"})
        case NotificationTemplateId.CALENDAR_SYNC_FAILURE_TITLE:
            return frozenset({"accountLabel"})
        case NotificationTemplateId.LOW_DISK_SPACE_MESSAGE:
            return frozenset({"operationLabel", "deficit"})
        case NotificationTemplateId.LOW_DISK_SPACE_TITLE:
            return frozenset({"operationLabel"})
        case NotificationTemplateId.MAIL_NEW_MESSAGE:
            return frozenset({"from", "subject"})
        case NotificationTemplateId.MAIL_NEW_TITLE:
            return frozenset({"accountLabel"})
        case NotificationTemplateId.MAIL_SYNC_FAILURE_MESSAGE:
            return frozenset({"reason"})
        case NotificationTemplateId.MAIL_SYNC_FAILURE_TITLE:
            return frozenset({"accountLabel"})
        case NotificationTemplateId.MESSAGING_ACCOUNT_DEGRADED_MESSAGE:
            return frozenset({"accountLabel", "providerLabel"})
        case NotificationTemplateId.MESSAGING_ACCOUNT_DEGRADED_TITLE:
            return frozenset()
        case NotificationTemplateId.MESSAGING_ACCOUNT_RECOVERED_MESSAGE:
            return frozenset({"accountLabel", "providerLabel"})
        case NotificationTemplateId.MESSAGING_ACCOUNT_RECOVERED_TITLE:
            return frozenset()
        case NotificationTemplateId.PLUGIN_CIRCUIT_BREAKER_TRIPPED_MESSAGE:
            return frozenset({"pluginName"})
        case NotificationTemplateId.PLUGIN_CIRCUIT_BREAKER_TRIPPED_TITLE:
            return frozenset()
        case NotificationTemplateId.CREDENTIAL_REQUEST_REQUIRED_MESSAGE:
            return frozenset()
        case NotificationTemplateId.CREDENTIAL_REQUEST_REQUIRED_TITLE:
            return frozenset()
        case NotificationTemplateId.SECURITY_LOGIN_THROTTLE_MESSAGE:
            return frozenset({"attemptCount", "windowMinutes"})
        case NotificationTemplateId.SECURITY_LOGIN_THROTTLE_TITLE:
            return frozenset()
        case NotificationTemplateId.TOOL_APPROVAL_REQUIRED_MESSAGE:
            return frozenset({"toolName"})
        case NotificationTemplateId.TOOL_APPROVAL_REQUIRED_TITLE:
            return frozenset()
        case _:
            raise StateError("Notification template params SQL contract is invalid.")
