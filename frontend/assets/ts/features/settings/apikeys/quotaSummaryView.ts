/* SoAI - Settings feature quota summary view [frontend/assets/ts/features/settings/apikeys/quotaSummaryView.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { renderLabelAttributes, toTrustedUiHtml, type TrustedHtml } from '@core/security/public.ts';
import { i18n } from '@core/i18n/index.ts';
import { EMPTY_UI_HTML } from '@core/security/uiHtml.ts';
import type { ApiKeyQuotaSummary } from '@core/settings/contracts.ts';
import type { ApiKeysViewRenderHost } from '@features/settings/apikeys/types.ts';
import { QUOTA_WINDOWS, renderQuotaWindowStatus } from '@features/settings/apikeys/quotaPresentation.ts';
import { serverEpochMs } from '@core/time/clock.ts';

const getQuotaModeBadgeClass = (unit: string): string => {
    switch (unit) {
        case 'tokens':
            return 'settings-record-badge--neutral';
        case 'requests':
            return 'settings-record-badge--active';
        default:
            return 'settings-record-badge--neutral';
    }
};

const renderApiKeyQuotaModeBadge = (host: ApiKeysViewRenderHost, keyId: string): TrustedHtml => {
    const quotaSummary: ApiKeyQuotaSummary | null = host.state.getApiKeyQuotaSummary(keyId);
    if (!quotaSummary) {
        return EMPTY_UI_HTML;
    }

    const unit = quotaSummary.status.unit;
    if (unit !== 'tokens' && unit !== 'requests') {
        return toTrustedUiHtml(`<span class="settings-record-badge settings-record-badge--neutral api-key-quota-mode-badge" ${renderLabelAttributes(i18n.t('settings.apiKeys.quota.mode.none')).html}>${host.api.sanitizeHtml(i18n.t('settings.apiKeys.quota.mode.noneSymbol'))}</span>`);
    }

    const badgeClass = getQuotaModeBadgeClass(unit);
    const modeLabel = unit === 'tokens' ? i18n.t('settings.apiKeys.quota.mode.tokens') : i18n.t('settings.apiKeys.quota.mode.requests');
    return toTrustedUiHtml(`<span class="settings-record-badge ${badgeClass} api-key-quota-mode-badge">${host.api.sanitizeHtml(modeLabel)}</span>`);
};

const renderApiKeyQuotaSummary = (host: ApiKeysViewRenderHost, keyId: string): TrustedHtml => {
    const quotaSummary: ApiKeyQuotaSummary | null = host.state.getApiKeyQuotaSummary(keyId);
    if (!quotaSummary) {
        return EMPTY_UI_HTML;
    }

    const unit = quotaSummary.status.unit;
    if (unit !== 'tokens' && unit !== 'requests') {
        return EMPTY_UI_HTML;
    }

    const nowTs = serverEpochMs();
    const windowBlocks = QUOTA_WINDOWS.map((windowName) => renderQuotaWindowStatus(host.api, quotaSummary.status, windowName, nowTs))
        .filter(Boolean)
        .join('');
    if (!windowBlocks) {
        return EMPTY_UI_HTML;
    }

    return toTrustedUiHtml(`<div class="api-key-quota-summary"><div class="api-key-quota-grid">${windowBlocks}</div></div>`);
};

export { renderApiKeyQuotaModeBadge, renderApiKeyQuotaSummary };
