/* SoAI - Shared notifications text parsing [frontend/assets/ts/core/notifications/textParsing.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { NOTIFICATION_TEMPLATE_REQUIRED_PARAMETER_KEYS, isNotificationTemplateId } from '@core/notifications/contracts.ts';
import type { NotificationTemplateId, NotificationText } from '@core/notifications/types.ts';
import { assertAllowedNotificationKeys } from '@core/notifications/valueParsing.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { isPlainObject, isString } from '@core/typeGuards.ts';

const NOTIFICATION_TEXT_PLAIN_KEYS: ReadonlySet<string> = Object.freeze(new Set(['text_type', 'text']));
const NOTIFICATION_TEXT_TEMPLATE_KEYS: ReadonlySet<string> = Object.freeze(new Set(['text_type', 'template', 'params']));
type TemplateNotificationText = Extract<NotificationText, { textType: 'template' }>;

const hasNoParameters = (parameters: JsonValue | null | undefined): boolean => parameters == null || (isPlainObject(parameters) && Object.keys(parameters).length === 0);

const parseSingleStringParameter = (parameters: JsonValue | null | undefined, key: string): Record<string, string> | null => {
    if (!isPlainObject(parameters)) {
        return null;
    }
    const keys = Object.keys(parameters);
    if (keys.length !== 1 || keys[0] !== key) {
        return null;
    }
    const value = parameters[key];
    if (!isString(value) || !value.trim()) {
        return null;
    }
    return { [key]: value.trim() };
};

const parseOrderedStringParameters = (parameters: JsonValue | null | undefined, keys: readonly string[]): Record<string, string> | null => {
    if (!isPlainObject(parameters)) {
        return null;
    }
    const sortedKeys = Object.keys(parameters).sort((left, right) => left.localeCompare(right, 'en'));
    const expectedKeys = [...keys].sort((left, right) => left.localeCompare(right, 'en'));
    if (sortedKeys.length !== expectedKeys.length || sortedKeys.some((key, index) => key !== expectedKeys[index])) {
        return null;
    }
    const parsed: Record<string, string> = {};
    for (const key of expectedKeys) {
        const value = parameters[key];
        if (!isString(value) || !value.trim()) {
            return null;
        }
        parsed[key] = value.trim();
    }
    return parsed;
};

const parseTemplateNotificationText = (template: NotificationTemplateId, parametersValue: JsonValue | null | undefined): TemplateNotificationText | null => {
    switch (template) {
        case 'tool_approval_required_title':
        case 'ask_user_required_title':
        case 'ask_user_required_message':
        case 'vault_secret_request_required_title':
        case 'vault_secret_request_required_message':
        case 'automation_completed_title':
        case 'automation_completed_message_generic':
        case 'automation_failed_title':
        case 'automation_failed_message_generic':
        case 'messaging_account_degraded_title':
        case 'messaging_account_recovered_title':
        case 'security_login_throttle_title':
        case 'plugin_circuit_breaker_tripped_title': {
            return hasNoParameters(parametersValue) ? { textType: 'template', template } : null;
        }
        case 'tool_approval_required_message': {
            const parameters = parseSingleStringParameter(parametersValue, 'toolName');
            const toolName = parameters?.['toolName'];
            return toolName === undefined ? null : { textType: 'template', template, parameters: { toolName } };
        }
        case 'automation_completed_message':
        case 'automation_failed_message': {
            const parameters = parseSingleStringParameter(parametersValue, 'automationTitle');
            const automationTitle = parameters?.['automationTitle'];
            return automationTitle === undefined ? null : { textType: 'template', template, parameters: { automationTitle } };
        }
        case 'openai_quota_exhausted_title': {
            const parameters = parseSingleStringParameter(parametersValue, 'keyLabel');
            const keyLabel = parameters?.['keyLabel'];
            return keyLabel === undefined ? null : { textType: 'template', template, parameters: { keyLabel } };
        }
        case 'api_rate_limit_applied_title': {
            const parameters = parseSingleStringParameter(parametersValue, 'scopeLabel');
            const scopeLabel = parameters?.['scopeLabel'];
            return scopeLabel === undefined ? null : { textType: 'template', template, parameters: { scopeLabel } };
        }
        case 'backup_operation_failed_title':
        case 'low_disk_space_title': {
            const parameters = parseSingleStringParameter(parametersValue, 'operationLabel');
            const operationLabel = parameters?.['operationLabel'];
            return operationLabel === undefined ? null : { textType: 'template', template, parameters: { operationLabel } };
        }
        case 'automation_failed_message_with_status': {
            const parameters = parseOrderedStringParameters(parametersValue, ['automationTitle', 'statusMessage']);
            const automationTitle = parameters?.['automationTitle'];
            const statusMessage = parameters?.['statusMessage'];
            return automationTitle === undefined || statusMessage === undefined ? null : { textType: 'template', template, parameters: { automationTitle, statusMessage } };
        }
        case 'openai_quota_exhausted_message': {
            const parameters = parseOrderedStringParameters(parametersValue, ['keyLabel', 'windowLabel']);
            const keyLabel = parameters?.['keyLabel'];
            const windowLabel = parameters?.['windowLabel'];
            return keyLabel === undefined || windowLabel === undefined ? null : { textType: 'template', template, parameters: { keyLabel, windowLabel } };
        }
        case 'api_rate_limit_applied_message': {
            const parameters = parseOrderedStringParameters(parametersValue, ['scopeLabel', 'failureCount']);
            const scopeLabel = parameters?.['scopeLabel'];
            const failureCount = parameters?.['failureCount'];
            return scopeLabel === undefined || failureCount === undefined ? null : { textType: 'template', template, parameters: { scopeLabel, failureCount } };
        }
        case 'backup_operation_failed_message': {
            const parameters = parseOrderedStringParameters(parametersValue, ['operationLabel', 'failureCount']);
            const operationLabel = parameters?.['operationLabel'];
            const failureCount = parameters?.['failureCount'];
            return operationLabel === undefined || failureCount === undefined ? null : { textType: 'template', template, parameters: { operationLabel, failureCount } };
        }
        case 'security_login_throttle_message': {
            const parameters = parseOrderedStringParameters(parametersValue, ['attemptCount', 'windowMinutes']);
            const attemptCount = parameters?.['attemptCount'];
            const windowMinutes = parameters?.['windowMinutes'];
            return attemptCount === undefined || windowMinutes === undefined ? null : { textType: 'template', template, parameters: { attemptCount, windowMinutes } };
        }
        case 'low_disk_space_message': {
            const parameters = parseOrderedStringParameters(parametersValue, ['operationLabel', 'deficit']);
            const operationLabel = parameters?.['operationLabel'];
            const deficit = parameters?.['deficit'];
            return operationLabel === undefined || deficit === undefined ? null : { textType: 'template', template, parameters: { operationLabel, deficit } };
        }
        case 'automation_failed_message_with_status_generic': {
            const parameters = parseSingleStringParameter(parametersValue, 'statusMessage');
            const statusMessage = parameters?.['statusMessage'];
            return statusMessage === undefined ? null : { textType: 'template', template, parameters: { statusMessage } };
        }
        case 'mail_new_title':
        case 'mail_sync_failure_title':
        case 'calendar_invite_update_title':
        case 'calendar_reminder_due_title':
        case 'calendar_reminder_missed_title':
        case 'calendar_sync_failure_title': {
            const parameters = parseSingleStringParameter(parametersValue, 'accountLabel');
            const accountLabel = parameters?.['accountLabel'];
            return accountLabel === undefined ? null : { textType: 'template', template, parameters: { accountLabel } };
        }
        case 'mail_new_message': {
            const parameters = parseOrderedStringParameters(parametersValue, ['from', 'subject']);
            const from = parameters?.['from'];
            const subject = parameters?.['subject'];
            return from === undefined || subject === undefined ? null : { textType: 'template', template, parameters: { from, subject } };
        }
        case 'messaging_account_degraded_message':
        case 'messaging_account_recovered_message': {
            const parameters = parseOrderedStringParameters(parametersValue, ['accountLabel', 'providerLabel']);
            const accountLabel = parameters?.['accountLabel'];
            const providerLabel = parameters?.['providerLabel'];
            return accountLabel === undefined || providerLabel === undefined ? null : { textType: 'template', template, parameters: { accountLabel, providerLabel } };
        }
        case 'mail_sync_failure_message':
        case 'calendar_sync_failure_message': {
            const parameters = parseSingleStringParameter(parametersValue, 'reason');
            const reason = parameters?.['reason'];
            return reason === undefined ? null : { textType: 'template', template, parameters: { reason } };
        }
        case 'plugin_circuit_breaker_tripped_message': {
            const parameters = parseSingleStringParameter(parametersValue, 'pluginName');
            const pluginName = parameters?.['pluginName'];
            return pluginName === undefined ? null : { textType: 'template', template, parameters: { pluginName } };
        }
        case 'calendar_invite_update_message':
        case 'calendar_reminder_due_message':
        case 'calendar_reminder_missed_message': {
            const parameters = parseOrderedStringParameters(parametersValue, ['summary', 'start']);
            const summary = parameters?.['summary'];
            const start = parameters?.['start'];
            return summary === undefined || start === undefined ? null : { textType: 'template', template, parameters: { summary, start } };
        }
        default:
            return null;
    }
};

const parseNotificationText = (value: JsonValue | null | undefined, options: { strict: boolean; label: string }): NotificationText => {
    if (!isPlainObject(value)) {
        throw new TypeError(`${options.label} must be an object`);
    }
    const textTypeValue = value['text_type'];
    if (textTypeValue === 'text') {
        if (options.strict) {
            assertAllowedNotificationKeys(value, NOTIFICATION_TEXT_PLAIN_KEYS, options.label);
        }
        const textValue = value['text'];
        if (!isString(textValue) || !textValue.trim()) {
            throw new TypeError(`${options.label}.text must be a non-empty string`);
        }
        return { textType: 'text', text: textValue.trim() };
    }
    if (textTypeValue === 'template') {
        if (options.strict) {
            assertAllowedNotificationKeys(value, NOTIFICATION_TEXT_TEMPLATE_KEYS, options.label);
        }
        const templateValue = value['template'];
        if (!isString(templateValue) || !templateValue.trim()) {
            throw new TypeError(`${options.label}.template must be a non-empty string`);
        }
        const template = templateValue.trim();
        if (!isNotificationTemplateId(template)) {
            throw new TypeError(`${options.label}.template is invalid`);
        }
        const parsed = parseTemplateNotificationText(template, value['params']);
        if (parsed === null) {
            throw new TypeError(`${options.label}.params must contain the required parameters only`);
        }
        if (options.strict) {
            const requiredKeys = NOTIFICATION_TEMPLATE_REQUIRED_PARAMETER_KEYS[template];
            const parsedParameterCount = 'parameters' in parsed ? Object.keys(parsed.parameters).length : 0;
            if (parsedParameterCount !== requiredKeys.length) {
                throw new TypeError(`${options.label}.params must contain the required parameters only`);
            }
        }
        return parsed;
    }
    throw new TypeError(`${options.label}.text_type is invalid`);
};

export { parseNotificationText };
