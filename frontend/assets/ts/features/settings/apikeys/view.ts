/* SoAI - Settings feature apikeys rendering [frontend/assets/ts/features/settings/apikeys/view.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { formatPositiveEpochMsWithFallback } from '@core/primitives/dateTime.ts';
import { renderAdminOnlyNotice } from '@core/settings/adminOnlyNotice.ts';
import { renderSection, renderSettingItem, renderSettingsRecordList, renderSettingsSubgroup, renderToggleControl } from '@core/settings/settingsMarkup.ts';
import { renderSettingsTitlebarAddButton } from '@core/settings/titlebarActions.ts';
import { renderEmptyState } from '@core/ui/emptyState.ts';
import { renderSettingsCapabilityNotice, type SettingsCapabilityAvailability } from '@features/settings/capabilityAvailability.ts';
import { API_KEYS_ACTION_CREATE, API_KEYS_ACTION_DELETE, API_KEYS_ACTION_DELETE_ALL, API_KEYS_ACTION_MANAGE_QUOTA, API_KEYS_ACTION_REVOKE, API_KEYS_ACTION_ROTATE } from '@features/settings/apikeys/constants.ts';
import { filterActiveApiKeys, filterVisibleApiKeys, hasRevokedApiKeys } from '@features/settings/apikeys/filters.ts';
import { renderApiKeyQuotaModeBadge, renderApiKeyQuotaSummary } from '@features/settings/apikeys/quotaSummaryView.ts';
import type { ApiKey, ApiKeysViewRenderHost } from '@features/settings/apikeys/types.ts';
import { getPreferenceStateLabels } from '@features/settings/preferenceStateLabels.ts';
import { resolveSettingsTokenBadgeClass, resolveSettingsTokenItemStateClass, resolveSettingsTokenStatus, resolveSettingsTokenStatusLabel } from '@features/settings/tokenflow/tokenListView.ts';

type ApiKeyActionOperation = 'limits' | 'rotate' | 'revoke' | 'delete';

const resolveApiKeyStatusLabel = (status: 'active' | 'revoked' | 'expired'): string => {
    return resolveSettingsTokenStatusLabel(status, {
        active: i18n.t('settings.apiKeys.keyItem.active'),
        revoked: i18n.t('settings.apiKeys.keyItem.revoked'),
        expired: i18n.t('settings.apiKeys.keyItem.expired')
    });
};

const resolveApiKeyActionLabel = (operation: ApiKeyActionOperation): string => {
    switch (operation) {
        case 'limits':
            return i18n.t('settings.apiKeys.actions.limits');
        case 'rotate':
            return i18n.t('settings.apiKeys.actions.rotate');
        case 'revoke':
            return i18n.t('settings.apiKeys.actions.revoke');
        case 'delete':
            return i18n.t('settings.apiKeys.actions.delete');
        default: {
            const exhaustive: never = operation;
            throw new Error(`Unhandled API key action: ${exhaustive}`);
        }
    }
};

const renderApiKeyItem = (host: ApiKeysViewRenderHost, key: ApiKey): string => {
    const isRevoked = Boolean(key.revoked);
    const status = resolveSettingsTokenStatus(isRevoked, key.expiresAtMs);
    const badgeClass = resolveSettingsTokenBadgeClass(status);
    const badge = `<span class="settings-record-badge settings-record-badge--${badgeClass}">${host.api.sanitizeHtml(resolveApiKeyStatusLabel(status))}</span>`;
    const quotaModeBadge = isRevoked ? '' : renderApiKeyQuotaModeBadge(host, key.keyId).html;

    const keyIdAttribute = host.api.sanitizeAttribute(key.keyId);
    const actionOperations: ReadonlyArray<{ operation: ApiKeyActionOperation; actionId: string }> = [
        { operation: 'limits', actionId: API_KEYS_ACTION_MANAGE_QUOTA },
        { operation: 'rotate', actionId: API_KEYS_ACTION_ROTATE },
        { operation: 'revoke', actionId: API_KEYS_ACTION_REVOKE },
        { operation: 'delete', actionId: API_KEYS_ACTION_DELETE }
    ];
    const actions = isRevoked
        ? (() => {
              const deleteLabel = resolveApiKeyActionLabel('delete');
              const deleteLabelAttr = host.api.sanitizeAttribute(deleteLabel);
              return `<button type="button" class="ui-button ui-button--sm ui-variant-danger api-key-delete-btn" data-action="${API_KEYS_ACTION_DELETE}" data-key-id="${keyIdAttribute}" aria-label="${deleteLabelAttr}" data-tooltip="${deleteLabelAttr}">${host.api.sanitizeHtml(deleteLabel)}</button>`;
          })()
        : actionOperations
              .map(({ operation, actionId }): string => {
                  const label = resolveApiKeyActionLabel(operation);
                  const labelAttr = host.api.sanitizeAttribute(label);
                  const variantClass = operation === 'delete' ? 'ui-variant-danger' : operation === 'revoke' ? 'ui-variant-warning' : operation === 'limits' ? 'ui-variant-primary' : 'ui-variant-neutral';
                  return `<button type="button" class="ui-button ui-button--sm ${variantClass} api-key-${operation}-btn" data-action="${actionId}" data-key-id="${keyIdAttribute}" aria-label="${labelAttr}" data-tooltip="${labelAttr}">${host.api.sanitizeHtml(label)}</button>`;
              })
              .join('');

    const labelDisplay = key.label ? host.api.sanitizeHtml(key.label) : `<em>${host.api.sanitizeHtml(i18n.t('settings.apiKeys.keyItem.prefix'))}</em>`;

    const rotationWarning = key.rotationDue ? `<span class="api-key-rotation-warning">${host.api.sanitizeHtml(i18n.t('settings.apiKeys.keyItem.rotationDue'))}</span>` : '';

    const createdDate = formatPositiveEpochMsWithFallback(key.createdAtMs, i18n.t('common.notAvailable'));
    const lastUsedDate = formatPositiveEpochMsWithFallback(key.lastUsedAtMs, i18n.t('settings.apiKeys.keyItem.never'));
    const expiresDate = formatPositiveEpochMsWithFallback(key.expiresAtMs, i18n.t('settings.apiKeys.keyItem.noExpiry'));
    const scopes = host.api.sanitizeHtml((key.scopes || ['OPENAI_API']).join(', '));
    const quotaSummary = isRevoked ? '' : renderApiKeyQuotaSummary(host, key.keyId).html;
    const requestCount = i18n.formatNumber(key.requestCount ?? 0);

    return `<div class="settings-record-item ${resolveSettingsTokenItemStateClass(status)}" data-key-id="${keyIdAttribute}"><div class="settings-record-info api-key-info"><div class="settings-record-header api-key-header"><span class="settings-record-label api-key-label">${labelDisplay}</span>${badge}${quotaModeBadge}${rotationWarning}</div><div class="api-key-prefix"><code>${host.api.sanitizeHtml(key.prefix || '')}...</code></div><div class="settings-record-meta api-key-meta"><span>${host.api.sanitizeHtml(i18n.t('settings.apiKeys.keyItem.scopes'))}: ${scopes}</span><span>${host.api.sanitizeHtml(i18n.t('settings.apiKeys.keyItem.created'))}: ${host.api.sanitizeHtml(createdDate)}</span><span>${host.api.sanitizeHtml(i18n.t('settings.apiKeys.keyItem.last_used'))}: ${host.api.sanitizeHtml(lastUsedDate)}</span><span>${host.api.sanitizeHtml(i18n.t('settings.apiKeys.keyItem.expires'))}: ${host.api.sanitizeHtml(expiresDate)}</span><span>${host.api.sanitizeHtml(i18n.t('settings.apiKeys.keyItem.requests'))}: ${host.api.sanitizeHtml(requestCount)}</span></div>${quotaSummary}</div><div class="settings-record-actions api-key-actions">${actions}</div></div>`;
};

const renderApiKeysSection = (host: ApiKeysViewRenderHost, availability: SettingsCapabilityAvailability): string => {
    if (!host.api.isAdmin()) {
        return renderSection({
            title: i18n.t('settings.apiKeys.sectionTitle'),
            description: i18n.t('settings.apiKeys.sectionDescription'),
            className: 'settings-section--api-keys',
            content: renderAdminOnlyNotice(i18n.t('settings.adminOnlyRequired')).html
        });
    }

    const preferenceLabels = getPreferenceStateLabels();
    const allKeys = host.state.getApiKeys();
    const showRevoked = host.state.getShowRevokedKeys();
    const activeKeys = filterActiveApiKeys(allKeys);
    const visibleKeys = filterVisibleApiKeys(allKeys, showRevoked);
    const showRevokedSetting = hasRevokedApiKeys(allKeys)
        ? renderSettingItem({
              label: i18n.t('settings.apiKeys.showRevoked'),
              help: i18n.t('settings.apiKeys.showRevokedHelp'),
              control: renderToggleControl({
                  id: 'api-keys-show-revoked',
                  checked: showRevoked,
                  labels: preferenceLabels
              })
          })
        : '';
    const deleteAllLabel = i18n.t('settings.apiKeys.deleteAll');
    const deleteAllLabelAttr = host.api.sanitizeAttribute(deleteAllLabel);
    const createLabel = i18n.t('settings.apiKeys.createKey');
    const createBtn = renderSettingsTitlebarAddButton({ id: 'api-keys-create-btn', action: API_KEYS_ACTION_CREATE, label: createLabel });
    const actionsBar = activeKeys.length > 1 ? `<div class="api-keys-actions-bar"><button type="button" id="api-keys-delete-all-btn" data-action="${API_KEYS_ACTION_DELETE_ALL}" class="ui-button ui-button--sm ui-variant-danger" aria-label="${deleteAllLabelAttr}" data-tooltip="${deleteAllLabelAttr}">${deleteAllLabel}</button></div>` : '';

    const listGroup = renderSettingsSubgroup({
        title: i18n.t('settings.apiKeys.listTitle'),
        description: i18n.t('settings.apiKeys.listDescription'),
        content: renderSettingsRecordList({
            id: 'api-keys-list',
            items: visibleKeys.map((key) => renderApiKeyItem(host, key)),
            empty: renderEmptyState({ title: i18n.t('settings.apiKeys.noKeys'), className: 'ui-empty-state--simple' }).html
        })
    });

    return renderSection({
        title: i18n.t('settings.apiKeys.sectionTitle'),
        description: i18n.t('settings.apiKeys.sectionDescription'),
        className: 'settings-section--api-keys',
        trailing: createBtn,
        content: `${renderSettingsCapabilityNotice(availability)}${listGroup}${showRevokedSetting}${actionsBar}`
    });
};

export { renderApiKeysSection };
