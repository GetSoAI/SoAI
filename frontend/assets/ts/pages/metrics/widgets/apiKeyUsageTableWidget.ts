/* SoAI - Metrics page API key usage table widget [frontend/assets/ts/pages/metrics/widgets/apiKeyUsageTableWidget.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrustedTableBodyHtml, type TrustedHtml } from '@core/security/public.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { i18n } from '@core/i18n/index.ts';
import { getCurrentLocale } from '@core/languageservice/service.ts';
import { formatPositiveEpochMsWithFallback } from '@core/primitives/dateTime.ts';
import { formatCompactNumber } from '@core/primitives/compactNumber.ts';
import { serverEpochMs } from '@core/time/clock.ts';
import { normalizeApiKeyUsageSnapshot } from '@core/settings/apiKeyPayloads.ts';
import { applyAdaptiveNumbers, renderAdaptiveNumber } from '@core/ui/adaptiveNumber.ts';
import { renderMetricsTableStateRow } from '@pages/metrics/rendering/layout/service.ts';
import type { ApiKeyUsageRow } from '@pages/metrics/types.ts';
import { updateApiKeyUsageSortIndicators, updateDistributionChart } from '@pages/metrics/widgets/effects.ts';
import { API_KEY_USAGE_SORT_COLUMNS, API_KEY_USAGE_SORT_DEFAULT_DIRECTIONS, resolveMetricsNextSortState } from '@pages/metrics/widgets/MetricsSortDefinitionsWidget.ts';
import type { MetricsPageWidgetHost } from '@pages/metrics/widgets/types.ts';

const resolveApiKeyUsageStatus = (row: ApiKeyUsageRow): string => {
    if (row.revoked) {
        return 'revoked';
    }
    if (row.expiresAtMs !== null && row.expiresAtMs <= serverEpochMs()) {
        return 'expired';
    }
    return 'active';
};

const resolveApiKeyUsageStatusLabel = (row: ApiKeyUsageRow): string => {
    const status = resolveApiKeyUsageStatus(row);
    if (status === 'revoked') {
        return i18n.t('metrics.cards.apiKeyUsage.status.revoked');
    }
    if (status === 'expired') {
        return i18n.t('metrics.cards.apiKeyUsage.status.expired');
    }
    return i18n.t('metrics.cards.apiKeyUsage.status.active');
};

const compareApiKeyUsageRows = (host: MetricsPageWidgetHost, left: ApiKeyUsageRow, right: ApiKeyUsageRow): number => {
    const column = host.state.apiKeyUsageSortColumn || 'requests';
    const direction = host.state.apiKeyUsageSortDirection === 'asc' ? 1 : -1;
    const compareText = (firstValue: string, secondValue: string): number => firstValue.localeCompare(secondValue, getCurrentLocale(), { sensitivity: 'base', numeric: true });
    const tieBreak = compareText(left.label || left.prefix || left.keyId, right.label || right.prefix || right.keyId);
    if (column === 'requests' && left.requestCount !== right.requestCount) {
        return direction * (left.requestCount - right.requestCount);
    }
    if (column === 'rateLimited' && left.rateLimitedCount !== right.rateLimitedCount) {
        return direction * (left.rateLimitedCount - right.rateLimitedCount);
    }
    if (column === 'lastUsed' && left.lastUsedAtMs !== right.lastUsedAtMs) {
        return direction * ((left.lastUsedAtMs || 0) - (right.lastUsedAtMs || 0));
    }
    if (column === 'status') {
        const statusComparison = compareText(resolveApiKeyUsageStatusLabel(left), resolveApiKeyUsageStatusLabel(right));
        if (statusComparison !== 0) {
            return direction * statusComparison;
        }
    }
    if (column === 'prefix') {
        const prefixComparison = compareText(left.prefix, right.prefix);
        if (prefixComparison !== 0) {
            return direction * prefixComparison;
        }
    }
    if (column === 'label') {
        const labelComparison = compareText(left.label, right.label);
        if (labelComparison !== 0) {
            return direction * labelComparison;
        }
    }
    return tieBreak;
};

const updateApiKeyUsageHtmlIfChanged = (host: MetricsPageWidgetHost, element: HTMLElement, html: TrustedHtml): void => {
    if (element.innerHTML === html.html) {
        return;
    }
    host.owners.pageDom.updateHtml(element, html);
    host.owners.pageDom.flush();
};

const renderApiKeyUsageRows = (host: MetricsPageWidgetHost, bodyElement: HTMLElement, rows: ApiKeyUsageRow[]): void => {
    if (!rows.length) {
        updateApiKeyUsageHtmlIfChanged(host, bodyElement, renderMetricsTableStateRow(i18n.t('metrics.cards.apiKeyUsage.noData'), 6));
        return;
    }
    const sortedRows = [...rows].sort((left, right) => compareApiKeyUsageRows(host, left, right));
    const markup = toTrustedTableBodyHtml(
        sortedRows
            .map((row) => {
                const label = host.owners.services.sanitizeText(row.label || row.keyId);
                const prefix = host.owners.services.sanitizeText(row.prefix);
                const statusLabel = host.owners.services.sanitizeText(resolveApiKeyUsageStatusLabel(row));
                const requestsLabel = host.metricsServices.metricsFormatter.number(row.requestCount);
                const rateLimitedLabel = host.metricsServices.metricsFormatter.number(row.rateLimitedCount);
                const lastUsedLabel = formatPositiveEpochMsWithFallback(row.lastUsedAtMs, i18n.t('metrics.cards.apiKeyUsage.neverUsed'));
                return `<tr><td>${label}</td><td><code>${prefix}</code></td><td>${statusLabel}</td><td>${renderAdaptiveNumber(requestsLabel, formatCompactNumber(row.requestCount), 'ui-adaptive-number metrics-adaptive-number')}</td><td>${renderAdaptiveNumber(rateLimitedLabel, formatCompactNumber(row.rateLimitedCount), 'ui-adaptive-number metrics-adaptive-number')}</td><td>${lastUsedLabel}</td></tr>`;
            })
            .join('')
    );
    updateApiKeyUsageHtmlIfChanged(host, bodyElement, markup);
    applyAdaptiveNumbers(bodyElement);
};

const updateApiKeyUsageTable = (host: MetricsPageWidgetHost): void => {
    const bodyElement = host.operations.getCachedUI('apiKeyUsageBody');
    if (!bodyElement) {
        return;
    }
    renderApiKeyUsageRows(host, bodyElement, host.state.currentApiKeyUsageRows ?? []);
    updateApiKeyUsageSortIndicators(host);
};

const updateApiKeyUsageFromSnapshot = (host: MetricsPageWidgetHost, value: JsonValue): void => {
    host.state.currentApiKeyUsageRows = normalizeApiKeyUsageSnapshot(value);
    updateApiKeyUsageTable(host);
    updateDistributionChart(host);
};

const handleApiKeyUsageSort = (host: MetricsPageWidgetHost, column: string): void => {
    const next = resolveMetricsNextSortState(host.state.apiKeyUsageSortColumn, host.state.apiKeyUsageSortDirection, column, API_KEY_USAGE_SORT_COLUMNS, API_KEY_USAGE_SORT_DEFAULT_DIRECTIONS, 'API key usage');
    host.state.apiKeyUsageSortColumn = next.column;
    host.state.apiKeyUsageSortDirection = next.direction;
    updateApiKeyUsageTable(host);
};

export { handleApiKeyUsageSort, updateApiKeyUsageFromSnapshot, updateApiKeyUsageTable };
