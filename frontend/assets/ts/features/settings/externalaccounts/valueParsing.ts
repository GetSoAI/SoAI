/* SoAI - Settings feature value parsing [frontend/assets/ts/features/settings/externalaccounts/valueParsing.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { splitTrimmedList, uniqueSortedStrings } from '@core/normalize.ts';
import { securityApi } from '@core/security/public.ts';
import { readRequiredTrimmedStringMessageValue } from '@core/types/payloadValueReaders.ts';
import type { ExternalAccountAuthType, MailProtocol, MailSecurity } from '@core/api/contracts/externalAccountContracts.ts';
import { parseExternalAccountAuthType, parseMailProtocol, parseMailSecurity } from '@features/settings/externalaccounts/values.ts';

const parseDelimitedList = (value: string): string[] => {
    return uniqueSortedStrings(splitTrimmedList(value, /\r?\n|,/), 'en');
};

const requireAbsoluteHttpUrl = (value: string, errorMessage: string): string => {
    const normalized = readRequiredTrimmedStringMessageValue(value, errorMessage);
    const sanitized = securityApi.sanitizeAbsoluteHttpUrl(normalized);
    if (!sanitized) {
        throw new Error(errorMessage);
    }
    return sanitized;
};

const requireOptionalAbsoluteHttpUrl = (value: string, errorMessage: string): string | null => {
    const normalized = value.trim();
    return normalized ? requireAbsoluteHttpUrl(normalized, errorMessage) : null;
};

const requireAuthType = (value: string): ExternalAccountAuthType => {
    const authType = parseExternalAccountAuthType(value);
    if (authType === null) {
        throw new Error(i18n.t('settings.externalAccounts.validation.authType'));
    }
    return authType;
};

const requireMailProtocol = (value: string): MailProtocol => {
    const protocol = parseMailProtocol(value);
    if (protocol === null) {
        throw new Error(i18n.t('settings.externalAccounts.validation.mailProtocol'));
    }
    return protocol;
};

const requireMailSecurity = (value: string, errorMessage: string): MailSecurity => {
    const security = parseMailSecurity(value);
    if (security === null) {
        throw new Error(errorMessage);
    }
    return security;
};

export { parseDelimitedList, requireAbsoluteHttpUrl, requireAuthType, requireMailProtocol, requireMailSecurity, requireOptionalAbsoluteHttpUrl };
