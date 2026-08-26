/* SoAI - Metrics page widgets service [frontend/assets/ts/pages/metrics/widgets/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrustedTableBodyHtml, type TrustedHtml } from '@core/security/public.ts';
import { i18n } from '@core/i18n/index.ts';
import { getCurrentLocale } from '@core/languageservice/service.ts';
import { formatCompactNumber } from '@core/primitives/compactNumber.ts';
import { uiHtml } from '@core/security/uiHtml.ts';
import { resolvePluginStatusFromRecord } from '@core/state/pluginStatus.ts';
import { isFiniteNumber } from '@core/typeGuards.ts';
import { readRuntimeFiniteNumberOrFallbackValue } from '@core/types/numberCoercionReaders.ts';
import { isJsonObject, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import { applyAdaptiveNumbers, renderAdaptiveNumber } from '@core/ui/adaptiveNumber.ts';
import { renderMetricsTableStateRow } from '@pages/metrics/rendering/layout/service.ts';
import type { PluginHealthRow } from '@pages/metrics/types.ts';
import { updateModelTableSortIndicators, updatePluginHealthSortIndicators } from '@pages/metrics/widgets/effects.ts';
import { resolvePluginName, resolvePluginRequestCount, resolvePluginTokenCount } from '@pages/metrics/widgets/mappers.ts';
import type { MetricsPageWidgetHost } from '@pages/metrics/widgets/types.ts';

const sortPluginHealthRows = (host: MetricsPageWidgetHost, rows: PluginHealthRow[]): PluginHealthRow[] => {
    const column = host.state.pluginHealthSortColumn || 'name';
    const direction = host.state.pluginHealthSortDirection === 'desc' ? -1 : 1;
    return [...rows].sort((firstValue, secondValue) => {
        if (column === 'status') {
            const statusComparison = firstValue.statusLabel.localeCompare(secondValue.statusLabel, getCurrentLocale(), {
                sensitivity: 'base',
                numeric: true
            });
            if (statusComparison !== 0) {
                return direction * statusComparison;
            }
            return direction * firstValue.name.localeCompare(secondValue.name, getCurrentLocale(), { sensitivity: 'base' });
        }
        if (column === 'requests') {
            const requestComparison = firstValue.requests - secondValue.requests;
            if (requestComparison !== 0) {
                return direction * requestComparison;
            }
            return direction * firstValue.name.localeCompare(secondValue.name, getCurrentLocale(), { sensitivity: 'base' });
        }
        if (column === 'tokens') {
            const tokenComparison = firstValue.tokens - secondValue.tokens;
            if (tokenComparison !== 0) {
                return direction * tokenComparison;
            }
            return direction * firstValue.name.localeCompare(secondValue.name, getCurrentLocale(), { sensitivity: 'base' });
        }
        return direction * firstValue.name.localeCompare(secondValue.name, getCurrentLocale(), { sensitivity: 'base' });
    });
};

const sortModelTableRows = (
    host: MetricsPageWidgetHost,
    rows: Array<{
        displayName: string;
        tokens: number;
        statusLabel: string;
        requests: number;
    }>
): typeof rows => {
    const column = host.state.modelTableSortColumn || 'requests';
    const direction = host.state.modelTableSortDirection === 'asc' ? 1 : -1;
    const compareText = (firstValue: string, secondValue: string): number =>
        firstValue.localeCompare(secondValue, getCurrentLocale(), {
            sensitivity: 'base',
            numeric: true
        });
    return [...rows].sort((firstValue, secondValue) => {
        switch (column) {
            case 'model':
                return direction * compareText(firstValue.displayName, secondValue.displayName);
            case 'tokens': {
                const tokenComparison = firstValue.tokens - secondValue.tokens;
                return tokenComparison !== 0 ? direction * tokenComparison : compareText(firstValue.displayName, secondValue.displayName);
            }
            case 'status': {
                const statusComparison = compareText(firstValue.statusLabel, secondValue.statusLabel);
                return statusComparison !== 0 ? direction * statusComparison : compareText(firstValue.displayName, secondValue.displayName);
            }
            case 'requests':
            default: {
                const requestComparison = firstValue.requests - secondValue.requests;
                return requestComparison !== 0 ? direction * requestComparison : compareText(firstValue.displayName, secondValue.displayName);
            }
        }
    });
};

const renderPluginHealthPlaceholder = (host: MetricsPageWidgetHost, bodyElement: HTMLElement): void => {
    updateMetricsHtmlIfChanged(host, bodyElement, renderMetricsTableStateRow(i18n.t('metrics.plugin_health.noPluginsInstalled'), 4));
};

const updateMetricsHtmlIfChanged = (host: MetricsPageWidgetHost, element: HTMLElement, html: TrustedHtml): void => {
    if (element.innerHTML === html.html) {
        return;
    }
    host.owners.pageDom.updateHtml(element, html);
    host.owners.pageDom.flush();
};

const renderPluginHealthRows = (host: MetricsPageWidgetHost, bodyElement: HTMLElement, rows: PluginHealthRow[]): void => {
    const sortedRows = sortPluginHealthRows(host, rows);
    const markup = toTrustedTableBodyHtml(
        sortedRows
            .map((row) => {
                const requestValue = renderAdaptiveNumber(row.requestsLabel, formatCompactNumber(row.requests), 'ui-adaptive-number metrics-adaptive-number');
                const tokenValue = renderAdaptiveNumber(row.tokensLabel, formatCompactNumber(row.tokens), 'ui-adaptive-number metrics-adaptive-number');
                return `<tr><td>${row.name}</td><td>${requestValue}</td><td>${tokenValue}</td><td><div class="plugin-status">${row.badge.html}</div></td></tr>`;
            })
            .join('')
    );
    updateMetricsHtmlIfChanged(host, bodyElement, markup);
    applyAdaptiveNumbers(bodyElement);
};

const createPluginHealthRow = (host: MetricsPageWidgetHost, plugin: JsonObject, status: string): PluginHealthRow => {
    const description = host.owners.stateManager.status.getDescription(status);
    const badgeLabel = host.owners.services.sanitizeText(description);
    const badgeClass = host.owners.stateManager.status.getCollectionBadgeClass(status);
    const requests = resolvePluginRequestCount(host.state.currentMetrics, plugin);
    const tokens = resolvePluginTokenCount(host.state.currentMetrics, plugin);
    return {
        name: host.owners.services.sanitizeText(resolvePluginName(plugin)),
        requests,
        requestsLabel: host.metricsServices.metricsFormatter.number(requests),
        tokens,
        tokensLabel: host.metricsServices.metricsFormatter.number(tokens),
        status,
        statusLabel: badgeLabel,
        badge: uiHtml`<span class="ui-status-badge ${badgeClass}">${badgeLabel}</span>`
    };
};

const collectMetricPluginRows = (host: MetricsPageWidgetHost): PluginHealthRow[] => {
    const pluginMetrics = host.state.currentMetrics?.plugins;
    if (!isJsonObject(pluginMetrics)) {
        return [];
    }
    return Object.keys(pluginMetrics)
        .filter((pluginName) => pluginName.trim())
        .map((pluginName) => {
            const plugin: JsonObject = { name: pluginName };
            return createPluginHealthRow(host, plugin, host.owners.stateManager.status.normalizeStatus('unknown'));
        });
};

const updatePluginHealth = (host: MetricsPageWidgetHost): void => {
    const countElement = host.operations.getCachedUI('pluginHealthCount');
    const bodyElement = host.operations.getCachedUI('pluginHealthBody');
    if (!countElement || !bodyElement) {
        return;
    }
    const rows = host.state.currentPlugins
        ? host.state.currentPlugins.filter(isJsonObject).map((plugin) => {
              const status = resolvePluginStatusFromRecord(plugin, (value: JsonValue): string => host.owners.stateManager.status.normalizeStatus(value));
              return createPluginHealthRow(host, plugin, status);
          })
        : collectMetricPluginRows(host);
    host.owners.pageElements.setValue('pluginHealthCount', i18n.plural('metrics.plugin_health.count', rows.length, { count: rows.length }));
    if (rows.length === 0) {
        renderPluginHealthPlaceholder(host, bodyElement);
        return;
    }
    renderPluginHealthRows(host, bodyElement, rows);
    const table = host.operations.getCachedUI('pluginHealthList');
    if (table) {
        updatePluginHealthSortIndicators(host);
    }
};

const updateModelTable = (host: MetricsPageWidgetHost): void => {
    const bodyElement = host.operations.getCachedUI('modelStatsBody');
    const countElement = host.operations.getCachedUI('modelUsageCount');
    if (!bodyElement || !host.state.currentMetrics) {
        return;
    }
    const { billing, director } = host.state.currentMetrics;
    const tokensByModel = billing?.tokensByModel ?? {};
    const requestsByModel = director?.requestsByModel ?? {};
    const requestsByVirtualModel = director?.requestsByVirtualModel ?? {};
    const models = [...new Set([...Object.keys(tokensByModel), ...Object.keys(requestsByModel), ...Object.keys(requestsByVirtualModel)])];
    const availableModels = isFiniteNumber(host.state.currentMetrics.models?.available) ? host.state.currentMetrics.models.available : models.length;
    if (countElement) {
        host.owners.pageElements.setValue('modelUsageCount', i18n.plural('metrics.modelTable.count', availableModels, { count: availableModels }));
    }
    type ModelTableRow = {
        displayName: string;
        tokens: number;
        statusLabel: string;
        requests: number;
    };
    if (models.length === 0) {
        updateMetricsHtmlIfChanged(host, bodyElement, renderMetricsTableStateRow(i18n.t('metrics.modelTable.noData'), 4));
    } else {
        const rowsData: ModelTableRow[] = models.map((modelId) => {
            const requests = readRuntimeFiniteNumberOrFallbackValue(requestsByModel[modelId], 0) + readRuntimeFiniteNumberOrFallbackValue(requestsByVirtualModel[modelId], 0);
            const tokens = readRuntimeFiniteNumberOrFallbackValue(tokensByModel[modelId], 0);
            const displayName = modelId.split('/').pop() || modelId;
            const isActive = requests > 0;
            const statusLabel = isActive ? i18n.t('metrics.modelTable.statusActive') : i18n.t('metrics.modelTable.statusIdle');
            return { displayName, requests, tokens, statusLabel };
        });
        const sortedRowsData = sortModelTableRows(host, rowsData);

        const tableMarkup = toTrustedTableBodyHtml(
            sortedRowsData
                .map((row) => {
                    const requestsLabel = host.metricsServices.metricsFormatter.number(row.requests);
                    const tokensLabel = host.metricsServices.metricsFormatter.number(row.tokens);
                    const compactRequestsLabel = formatCompactNumber(row.requests);
                    const compactTokensLabel = formatCompactNumber(row.tokens);
                    const displayLabel = host.owners.services.sanitizeText(row.displayName);
                    const statusLabel = host.owners.services.sanitizeText(row.statusLabel);
                    return `<tr><td>${displayLabel}</td><td>${renderAdaptiveNumber(requestsLabel, compactRequestsLabel, 'ui-adaptive-number metrics-adaptive-number')}</td><td>${renderAdaptiveNumber(tokensLabel, compactTokensLabel, 'ui-adaptive-number metrics-adaptive-number')}</td><td>${statusLabel}</td></tr>`;
                })
                .join('')
        );
        updateMetricsHtmlIfChanged(host, bodyElement, tableMarkup);
        applyAdaptiveNumbers(bodyElement);
    }
    const table = host.operations.getCachedUI('modelStatsTable');
    if (table) {
        updateModelTableSortIndicators(host);
    }
};

export { updateModelTable, updatePluginHealth };
