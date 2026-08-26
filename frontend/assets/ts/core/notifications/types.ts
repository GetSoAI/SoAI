/* SoAI - Shared frontend notifications public contracts [frontend/assets/ts/core/notifications/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

export type NotificationRecordType = 'info' | 'success' | 'warning' | 'error';

export type NotificationLinkType = 'url' | 'conversation' | 'automation_run';

export type NotificationTemplateId =
    | 'api_rate_limit_applied_message'
    | 'api_rate_limit_applied_title'
    | 'tool_approval_required_title'
    | 'tool_approval_required_message'
    | 'ask_user_required_title'
    | 'ask_user_required_message'
    | 'vault_secret_request_required_title'
    | 'vault_secret_request_required_message'
    | 'automation_completed_title'
    | 'automation_completed_message'
    | 'automation_completed_message_generic'
    | 'automation_failed_title'
    | 'automation_failed_message'
    | 'automation_failed_message_generic'
    | 'automation_failed_message_with_status'
    | 'automation_failed_message_with_status_generic'
    | 'backup_operation_failed_message'
    | 'backup_operation_failed_title'
    | 'mail_new_title'
    | 'openai_quota_exhausted_message'
    | 'openai_quota_exhausted_title'
    | 'mail_new_message'
    | 'mail_sync_failure_title'
    | 'mail_sync_failure_message'
    | 'messaging_account_degraded_title'
    | 'messaging_account_degraded_message'
    | 'messaging_account_recovered_title'
    | 'messaging_account_recovered_message'
    | 'calendar_invite_update_title'
    | 'calendar_invite_update_message'
    | 'calendar_reminder_due_title'
    | 'calendar_reminder_due_message'
    | 'calendar_reminder_missed_title'
    | 'calendar_reminder_missed_message'
    | 'calendar_sync_failure_title'
    | 'calendar_sync_failure_message'
    | 'low_disk_space_message'
    | 'low_disk_space_title'
    | 'security_login_throttle_title'
    | 'security_login_throttle_message'
    | 'plugin_circuit_breaker_tripped_title'
    | 'plugin_circuit_breaker_tripped_message';

type NotificationTemplateText =
    | { textType: 'template'; template: 'api_rate_limit_applied_message'; parameters: { scopeLabel: string; failureCount: string } }
    | { textType: 'template'; template: 'api_rate_limit_applied_title'; parameters: { scopeLabel: string } }
    | { textType: 'template'; template: 'tool_approval_required_title' }
    | { textType: 'template'; template: 'tool_approval_required_message'; parameters: { toolName: string } }
    | { textType: 'template'; template: 'ask_user_required_title' }
    | { textType: 'template'; template: 'ask_user_required_message' }
    | { textType: 'template'; template: 'vault_secret_request_required_title' }
    | { textType: 'template'; template: 'vault_secret_request_required_message' }
    | { textType: 'template'; template: 'automation_completed_title' }
    | { textType: 'template'; template: 'automation_completed_message'; parameters: { automationTitle: string } }
    | { textType: 'template'; template: 'automation_completed_message_generic' }
    | { textType: 'template'; template: 'automation_failed_title' }
    | { textType: 'template'; template: 'automation_failed_message'; parameters: { automationTitle: string } }
    | { textType: 'template'; template: 'automation_failed_message_generic' }
    | { textType: 'template'; template: 'automation_failed_message_with_status'; parameters: { automationTitle: string; statusMessage: string } }
    | { textType: 'template'; template: 'automation_failed_message_with_status_generic'; parameters: { statusMessage: string } }
    | { textType: 'template'; template: 'backup_operation_failed_message'; parameters: { operationLabel: string; failureCount: string } }
    | { textType: 'template'; template: 'backup_operation_failed_title'; parameters: { operationLabel: string } }
    | { textType: 'template'; template: 'mail_new_title'; parameters: { accountLabel: string } }
    | { textType: 'template'; template: 'openai_quota_exhausted_message'; parameters: { keyLabel: string; windowLabel: string } }
    | { textType: 'template'; template: 'openai_quota_exhausted_title'; parameters: { keyLabel: string } }
    | { textType: 'template'; template: 'mail_new_message'; parameters: { from: string; subject: string } }
    | { textType: 'template'; template: 'mail_sync_failure_title'; parameters: { accountLabel: string } }
    | { textType: 'template'; template: 'mail_sync_failure_message'; parameters: { reason: string } }
    | { textType: 'template'; template: 'messaging_account_degraded_title' }
    | { textType: 'template'; template: 'messaging_account_degraded_message'; parameters: { accountLabel: string; providerLabel: string } }
    | { textType: 'template'; template: 'messaging_account_recovered_title' }
    | { textType: 'template'; template: 'messaging_account_recovered_message'; parameters: { accountLabel: string; providerLabel: string } }
    | { textType: 'template'; template: 'calendar_invite_update_title'; parameters: { accountLabel: string } }
    | { textType: 'template'; template: 'calendar_invite_update_message'; parameters: { summary: string; start: string } }
    | { textType: 'template'; template: 'calendar_reminder_due_title'; parameters: { accountLabel: string } }
    | { textType: 'template'; template: 'calendar_reminder_due_message'; parameters: { summary: string; start: string } }
    | { textType: 'template'; template: 'calendar_reminder_missed_title'; parameters: { accountLabel: string } }
    | { textType: 'template'; template: 'calendar_reminder_missed_message'; parameters: { summary: string; start: string } }
    | { textType: 'template'; template: 'calendar_sync_failure_title'; parameters: { accountLabel: string } }
    | { textType: 'template'; template: 'calendar_sync_failure_message'; parameters: { reason: string } }
    | { textType: 'template'; template: 'low_disk_space_message'; parameters: { operationLabel: string; deficit: string } }
    | { textType: 'template'; template: 'low_disk_space_title'; parameters: { operationLabel: string } }
    | { textType: 'template'; template: 'security_login_throttle_title' }
    | { textType: 'template'; template: 'security_login_throttle_message'; parameters: { attemptCount: string; windowMinutes: string } }
    | { textType: 'template'; template: 'plugin_circuit_breaker_tripped_title' }
    | { textType: 'template'; template: 'plugin_circuit_breaker_tripped_message'; parameters: { pluginName: string } };

export type NotificationText = NotificationTemplateText | { textType: 'text'; text: string };

export interface NotificationLink {
    linkType: NotificationLinkType;
    value: string;
}

export interface NotificationRecord {
    id: string;
    userId: number;
    createdAtMs: number;
    type: NotificationRecordType;
    title: NotificationText;
    message: NotificationText;
    source: string | null;
    link: NotificationLink | null;
    readAtMs: number | null;
}

export interface NotificationCursor {
    createdAtMs: number;
    id: string;
}

export interface NotificationsListResponse {
    notifications: NotificationRecord[];
    totalCount: number;
    unreadCount: number;
    nextCursor: NotificationCursor | null;
}
