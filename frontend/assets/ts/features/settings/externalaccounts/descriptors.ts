/* SoAI - Settings feature descriptors [frontend/assets/ts/features/settings/externalaccounts/descriptors.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import type { CalendarAccountEntry, CalendarAccountWriteRequest, ExternalAccountType, MailAccountEntry, MailAccountWriteRequest } from '@core/api/contracts/externalAccountContracts.ts';
import type { ExternalAccountsEndpoints } from '@core/api/endpoints/webuiExternalAccounts.ts';
import { CALENDAR_LIST_ID, MAIL_LIST_ID } from '@features/settings/externalaccounts/dom.ts';
import type { ExternalAccountsManagerHost, FormMode } from '@features/settings/externalaccounts/types.ts';
import { buildCalendarAccountPayload, buildMailAccountPayload } from '@features/settings/externalaccounts/forms.ts';
import { renderCalendarAccountRow, renderMailAccountRow } from '@features/settings/externalaccounts/rowDetails.ts';

interface ExternalAccountsDescriptorContext {
    mailAccounts: MailAccountEntry[];
    linkedMailLabels: Map<string, string>;
}

interface ExternalAccountDescriptorMessages {
    createSuccess: () => string;
    updateSuccess: () => string;
    testSuccess: () => string;
    syncSuccess: () => string;
    oauthConnectSuccess: () => string;
    oauthClearSuccess: () => string;
    oauthFailed: () => string;
    deleteSuccess: () => string;
    deleteConfirmTitle: () => string;
    deleteConfirmMessage: () => string;
}

interface ExternalAccountDescriptor<AccountType extends ExternalAccountType, Account, WriteRequest> {
    type: AccountType;
    listId: string;
    messages: ExternalAccountDescriptorMessages;
    api: (host: ExternalAccountsManagerHost) => ExternalAccountsEndpoints<Account, WriteRequest>;
    buildPayload: (inputArguments: { form: HTMLFormElement; mode: FormMode; currentAccount: Account | null }) => WriteRequest;
    renderRow: (account: Account, context: ExternalAccountsDescriptorContext) => string;
}

const MAIL_DESCRIPTOR: ExternalAccountDescriptor<'mail', MailAccountEntry, MailAccountWriteRequest> = {
    type: 'mail',
    listId: MAIL_LIST_ID,
    messages: {
        createSuccess: () => i18n.t('settings.externalAccounts.mail.notifications.created'),
        updateSuccess: () => i18n.t('settings.externalAccounts.mail.notifications.updated'),
        testSuccess: () => i18n.t('settings.externalAccounts.mail.notifications.tested'),
        syncSuccess: () => i18n.t('settings.externalAccounts.mail.notifications.synced'),
        oauthConnectSuccess: () => i18n.t('settings.externalAccounts.mail.notifications.oauthConnected'),
        oauthClearSuccess: () => i18n.t('settings.externalAccounts.mail.notifications.oauthCleared'),
        oauthFailed: () => i18n.t('settings.externalAccounts.mail.notifications.oauthFailed'),
        deleteSuccess: () => i18n.t('settings.externalAccounts.mail.notifications.deleted'),
        deleteConfirmTitle: () => i18n.t('settings.externalAccounts.mail.confirmDelete.title'),
        deleteConfirmMessage: () => i18n.t('settings.externalAccounts.mail.confirmDelete.message')
    },
    api: (host) => host.api.webui.mail.accounts,
    buildPayload: buildMailAccountPayload,
    renderRow: (account) => renderMailAccountRow(account)
};

const CALENDAR_DESCRIPTOR: ExternalAccountDescriptor<'calendar', CalendarAccountEntry, CalendarAccountWriteRequest> = {
    type: 'calendar',
    listId: CALENDAR_LIST_ID,
    messages: {
        createSuccess: () => i18n.t('settings.externalAccounts.calendar.notifications.created'),
        updateSuccess: () => i18n.t('settings.externalAccounts.calendar.notifications.updated'),
        testSuccess: () => i18n.t('settings.externalAccounts.calendar.notifications.tested'),
        syncSuccess: () => i18n.t('settings.externalAccounts.calendar.notifications.synced'),
        oauthConnectSuccess: () => i18n.t('settings.externalAccounts.calendar.notifications.oauthConnected'),
        oauthClearSuccess: () => i18n.t('settings.externalAccounts.calendar.notifications.oauthCleared'),
        oauthFailed: () => i18n.t('settings.externalAccounts.calendar.notifications.oauthFailed'),
        deleteSuccess: () => i18n.t('settings.externalAccounts.calendar.notifications.deleted'),
        deleteConfirmTitle: () => i18n.t('settings.externalAccounts.calendar.confirmDelete.title'),
        deleteConfirmMessage: () => i18n.t('settings.externalAccounts.calendar.confirmDelete.message')
    },
    api: (host) => host.api.webui.calendar.accounts,
    buildPayload: buildCalendarAccountPayload,
    renderRow: (account, context) => renderCalendarAccountRow(account, context.linkedMailLabels.get(account.transport.linkedMailAccountId ?? '') ?? null)
};

const EXTERNAL_ACCOUNT_DESCRIPTORS = {
    mail: MAIL_DESCRIPTOR,
    calendar: CALENDAR_DESCRIPTOR
};

export { CALENDAR_DESCRIPTOR, EXTERNAL_ACCOUNT_DESCRIPTORS, MAIL_DESCRIPTOR };
export type { ExternalAccountDescriptor, ExternalAccountDescriptorMessages, ExternalAccountsDescriptorContext };
