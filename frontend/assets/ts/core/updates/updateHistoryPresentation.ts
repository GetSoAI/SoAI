/* SoAI - Localized update history freshness and timestamps [frontend/assets/ts/core/updates/updateHistoryPresentation.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { formatLocalizedDate } from '@core/localization/public.ts';
import type { UpdateHistory } from '@core/updates/updateHistory.ts';

const formatTimestamp = (timestamp: number): string => formatLocalizedDate(new Date(timestamp), { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });

const formatUpdateHistory = (history: UpdateHistory, saved: boolean): string => {
    const parts: string[] = [];
    if (history.checkedAtMs !== null) parts.push(i18n.t('updates.history.lastCheck', { date: formatTimestamp(history.checkedAtMs) }));
    if (history.updatedAtMs !== null) parts.push(i18n.t('updates.history.lastUpdate', { date: formatTimestamp(history.updatedAtMs) }));
    if (saved && history.resultAtMs !== null) parts.push(i18n.t('updates.history.savedResults', { date: formatTimestamp(history.resultAtMs) }));
    return parts.join(' ');
};

export { formatUpdateHistory };
