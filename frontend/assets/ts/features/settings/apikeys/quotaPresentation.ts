/* SoAI - Settings feature quota presentation [frontend/assets/ts/features/settings/apikeys/quotaPresentation.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { clampPercent } from '@core/primitives/clampNumber.ts';
import { formatDuration } from '@core/primitives/duration.ts';
import type { ApiKeyQuotaStatus } from '@core/settings/contracts.ts';
import { PROGRESS_WIDTH_ATTRIBUTE, resolveProgressUsageClass } from '@core/ui/progressWidths.ts';

type QuotaWindowName = 'hourly' | 'daily' | 'weekly' | 'monthly';

interface QuotaWindowRenderHost {
    sanitizeAttribute: (value: string) => string;
    sanitizeHtml: (value: string) => string;
}

const QUOTA_WINDOWS: readonly QuotaWindowName[] = Object.freeze(['hourly', 'daily', 'weekly', 'monthly']);

const resolveQuotaWindowLabel = (windowName: QuotaWindowName): string => {
    switch (windowName) {
        case 'hourly':
            return i18n.t('settings.apiKeys.quota.windows.hourly');
        case 'daily':
            return i18n.t('settings.apiKeys.quota.windows.daily');
        case 'weekly':
            return i18n.t('settings.apiKeys.quota.windows.weekly');
        case 'monthly':
            return i18n.t('settings.apiKeys.quota.windows.monthly');
        default: {
            const exhaustive: never = windowName;
            throw new Error(`Unhandled quota window: ${exhaustive}`);
        }
    }
};

const renderQuotaWindowStatus = (host: QuotaWindowRenderHost, quotaStatus: ApiKeyQuotaStatus, windowName: QuotaWindowName, nowTs: number): string => {
    const entry = quotaStatus[windowName];
    if (!entry) {
        return '';
    }
    const usedUnits = entry.usedUnits + entry.reservedUnits;
    const limitUnits = entry.limitUnits;
    const percentUsed = limitUnits > 0 ? clampPercent((usedUnits / limitUnits) * 100) : 0;
    const usageClass = resolveProgressUsageClass(percentUsed);
    const label = resolveQuotaWindowLabel(windowName);
    const usedLabel = `${i18n.formatNumber(usedUnits)}/${i18n.formatNumber(limitUnits)}`;
    const resetInSeconds = Math.ceil(Math.max(0, entry.resetAtMs - nowTs) / 1000);
    const resetText = i18n.t('settings.apiKeys.quota.resetsIn', { duration: formatDuration(resetInSeconds) });

    return `<div class="api-key-quota-window settings-card-surface" data-quota-window="${host.sanitizeAttribute(windowName)}" data-tooltip="${host.sanitizeAttribute(`${label} • ${usedLabel} • ${resetText}`)}"><div class="api-key-quota-window-header"><span class="api-key-quota-window-label">${label}</span><span class="api-key-quota-window-value">${host.sanitizeHtml(usedLabel)}</span></div><div class="progress-bar api-key-quota-progress"><div class="progress-fill ${usageClass}" ${PROGRESS_WIDTH_ATTRIBUTE}="${percentUsed.toFixed(1)}"></div></div><div class="api-key-quota-window-meta">${resetText}</div></div>`;
};

export { QUOTA_WINDOWS, renderQuotaWindowStatus };
