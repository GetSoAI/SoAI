/* SoAI - Settings feature values [frontend/assets/ts/features/settings/externalaccounts/values.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { readRequiredTrimmedStringArrayValue } from '@core/types/payloadArrayReaders.ts';
import { readAllowedStringValue, readRequiredEnumValue } from '@core/types/payloadValueReaders.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import type { CalendarAccountSupportedAction, ExternalAccountAuthType, MailAccountSupportedAction, MailProtocol, MailSecurity } from '@core/api/contracts/externalAccountContracts.ts';

const EXTERNAL_ACCOUNT_AUTH_TYPES: readonly ExternalAccountAuthType[] = ['password', 'oauth2'];
const MAIL_PROTOCOLS: readonly MailProtocol[] = ['imap', 'pop3'];
const MAIL_SECURITIES: readonly MailSecurity[] = ['tls', 'starttls'];
const MAIL_SUPPORTED_ACTIONS: readonly MailAccountSupportedAction[] = ['delete', 'test', 'sync', 'compose', 'oauth_connect', 'oauth_clear'];
const CALENDAR_SUPPORTED_ACTIONS: readonly CalendarAccountSupportedAction[] = ['delete', 'test', 'sync', 'oauth_connect', 'oauth_clear'];

const parseExternalAccountAuthType = (value: JsonValue | null | undefined): ExternalAccountAuthType | null => readAllowedStringValue(value, EXTERNAL_ACCOUNT_AUTH_TYPES);

const parseMailProtocol = (value: JsonValue | null | undefined): MailProtocol | null => readAllowedStringValue(value, MAIL_PROTOCOLS);

const parseMailSecurity = (value: JsonValue | null | undefined): MailSecurity | null => readAllowedStringValue(value, MAIL_SECURITIES);

const readExternalAccountAuthType = (value: JsonValue | null | undefined, label: string): ExternalAccountAuthType => readRequiredEnumValue(value, label, EXTERNAL_ACCOUNT_AUTH_TYPES);

const readMailProtocol = (value: JsonValue | null | undefined, label: string): MailProtocol => readRequiredEnumValue(value, label, MAIL_PROTOCOLS);

const readMailSecurity = (value: JsonValue | null | undefined, label: string): MailSecurity => readRequiredEnumValue(value, label, MAIL_SECURITIES);

const readNullableMailSecurity = (value: JsonValue | null | undefined, label: string): MailSecurity | null => {
    if (value === null || value === undefined) {
        return null;
    }
    return readMailSecurity(value, label);
};

const normalizeSupportedActions = <TAction extends string>(value: JsonValue | null | undefined, label: string, allowedActions: readonly TAction[]): TAction[] => {
    const actions = readRequiredTrimmedStringArrayValue(value, label);
    const normalized: TAction[] = [];
    actions.forEach((action) => {
        const allowedAction = readAllowedStringValue(action, allowedActions);
        if (allowedAction === null) {
            throw new Error(`${label} entry is invalid: ${action}`);
        }
        if (normalized.includes(allowedAction)) {
            throw new Error(`${label} entry is duplicated: ${action}`);
        }
        normalized.push(allowedAction);
    });
    return normalized;
};

const normalizeMailSupportedActions = (value: JsonValue | null | undefined): MailAccountSupportedAction[] => normalizeSupportedActions(value, 'Mail supported_actions', MAIL_SUPPORTED_ACTIONS);

const normalizeCalendarSupportedActions = (value: JsonValue | null | undefined): CalendarAccountSupportedAction[] => normalizeSupportedActions(value, 'Calendar supported_actions', CALENDAR_SUPPORTED_ACTIONS);

export { normalizeCalendarSupportedActions, normalizeMailSupportedActions, parseExternalAccountAuthType, parseMailProtocol, parseMailSecurity, readExternalAccountAuthType, readMailProtocol, readNullableMailSecurity };
