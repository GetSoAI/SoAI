/* SoAI - Shared frontend notifications boundary contracts [frontend/assets/ts/core/notifications/contracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { hasOwn } from '@core/typeGuards.ts';
import type { NotificationTemplateId } from '@core/notifications/types.ts';

const NOTIFICATION_TEMPLATE_REQUIRED_PARAMETER_KEYS: { readonly [K in NotificationTemplateId]: readonly string[] } = {
    'api_rate_limit_applied_message': ['scopeLabel', 'failureCount'],
    'api_rate_limit_applied_title': ['scopeLabel'],
    'tool_approval_required_title': [],
    'tool_approval_required_message': ['toolName'],
    'ask_user_required_title': [],
    'ask_user_required_message': [],
    'vault_secret_request_required_title': [],
    'vault_secret_request_required_message': [],
    'automation_completed_title': [],
    'automation_completed_message': ['automationTitle'],
    'automation_completed_message_generic': [],
    'automation_failed_title': [],
    'automation_failed_message': ['automationTitle'],
    'automation_failed_message_generic': [],
    'automation_failed_message_with_status': ['automationTitle', 'statusMessage'],
    'automation_failed_message_with_status_generic': ['statusMessage'],
    'backup_operation_failed_message': ['operationLabel', 'failureCount'],
    'backup_operation_failed_title': ['operationLabel'],
    'mail_new_title': ['accountLabel'],
    'openai_quota_exhausted_message': ['keyLabel', 'windowLabel'],
    'openai_quota_exhausted_title': ['keyLabel'],
    'mail_new_message': ['from', 'subject'],
    'mail_sync_failure_title': ['accountLabel'],
    'mail_sync_failure_message': ['reason'],
    'messaging_account_degraded_title': [],
    'messaging_account_degraded_message': ['accountLabel', 'providerLabel'],
    'messaging_account_recovered_title': [],
    'messaging_account_recovered_message': ['accountLabel', 'providerLabel'],
    'calendar_invite_update_title': ['accountLabel'],
    'calendar_invite_update_message': ['summary', 'start'],
    'calendar_reminder_due_title': ['accountLabel'],
    'calendar_reminder_due_message': ['summary', 'start'],
    'calendar_reminder_missed_title': ['accountLabel'],
    'calendar_reminder_missed_message': ['summary', 'start'],
    'calendar_sync_failure_title': ['accountLabel'],
    'calendar_sync_failure_message': ['reason'],
    'low_disk_space_message': ['operationLabel', 'deficit'],
    'low_disk_space_title': ['operationLabel'],
    'security_login_throttle_title': [],
    'security_login_throttle_message': ['attemptCount', 'windowMinutes'],
    'plugin_circuit_breaker_tripped_title': [],
    'plugin_circuit_breaker_tripped_message': ['pluginName']
};

const isNotificationTemplateId = (value: string): value is NotificationTemplateId => {
    return hasOwn(NOTIFICATION_TEMPLATE_REQUIRED_PARAMETER_KEYS, value);
};

export { NOTIFICATION_TEMPLATE_REQUIRED_PARAMETER_KEYS, isNotificationTemplateId };
