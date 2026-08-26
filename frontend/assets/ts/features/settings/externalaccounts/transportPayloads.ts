/* SoAI - Settings feature transport payloads [frontend/assets/ts/features/settings/externalaccounts/transportPayloads.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { parseJsonObjectText, parseOptionalJsonStringRecordText } from '@core/serialization/json.ts';
import { readRequiredPositiveIntegerTextValue } from '@core/types/payloadNumberReaders.ts';
import { readRequiredTrimmedStringMessageValue } from '@core/types/payloadValueReaders.ts';
import type { CalendarAccountTransportWrite, MailAccountTransportWrite } from '@core/api/contracts/externalAccountContracts.ts';
import { requireAbsoluteHttpUrl, requireMailProtocol, requireMailSecurity } from '@features/settings/externalaccounts/valueParsing.ts';

const buildMailTransportPayload = (readTrimmed: (name: string) => string): MailAccountTransportWrite => ({
    protocol: requireMailProtocol(readTrimmed('protocol')),
    inboundHost: readRequiredTrimmedStringMessageValue(readTrimmed('inbound_host'), i18n.t('settings.externalAccounts.validation.mailInboundHost')),
    inboundPort: readRequiredPositiveIntegerTextValue(readTrimmed('inbound_port'), i18n.t('settings.externalAccounts.validation.mailInboundPort')),
    inboundSecurity: requireMailSecurity(readTrimmed('inbound_security'), i18n.t('settings.externalAccounts.validation.mailInboundSecurity')),
    smtpHost: readRequiredTrimmedStringMessageValue(readTrimmed('smtp_host'), i18n.t('settings.externalAccounts.validation.mailSmtpHost')),
    smtpPort: readRequiredPositiveIntegerTextValue(readTrimmed('smtp_port'), i18n.t('settings.externalAccounts.validation.mailSmtpPort')),
    smtpSecurity: requireMailSecurity(readTrimmed('smtp_security'), i18n.t('settings.externalAccounts.validation.mailSmtpSecurity')),
    folderMapping: parseOptionalJsonStringRecordText(readTrimmed('folder_mapping'), i18n.t('settings.externalAccounts.validation.mailFolderMapping'))
});

const buildCalendarTransportPayload = (readTrimmed: (name: string) => string): CalendarAccountTransportWrite => ({
    caldavBaseUrl: requireAbsoluteHttpUrl(readTrimmed('caldav_base_url'), i18n.t('settings.externalAccounts.validation.calendarBaseUrl')),
    linkedMailAccountId: readTrimmed('linked_mail_account_id') || null,
    discoveredPrincipal: parseJsonObjectText(readTrimmed('discovered_principal'), i18n.t('settings.externalAccounts.validation.calendarDiscoveredPrincipal'))
});

export { buildCalendarTransportPayload, buildMailTransportPayload };
