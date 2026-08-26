/* SoAI - Settings feature row details [frontend/assets/ts/features/settings/externalaccounts/rowDetails.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { formatNullableEpochMsMinuteWithFallback } from '@core/primitives/dateTime.ts';
import { securityApi } from '@core/security/public.ts';
import { EXTERNAL_ACCOUNTS_ACTION_MANAGE } from '@features/settings/externalaccounts/actionIds.ts';
import { resolveExternalAccountOauthStatusLabel } from '@features/settings/externalaccounts/oauthPresentation.ts';
import type { CalendarAccountEntry, ExternalAccountEntry, MailAccountEntry } from '@core/api/contracts/externalAccountContracts.ts';
import type { OauthStatus } from '@core/api/contracts/oauthContracts.ts';
import { isSettingsOauthWarningStatus } from '@features/settings/oauthValues.ts';

const formatTimestamp = (timestampMs: number | null): string => formatNullableEpochMsMinuteWithFallback(timestampMs, i18n.t('common.notAvailable'));

const renderBadge = (value: string, tone: 'settings-record-badge--neutral' | 'settings-record-badge--active' | 'settings-record-badge--warning' | 'settings-record-badge--danger' = 'settings-record-badge--neutral'): string => `<span class="settings-record-badge ${securityApi.escapeAttribute(tone)}">${securityApi.escapeHtml(value)}</span>`;

const renderActionButton = (inputArguments: { actionId: string; label: string; type: 'mail' | 'calendar'; accountId: string; tone?: 'default' | 'danger' }): string => `<button type="button" class="ui-button ui-button--sm ${inputArguments.tone === 'danger' ? 'ui-variant-danger' : 'ui-variant-neutral'}" data-action="${securityApi.escapeAttribute(inputArguments.actionId)}" data-account-type="${securityApi.escapeAttribute(inputArguments.type)}" data-account-id="${securityApi.escapeAttribute(inputArguments.accountId)}" aria-label="${securityApi.escapeAttribute(inputArguments.label)}" data-tooltip="${securityApi.escapeAttribute(inputArguments.label)}">${securityApi.escapeHtml(inputArguments.label)}</button>`;

const resolveOauthBadgeTone = (status: OauthStatus): 'settings-record-badge--neutral' | 'settings-record-badge--active' | 'settings-record-badge--warning' | 'settings-record-badge--danger' => {
    if (status === 'ready') {
        return 'settings-record-badge--active';
    }
    if (isSettingsOauthWarningStatus(status)) {
        return 'settings-record-badge--warning';
    }
    if (status === 'error') {
        return 'settings-record-badge--danger';
    }
    return 'settings-record-badge--neutral';
};

const renderAccountSyncBadge = (account: ExternalAccountEntry): string | null => {
    if (account.sync.lastSyncError) {
        return renderBadge(i18n.t('settings.externalAccounts.shared.syncError'), 'settings-record-badge--danger');
    }
    if (account.supportedActions.includes('sync')) {
        return renderBadge(i18n.t('settings.externalAccounts.shared.syncReady'), 'settings-record-badge--active');
    }
    return null;
};

const buildActionButtons = (account: ExternalAccountEntry): string[] => {
    return [renderActionButton({ actionId: EXTERNAL_ACCOUNTS_ACTION_MANAGE, label: i18n.t('settings.externalAccounts.shared.actions.manage'), type: account.accountType, accountId: account.accountId })];
};

const buildBaseBadges = (account: ExternalAccountEntry, primaryBadge: string): string[] => {
    const badges = [renderBadge(primaryBadge, 'settings-record-badge--neutral'), renderBadge(account.auth.type === 'oauth2' ? i18n.t('settings.externalAccounts.shared.auth.oauth2') : i18n.t('settings.externalAccounts.shared.auth.password'))];
    const syncBadge = renderAccountSyncBadge(account);
    if (syncBadge !== null) {
        badges.push(syncBadge);
    }
    if (account.auth.type === 'oauth2' && account.auth.oauth.status !== 'none') {
        badges.push(renderBadge(resolveExternalAccountOauthStatusLabel(account.auth.oauth.status), resolveOauthBadgeTone(account.auth.oauth.status)));
    }
    return badges;
};

const renderAccountRow = (account: ExternalAccountEntry, badges: string[], meta: string[]): string => {
    const errorMarkup = account.sync.lastSyncError ? `<div class="settings-record-description settings-record-error">${i18n.t('settings.externalAccounts.shared.lastError')}: ${securityApi.escapeHtml(account.sync.lastSyncError)}</div>` : '';
    return `<div class="settings-record-item" data-account-id="${securityApi.escapeAttribute(account.accountId)}"><div class="settings-record-info"><div class="settings-record-header"><span class="settings-record-label">${securityApi.escapeHtml(account.label)}</span><div class="settings-record-badges">${badges.join('')}</div></div><div class="settings-record-meta">${meta.map((entry) => `<span>${entry}</span>`).join('')}</div>${errorMarkup}</div><div class="settings-record-actions">${buildActionButtons(account).join('')}</div></div>`;
};

const renderMailAccountRow = (account: MailAccountEntry): string => {
    return renderAccountRow(account, buildBaseBadges(account, account.transport.protocol.toUpperCase()), [`${i18n.t('settings.externalAccounts.shared.username')}: ${securityApi.escapeHtml(account.username ?? i18n.t('common.notAvailable'))}`, `${i18n.t('settings.externalAccounts.mail.inboundLabel')}: ${securityApi.escapeHtml(account.transport.inbound.host ?? i18n.t('common.notAvailable'))}:${securityApi.escapeHtml(account.transport.inbound.port ?? i18n.t('common.notAvailable'))}`, `${i18n.t('settings.externalAccounts.mail.smtpLabel')}: ${securityApi.escapeHtml(account.transport.outbound.host ?? i18n.t('common.notAvailable'))}:${securityApi.escapeHtml(account.transport.outbound.port ?? i18n.t('common.notAvailable'))}`, `${i18n.t('settings.externalAccounts.shared.lastSync')}: ${securityApi.escapeHtml(formatTimestamp(account.sync.lastSyncAtMs))}`]);
};

const renderCalendarAccountRow = (account: CalendarAccountEntry, linkedMailLabel: string | null): string => {
    const linkedMailValue = linkedMailLabel ?? (account.transport.linkedMailAccountId !== null ? i18n.t('common.notAvailable') : i18n.t('common.none'));
    return renderAccountRow(account, buildBaseBadges(account, i18n.t('settings.externalAccounts.calendar.badge')), [`${i18n.t('settings.externalAccounts.shared.username')}: ${securityApi.escapeHtml(account.username ?? i18n.t('common.notAvailable'))}`, `${i18n.t('settings.externalAccounts.calendar.caldavBaseUrl')}: ${securityApi.escapeHtml(account.transport.caldavBaseUrl ?? i18n.t('common.notAvailable'))}`, `${i18n.t('settings.externalAccounts.calendar.linkedMailAccount')}: ${securityApi.escapeHtml(linkedMailValue)}`, `${i18n.t('settings.externalAccounts.shared.lastSync')}: ${securityApi.escapeHtml(formatTimestamp(account.sync.lastSyncAtMs))}`]);
};

export { renderCalendarAccountRow, renderMailAccountRow };
