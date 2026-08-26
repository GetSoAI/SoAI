/* SoAI - Settings feature quota modal markup [frontend/assets/ts/features/settings/apikeys/quotaModalMarkup.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrustedUiHtml, type TrustedHtml } from '@core/security/public.ts';
import { i18n } from '@core/i18n/index.ts';
import { renderModalFooterActionButton, renderModalFooterCloseButton } from '@core/modals/footerButtons.ts';
import { renderDynamicSplitModalFooterContent } from '@core/modals/scaffold.ts';
import { modalUiId } from '@core/modals/uiIds.ts';
import type { ApiKey, ApiKeyQuotaSummary } from '@core/settings/contracts.ts';
import { renderSettingItem, renderSettingsGroup } from '@core/settings/settingsMarkup.ts';
import { renderEmptyState } from '@core/ui/emptyState.ts';
import { renderStandardDropdownSelectControl } from '@core/ui/dropdown/selectControl.ts';
import { QUOTA_WINDOWS, renderQuotaWindowStatus } from '@features/settings/apikeys/quotaPresentation.ts';
import { serverEpochMs } from '@core/time/clock.ts';
import type { ApiKeysManagerHost } from '@features/settings/apikeys/types.ts';

const resolveQuotaModeLabel = (mode: 'none' | 'tokens' | 'requests'): string => {
    switch (mode) {
        case 'none':
            return i18n.t('settings.apiKeys.quota.mode.none');
        case 'tokens':
            return i18n.t('settings.apiKeys.quota.mode.tokens');
        case 'requests':
            return i18n.t('settings.apiKeys.quota.mode.requests');
        default: {
            const exhaustive: never = mode;
            throw new Error(`Unhandled quota mode: ${exhaustive}`);
        }
    }
};

const renderApiKeyQuotaStatusPreview = (host: ApiKeysManagerHost, summary: ApiKeyQuotaSummary): TrustedHtml => {
    const unit = summary.status.unit;
    if (unit !== 'tokens' && unit !== 'requests') {
        return renderEmptyState({ title: i18n.t('settings.apiKeys.quota.noneConfigured'), className: 'ui-empty-state--simple' });
    }
    const nowTs = serverEpochMs();
    const blocks = QUOTA_WINDOWS.map((windowName) => renderQuotaWindowStatus(host.api, summary.status, windowName, nowTs))
        .filter(Boolean)
        .join('');
    return blocks ? toTrustedUiHtml(`<div class="api-key-quota-grid">${blocks}</div>`) : renderEmptyState({ title: i18n.t('settings.apiKeys.quota.noneConfigured'), className: 'ui-empty-state--simple' });
};

interface QuotaModalUsers {
    users: ReadonlyArray<{ id: number; username: string }>;
    assignedUserId: number | null;
}

const buildApiKeyQuotaModalBody = (host: ApiKeysManagerHost, key: ApiKey, summary: ApiKeyQuotaSummary, modalId: string, userAssignment: QuotaModalUsers | null): TrustedHtml => {
    const modeValue = summary.config.mode;
    type QuotaMode = 'none' | 'tokens' | 'requests';
    const quotaModes: QuotaMode[] = ['none', 'tokens', 'requests'];
    const modeOptions = quotaModes
        .map((mode) => {
            const label = resolveQuotaModeLabel(mode);
            const selected = mode === modeValue ? ' selected' : '';
            return `<option value="${mode}"${selected}>${host.api.sanitizeHtml(label)}</option>`;
        })
        .join('');

    const hourlyLimitValue = summary.config.hourly?.limitUnits ?? '';
    const hourlyWindowValue = summary.config.hourly?.windowHours ?? '';
    const dailyLimitValue = summary.config.daily?.limitUnits ?? '';
    const weeklyLimitValue = summary.config.weekly?.limitUnits ?? '';
    const monthlyLimitValue = summary.config.monthly?.limitUnits ?? '';
    const limitPlaceholder = i18n.t('settings.apiKeys.quota.modal.unlimitedPlaceholder');
    const windowHoursPlaceholder = i18n.t('settings.apiKeys.quota.modal.windowHoursPlaceholder');

    const keyLabel = key.label ? host.api.sanitizeHtml(key.label) : `<em>${i18n.t('settings.apiKeys.keyItem.prefix')}</em>`;
    const keyPrefix = host.api.sanitizeHtml(key.prefix || '');
    const usagePreview = renderApiKeyQuotaStatusPreview(host, summary).html;
    const notice = `<p class="setting-help api-key-quota-modal-note">${i18n.t('settings.apiKeys.quota.modal.saveResetsUsage')}</p>`;

    const userAssignmentItem = userAssignment
        ? (() => {
              const noneLabel = i18n.t('settings.apiKeys.quota.modal.assignedUserNone');
              const userOptions = [`<option value="">${host.api.sanitizeHtml(noneLabel)}</option>`]
                  .concat(
                      userAssignment.users.map((user) => {
                          const selected = user.id === userAssignment.assignedUserId ? ' selected' : '';
                          return `<option value="${host.api.sanitizeAttribute(user.id)}"${selected}>${host.api.sanitizeHtml(user.username)}</option>`;
                      })
                  )
                  .join('');
              return renderSettingItem({
                  label: i18n.t('settings.apiKeys.quota.modal.assignedUserLabel'),
                  help: i18n.t('settings.apiKeys.quota.modal.assignedUserHelp'),
                  control: renderStandardDropdownSelectControl(`<select id="${modalUiId(modalId, 'assigned-user')}" class="setting-input setting-input--wide">${userOptions}</select>`),
                  className: 'full-width'
              });
          })()
        : null;

    return toTrustedUiHtml(
        `<div class="api-key-quota-modal"><div class="api-key-quota-modal-key"><div class="api-key-quota-modal-key-header"><span class="api-key-label">${keyLabel}</span><span class="api-key-prefix"><code>${keyPrefix}...</code></span></div></div>${notice}<div class="api-key-quota-modal-status">${usagePreview}</div>${renderSettingsGroup([
            ...(userAssignmentItem ? [userAssignmentItem] : []),
            renderSettingItem({
                label: i18n.t('settings.apiKeys.quota.modal.modeLabel'),
                help: i18n.t('settings.apiKeys.quota.modal.modeHelp'),
                control: renderStandardDropdownSelectControl(`<select id="${modalUiId(modalId, 'mode')}" class="setting-input setting-input--wide setting-input--full">${modeOptions}</select>`),
                className: 'full-width'
            }),
            renderSettingItem({
                label: i18n.t('settings.apiKeys.quota.windows.hourly'),
                help: i18n.t('settings.apiKeys.quota.modal.hourlyHelp'),
                control: `<div class="api-key-quota-modal-hourly"><input id="${modalUiId(modalId, 'hourly-limit')}" type="number" min="1" step="1" class="setting-input setting-input--full" value="${hourlyLimitValue}" placeholder="${host.api.sanitizeAttribute(limitPlaceholder)}"><input id="${modalUiId(modalId, 'hourly-window')}" type="number" min="1" step="1" class="setting-input setting-input--full" value="${hourlyWindowValue}" placeholder="${host.api.sanitizeAttribute(windowHoursPlaceholder)}"></div>`,
                className: 'api-key-quota-modal-hourly-item'
            }),
            renderSettingItem({
                label: i18n.t('settings.apiKeys.quota.windows.daily'),
                help: i18n.t('settings.apiKeys.quota.modal.dailyHelp'),
                control: `<input id="${modalUiId(modalId, 'daily-limit')}" type="number" min="1" step="1" class="setting-input setting-input--wide setting-input--full" value="${dailyLimitValue}" placeholder="${host.api.sanitizeAttribute(limitPlaceholder)}">`
            }),
            renderSettingItem({
                label: i18n.t('settings.apiKeys.quota.windows.weekly'),
                help: i18n.t('settings.apiKeys.quota.modal.weeklyHelp'),
                control: `<input id="${modalUiId(modalId, 'weekly-limit')}" type="number" min="1" step="1" class="setting-input setting-input--wide setting-input--full" value="${weeklyLimitValue}" placeholder="${host.api.sanitizeAttribute(limitPlaceholder)}">`
            }),
            renderSettingItem({
                label: i18n.t('settings.apiKeys.quota.windows.monthly'),
                help: i18n.t('settings.apiKeys.quota.modal.monthlyHelp'),
                control: `<input id="${modalUiId(modalId, 'monthly-limit')}" type="number" min="1" step="1" class="setting-input setting-input--wide setting-input--full" value="${monthlyLimitValue}" placeholder="${host.api.sanitizeAttribute(limitPlaceholder)}">`
            })
        ])}</div>`
    );
};

const buildApiKeyQuotaModalFooter = (host: ApiKeysManagerHost, modalId: string): TrustedHtml => {
    void host;
    const closeLabel = i18n.t('common.close');
    const saveLabel = i18n.t('common.save');

    return renderDynamicSplitModalFooterContent({
        left: renderModalFooterCloseButton({ modalId, text: closeLabel }),
        right: renderModalFooterActionButton({
            id: modalUiId(modalId, 'save'),
            text: saveLabel,
            variant: 'accent'
        })
    });
};

export { buildApiKeyQuotaModalBody, buildApiKeyQuotaModalFooter, renderApiKeyQuotaStatusPreview };
export type { QuotaModalUsers };
