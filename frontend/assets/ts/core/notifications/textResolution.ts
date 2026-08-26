/* SoAI - Shared notifications text resolution [frontend/assets/ts/core/notifications/textResolution.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { assertNever } from '@core/assertions.ts';
import { i18n } from '@core/i18n/index.ts';
import type { NotificationText } from '@core/notifications/types.ts';

const resolveNotificationText = (value: NotificationText): string => {
    if (value.textType === 'text') {
        return value.text;
    }
    switch (value.template) {
        case 'openai_quota_exhausted_message':
            return i18n.t('notifications.openaiQuota.exhausted.message', { keyLabel: value.parameters.keyLabel, windowLabel: value.parameters.windowLabel });
        case 'openai_quota_exhausted_title':
            return i18n.t('notifications.openaiQuota.exhausted.title', { keyLabel: value.parameters.keyLabel });
        case 'api_rate_limit_applied_message':
            return i18n.t('notifications.apiRateLimit.applied.message', { scopeLabel: value.parameters.scopeLabel, failureCount: value.parameters.failureCount });
        case 'api_rate_limit_applied_title':
            return i18n.t('notifications.apiRateLimit.applied.title', { scopeLabel: value.parameters.scopeLabel });
        case 'tool_approval_required_title':
            return i18n.t('notifications.toolApproval.required.title');
        case 'tool_approval_required_message':
            return i18n.t('notifications.toolApproval.required.message', { toolName: value.parameters.toolName });
        case 'ask_user_required_title':
            return i18n.t('notifications.askUser.required.title');
        case 'ask_user_required_message':
            return i18n.t('notifications.askUser.required.message');
        case 'vault_secret_request_required_title':
            return i18n.t('notifications.vaultSecretRequest.required.title');
        case 'vault_secret_request_required_message':
            return i18n.t('notifications.vaultSecretRequest.required.message');
        case 'automation_completed_title':
            return i18n.t('notifications.automation.completed.title');
        case 'automation_completed_message':
            return i18n.t('notifications.automation.completed.message', { automationTitle: value.parameters.automationTitle });
        case 'automation_completed_message_generic':
            return i18n.t('notifications.automation.completed.messageGeneric');
        case 'automation_failed_title':
            return i18n.t('notifications.automation.failed.title');
        case 'automation_failed_message':
            return i18n.t('notifications.automation.failed.message', { automationTitle: value.parameters.automationTitle });
        case 'automation_failed_message_generic':
            return i18n.t('notifications.automation.failed.messageGeneric');
        case 'automation_failed_message_with_status':
            return i18n.t('notifications.automation.failed.messageWithStatus', { automationTitle: value.parameters.automationTitle, statusMessage: value.parameters.statusMessage });
        case 'automation_failed_message_with_status_generic':
            return i18n.t('notifications.automation.failed.messageWithStatusGeneric', { statusMessage: value.parameters.statusMessage });
        case 'backup_operation_failed_message':
            return i18n.t('notifications.backup.operationFailed.message', { operationLabel: value.parameters.operationLabel, failureCount: value.parameters.failureCount });
        case 'backup_operation_failed_title':
            return i18n.t('notifications.backup.operationFailed.title', { operationLabel: value.parameters.operationLabel });
        case 'mail_new_title':
            return i18n.t('notifications.mail.new.title', { accountLabel: value.parameters.accountLabel });
        case 'mail_new_message':
            return i18n.t('notifications.mail.new.message', { from: value.parameters.from, subject: value.parameters.subject });
        case 'mail_sync_failure_title':
            return i18n.t('notifications.mail.syncFailure.title', { accountLabel: value.parameters.accountLabel });
        case 'mail_sync_failure_message':
            return i18n.t('notifications.mail.syncFailure.message', { reason: value.parameters.reason });
        case 'messaging_account_degraded_title':
            return i18n.t('notifications.messaging.degraded.title');
        case 'messaging_account_degraded_message':
            return i18n.t('notifications.messaging.degraded.message', { accountLabel: value.parameters.accountLabel, providerLabel: value.parameters.providerLabel });
        case 'messaging_account_recovered_title':
            return i18n.t('notifications.messaging.recovered.title');
        case 'messaging_account_recovered_message':
            return i18n.t('notifications.messaging.recovered.message', { accountLabel: value.parameters.accountLabel, providerLabel: value.parameters.providerLabel });
        case 'calendar_invite_update_title':
            return i18n.t('notifications.calendar.inviteUpdate.title', { accountLabel: value.parameters.accountLabel });
        case 'calendar_invite_update_message':
            return i18n.t('notifications.calendar.inviteUpdate.message', { summary: value.parameters.summary, start: value.parameters.start });
        case 'calendar_reminder_due_title':
            return i18n.t('notifications.calendar.reminderDue.title', { accountLabel: value.parameters.accountLabel });
        case 'calendar_reminder_due_message':
            return i18n.t('notifications.calendar.reminderDue.message', { summary: value.parameters.summary, start: value.parameters.start });
        case 'calendar_reminder_missed_title':
            return i18n.t('notifications.calendar.reminderMissed.title', { accountLabel: value.parameters.accountLabel });
        case 'calendar_reminder_missed_message':
            return i18n.t('notifications.calendar.reminderMissed.message', { summary: value.parameters.summary, start: value.parameters.start });
        case 'calendar_sync_failure_title':
            return i18n.t('notifications.calendar.syncFailure.title', { accountLabel: value.parameters.accountLabel });
        case 'calendar_sync_failure_message':
            return i18n.t('notifications.calendar.syncFailure.message', { reason: value.parameters.reason });
        case 'low_disk_space_message':
            return i18n.t('notifications.storage.lowDisk.message', { operationLabel: value.parameters.operationLabel, deficit: value.parameters.deficit });
        case 'low_disk_space_title':
            return i18n.t('notifications.storage.lowDisk.title', { operationLabel: value.parameters.operationLabel });
        case 'security_login_throttle_title':
            return i18n.t('notifications.security.loginThrottle.title');
        case 'security_login_throttle_message':
            return i18n.t('notifications.security.loginThrottle.message', { attemptCount: value.parameters.attemptCount, windowMinutes: value.parameters.windowMinutes });
        case 'plugin_circuit_breaker_tripped_title':
            return i18n.t('plugins.notifications.circuitBreakerTrippedTitle');
        case 'plugin_circuit_breaker_tripped_message':
            return i18n.t('plugins.notifications.circuitBreakerTrippedMessage', { pluginName: value.parameters.pluginName });
        default:
            return assertNever(value, 'Notification template is invalid');
    }
};

export { resolveNotificationText };
