/* SoAI - Messaging account list rendering [frontend/assets/ts/features/settings/messaging/view.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { MessagingAccount } from '@core/api/contracts/messagingAccountContracts.ts';
import { i18n } from '@core/i18n/index.ts';
import { securityApi } from '@core/security/public.ts';
import { renderSection, renderSettingsRecordList, renderSettingsSubgroup } from '@core/settings/settingsMarkup.ts';
import { renderSettingsTitlebarAddButton } from '@core/settings/titlebarActions.ts';
import { renderEmptyState } from '@core/ui/emptyState.ts';
import { MESSAGING_ACTION_ADD_ACCOUNT, MESSAGING_ACTION_DISABLE_ACCOUNT, MESSAGING_ACTION_EDIT_ACCOUNT, MESSAGING_ACTION_ENABLE_ACCOUNT, MESSAGING_ACTION_REMOVE_ACCOUNT } from '@features/settings/messaging/constants.ts';
import { resolveMessagingHealthLabel, resolveMessagingProviderDescription, resolveMessagingProviderTitle, resolveMessagingStatusLabel } from '@features/settings/messaging/labels.ts';

const renderAccountActions = (account: MessagingAccount): string => {
    const accountId = securityApi.escapeAttribute(account.accountId);
    const edit = i18n.t('settings.messaging.accounts.actions.edit');
    const remove = i18n.t('settings.messaging.accounts.actions.remove');
    const enabled = account.lifecycleState === 'enabled' || account.lifecycleState === 'degraded';
    const toggleAction = enabled ? MESSAGING_ACTION_DISABLE_ACCOUNT : MESSAGING_ACTION_ENABLE_ACCOUNT;
    const toggleLabel = enabled ? i18n.t('settings.messaging.accounts.actions.disable') : i18n.t('settings.messaging.accounts.actions.enable');
    const disabled = account.lifecycleState === 'deleting' ? ' disabled' : '';
    return `<div class="settings-record-actions"><button type="button" class="ui-button ui-button--sm ui-variant-warning" data-action="${MESSAGING_ACTION_EDIT_ACCOUNT}" data-account-id="${accountId}" aria-label="${edit}" data-tooltip="${edit}"${disabled}>${edit}</button><button type="button" class="ui-button ui-button--sm" data-action="${toggleAction}" data-account-id="${accountId}" aria-label="${toggleLabel}" data-tooltip="${toggleLabel}"${disabled}>${toggleLabel}</button><button type="button" class="ui-button ui-button--sm ui-variant-danger" data-action="${MESSAGING_ACTION_REMOVE_ACCOUNT}" data-account-id="${accountId}" aria-label="${remove}" data-tooltip="${remove}"${disabled}>${remove}</button></div>`;
};

const renderAccountCard = (account: MessagingAccount): string => {
    const state = account.lifecycleState;
    const badgeClass = state === 'enabled' ? 'settings-record-badge--active' : state === 'degraded' || state === 'deleting' ? 'settings-record-badge--warning' : 'settings-record-badge--inactive';
    const principal = account.principalLabel ?? account.principalId;
    const health = resolveMessagingHealthLabel(account);
    const senderAccess = account.acceptMessagesFromAnyone ? i18n.t('settings.messaging.accounts.anySender') : i18n.t('settings.messaging.accounts.authorizedSenderCount', { count: account.authorizedSenders.length });
    return `<div class="settings-record-item messaging-account-item" data-account-id="${securityApi.escapeAttribute(account.accountId)}"><div class="settings-record-info"><div class="settings-record-header"><span class="settings-record-label">${securityApi.escapeHtml(account.label)}</span><span class="settings-record-badge ${badgeClass}">${resolveMessagingStatusLabel(state)}</span></div><div class="settings-record-description">${resolveMessagingProviderTitle(account.platform)} · ${securityApi.escapeHtml(principal)}</div><div class="settings-record-meta"><span>${resolveMessagingProviderDescription(account.platform)}</span><span>${senderAccess}</span><span>${health}</span></div></div>${renderAccountActions(account)}</div>`;
};

const renderMessagingSection = (accounts: readonly MessagingAccount[]): string => {
    const content = renderSettingsSubgroup({
        title: i18n.t('settings.messaging.accounts.title'),
        description: i18n.t('settings.messaging.accounts.description'),
        content: renderSettingsRecordList({ id: 'messaging-accounts-list', items: accounts.map(renderAccountCard), empty: renderEmptyState({ title: i18n.t('settings.messaging.accounts.empty'), className: 'ui-empty-state--simple' }).html, className: 'messaging-account-list' })
    });
    return renderSection({
        title: i18n.t('settings.messaging.sectionTitle'),
        description: i18n.t('settings.messaging.sectionDescription'),
        className: 'settings-section--messaging',
        trailing: renderSettingsTitlebarAddButton({ id: 'messaging-add-account-btn', action: MESSAGING_ACTION_ADD_ACCOUNT, label: i18n.t('settings.messaging.accounts.actions.add') }),
        content
    });
};

export { renderMessagingSection };
