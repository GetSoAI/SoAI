/* SoAI - Settings feature external accounts rendering [frontend/assets/ts/features/settings/externalaccounts/view.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { renderSection, renderSettingsRecordList, renderSettingsSubgroup } from '@core/settings/settingsMarkup.ts';
import { renderSettingsTitlebarAddButton } from '@core/settings/titlebarActions.ts';
import { securityApi } from '@core/security/public.ts';
import { renderEmptyState } from '@core/ui/emptyState.ts';
import { resolveSettingsCapabilityMessage, type SettingsCapabilityAvailability } from '@features/settings/capabilityAvailability.ts';
import { EXTERNAL_ACCOUNTS_ACTION_ADD } from '@features/settings/externalaccounts/actionIds.ts';
import { CALENDAR_AVAILABILITY_ID, CALENDAR_COUNT_ID, CALENDAR_LIST_ID, EXTERNAL_ACCOUNTS_ADD_BUTTON_ID, MAIL_AVAILABILITY_ID, MAIL_COUNT_ID, MAIL_LIST_ID } from '@features/settings/externalaccounts/dom.ts';

const renderAddButton = (): string => {
    const label = i18n.t('settings.externalAccounts.shared.actions.add');
    return renderSettingsTitlebarAddButton({ id: EXTERNAL_ACCOUNTS_ADD_BUTTON_ID, action: EXTERNAL_ACCOUNTS_ACTION_ADD, label });
};

const renderSubgroup = (inputArguments: { availability: SettingsCapabilityAvailability; availabilityId: string; countId: string; listId: string; title: string; description: string; emptyMessage: string }): string => {
    const availabilityMessage = resolveSettingsCapabilityMessage(inputArguments.availability);
    return renderSettingsSubgroup({
        title: securityApi.escapeHtml(inputArguments.title),
        description: securityApi.escapeHtml(inputArguments.description),
        trailing: `<span class="settings-record-badge settings-record-badge--neutral external-accounts-subgroup__count" hidden><span id="${securityApi.escapeAttribute(inputArguments.countId)}">0</span><span>${securityApi.escapeHtml(i18n.t('common.total'))}</span></span>`,
        className: 'external-accounts-subgroup',
        content: `<div id="${securityApi.escapeAttribute(inputArguments.availabilityId)}" class="settings-card-surface settings-capability-notice" role="status"${availabilityMessage === null ? ' hidden' : ''}>${securityApi.escapeHtml(availabilityMessage ?? '')}</div>${renderSettingsRecordList({
            id: inputArguments.listId,
            items: [],
            empty: renderEmptyState({ title: inputArguments.emptyMessage, className: 'ui-empty-state--simple' }).html
        })}`
    });
};

const renderExternalAccountsSection = (mailAvailability: SettingsCapabilityAvailability, calendarAvailability: SettingsCapabilityAvailability): string => {
    return renderSection({
        title: i18n.t('settings.externalAccounts.sectionTitle'),
        description: i18n.t('settings.externalAccounts.overviewDescription'),
        className: 'settings-section--external-accounts',
        trailing: renderAddButton(),
        content: `${renderSubgroup({
            availability: mailAvailability,
            availabilityId: MAIL_AVAILABILITY_ID,
            countId: MAIL_COUNT_ID,
            listId: MAIL_LIST_ID,
            title: i18n.t('settings.externalAccounts.mail.listTitle'),
            description: i18n.t('settings.externalAccounts.mail.sectionDescription'),
            emptyMessage: i18n.t('settings.externalAccounts.mail.empty')
        })}${renderSubgroup({
            availability: calendarAvailability,
            availabilityId: CALENDAR_AVAILABILITY_ID,
            countId: CALENDAR_COUNT_ID,
            listId: CALENDAR_LIST_ID,
            title: i18n.t('settings.externalAccounts.calendar.listTitle'),
            description: i18n.t('settings.externalAccounts.calendar.sectionDescription'),
            emptyMessage: i18n.t('settings.externalAccounts.calendar.empty')
        })}`
    });
};

export { renderExternalAccountsSection };
