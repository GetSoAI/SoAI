/* SoAI - Settings feature render state [frontend/assets/ts/features/settings/externalaccounts/renderState.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { renderEmptyState } from '@core/ui/emptyState.ts';
import { resolveSettingsCapabilityMessage, type SettingsCapabilityAvailability } from '@features/settings/capabilityAvailability.ts';
import { CALENDAR_AVAILABILITY_ID, CALENDAR_COUNT_ID, CALENDAR_LIST_ID, MAIL_AVAILABILITY_ID, MAIL_COUNT_ID, MAIL_LIST_ID, requireRoot } from '@features/settings/externalaccounts/dom.ts';
import { EXTERNAL_ACCOUNT_DESCRIPTORS, type ExternalAccountsDescriptorContext } from '@features/settings/externalaccounts/descriptors.ts';
import { patchKeyedRows } from '@features/settings/externalaccounts/rowPatching.ts';
import type { CalendarAccountEntry, MailAccountEntry } from '@core/api/contracts/externalAccountContracts.ts';
import type { ExternalAccountsManagerHost } from '@features/settings/externalaccounts/types.ts';

interface ExternalAccountsRenderedStateArguments {
    host: ExternalAccountsManagerHost;
    mailAccounts: MailAccountEntry[];
    calendarAccounts: CalendarAccountEntry[];
    mailAvailability: SettingsCapabilityAvailability;
    calendarAvailability: SettingsCapabilityAvailability;
}

const resolveEmptyListMarkup = (accountType: 'mail' | 'calendar'): string => {
    const message = accountType === 'mail' ? i18n.t('settings.externalAccounts.mail.empty') : i18n.t('settings.externalAccounts.calendar.empty');
    return renderEmptyState({ title: message, className: 'ui-empty-state--simple' }).html;
};

const updateAccountCount = (countElement: HTMLElement, count: number): void => {
    countElement.textContent = String(count);
    const badge = countElement.closest('.external-accounts-subgroup__count');
    if (!(badge instanceof HTMLElement)) {
        throw new Error('External accounts count badge is missing');
    }
    badge.hidden = count === 0;
};

const updateAvailability = (element: HTMLElement, availability: SettingsCapabilityAvailability): void => {
    const message = resolveSettingsCapabilityMessage(availability);
    element.textContent = message ?? '';
    element.hidden = message === null;
};

const syncExternalAccountsRenderedState = (inputArguments: ExternalAccountsRenderedStateArguments): void => {
    const root = requireRoot(inputArguments.host);
    const context: ExternalAccountsDescriptorContext = {
        mailAccounts: inputArguments.mailAccounts,
        linkedMailLabels: new Map(inputArguments.mailAccounts.map((account) => [account.accountId, account.label]))
    };
    patchKeyedRows(
        inputArguments.host.pageDom.requireHTMLElement(`#${MAIL_LIST_ID}`, root),
        inputArguments.mailAccounts.map((account) => ({ key: account.accountId, markup: EXTERNAL_ACCOUNT_DESCRIPTORS.mail.renderRow(account, context) })),
        resolveEmptyListMarkup('mail')
    );
    patchKeyedRows(
        inputArguments.host.pageDom.requireHTMLElement(`#${CALENDAR_LIST_ID}`, root),
        inputArguments.calendarAccounts.map((account) => ({ key: account.accountId, markup: EXTERNAL_ACCOUNT_DESCRIPTORS.calendar.renderRow(account, context) })),
        resolveEmptyListMarkup('calendar')
    );
    updateAccountCount(inputArguments.host.pageDom.requireHTMLElement(`#${MAIL_COUNT_ID}`, root), inputArguments.mailAccounts.length);
    updateAccountCount(inputArguments.host.pageDom.requireHTMLElement(`#${CALENDAR_COUNT_ID}`, root), inputArguments.calendarAccounts.length);
    updateAvailability(inputArguments.host.pageDom.requireHTMLElement(`#${MAIL_AVAILABILITY_ID}`, root), inputArguments.mailAvailability);
    updateAvailability(inputArguments.host.pageDom.requireHTMLElement(`#${CALENDAR_AVAILABILITY_ID}`, root), inputArguments.calendarAvailability);
    if (inputArguments.host.hasSearchQuery()) {
        inputArguments.host.filterSettings();
    }
};

export { syncExternalAccountsRenderedState };
