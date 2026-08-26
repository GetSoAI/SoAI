/* SoAI - Shared notifications classification [frontend/assets/ts/core/notifications/classification.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { NotificationRecord, NotificationTemplateId, NotificationText } from '@core/notifications/types.ts';

const isNotificationAskUserTemplate = (template: NotificationTemplateId): boolean => {
    return template === 'ask_user_required_title' || template === 'ask_user_required_message';
};

const isNotificationAttentionTemplate = (template: NotificationTemplateId): boolean => {
    return template === 'tool_approval_required_title' || template === 'tool_approval_required_message' || isNotificationAskUserTemplate(template) || template === 'vault_secret_request_required_title' || template === 'vault_secret_request_required_message';
};

const notificationTextRequiresUserAttention = (text: NotificationText): boolean => {
    return text.textType === 'template' && isNotificationAttentionTemplate(text.template);
};

const notificationRecordRequiresUserAttention = (record: NotificationRecord): boolean => {
    return notificationTextRequiresUserAttention(record.title) || notificationTextRequiresUserAttention(record.message);
};

export { notificationRecordRequiresUserAttention, notificationTextRequiresUserAttention };
