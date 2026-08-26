/* SoAI - Metrics page tables [frontend/assets/ts/pages/metrics/controllers/page/tables.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { requireClosestElement, requireTrimmedDataAttribute } from '@core/dom/attributes.ts';
import { dom } from '@core/dom/dom.ts';
import { isHTMLElement, isString } from '@core/typeGuards.ts';
import type { MetricsPageServiceHost } from '@pages/metrics/controllers/page/contracts.ts';
import { persistMetricsPageControls } from '@pages/metrics/controllers/page/metricsPageControlsController.ts';
import type { TableBodyContext } from '@pages/metrics/types.ts';
import { handleApiKeyUsageSort } from '@pages/metrics/widgets/apiKeyUsageTableWidget.ts';
import { handleFrontendTelemetrySort, handleModelTableSort, handlePluginHealthSort, handleSystemStatsSort, updateFrontendTelemetrySortIndicators, updateModelTableSortIndicators, updatePluginHealthSortIndicators, updateSystemStatsSortIndicators } from '@pages/metrics/widgets/events.ts';
import { updateApiKeyUsageSortIndicators } from '@pages/metrics/widgets/effects.ts';

const getMetricsCachedUiElement = (host: MetricsPageServiceHost, id: string): HTMLElement | null => {
    if (!id) {
        return null;
    }
    const cached = host.state.uiCache.get(id);
    if (isHTMLElement(cached) && cached.isConnected) {
        return cached;
    }
    const ui = host.owners.pageDom.optional(id);
    const element = isHTMLElement(ui) ? ui : null;
    if (element) {
        host.state.uiCache.set(id, element);
        return element;
    }
    host.state.uiCache.delete(id);
    return null;
};

const resolveMetricsTableBodyContext = (host: MetricsPageServiceHost, tableId: string): TableBodyContext | null => {
    if (!tableId) {
        return null;
    }
    const table = getMetricsCachedUiElement(host, tableId);
    if (!table) {
        return null;
    }
    const bodyElement = dom.resolve('tbody', table);
    if (!isHTMLElement(bodyElement)) {
        return null;
    }
    const rows = dom.resolveAll('tr', bodyElement).filter((row): row is HTMLTableRowElement => row instanceof HTMLTableRowElement);
    if (rows.length === 0) {
        return null;
    }
    return { table, bodyElement: bodyElement, rows };
};

const handleMetricsRootSortAction = (host: MetricsPageServiceHost, actionElement: Element): void => {
    const column = requireTrimmedDataAttribute(actionElement, 'sort', 'Metrics sort action');
    const tableId = requireClosestElement(actionElement, 'table', 'Metrics sort action').id;
    if (!isString(tableId) || !tableId) {
        throw new Error('Metrics sort action is missing required table scope');
    }
    if (tableId === 'pluginHealthList') {
        handlePluginHealthSort(host, column);
        persistMetricsPageControls(host.state);
        updatePluginHealthSortIndicators(host);
        return;
    }
    if (tableId === 'modelStatsTable') {
        handleModelTableSort(host, column);
        persistMetricsPageControls(host.state);
        updateModelTableSortIndicators(host);
        return;
    }
    if (tableId === 'apiKeyUsageTable') {
        handleApiKeyUsageSort(host, column);
        persistMetricsPageControls(host.state);
        updateApiKeyUsageSortIndicators(host);
        return;
    }
    if (tableId === 'frontendMetricsTable') {
        handleFrontendTelemetrySort(host, column);
        persistMetricsPageControls(host.state);
        updateFrontendTelemetrySortIndicators(host);
        return;
    }
    if (tableId === 'systemStatsTable') {
        handleSystemStatsSort(host, column);
        persistMetricsPageControls(host.state);
        updateSystemStatsSortIndicators(host);
        return;
    }
    throw new Error(`Unsupported metrics sortable table: ${tableId}`);
};

const initializeMetricsTables = (host: MetricsPageServiceHost): void => {
    updatePluginHealthSortIndicators(host);
    updateModelTableSortIndicators(host);
    if (getMetricsCachedUiElement(host, 'apiKeyUsageTable')) {
        updateApiKeyUsageSortIndicators(host);
    }
    updateFrontendTelemetrySortIndicators(host);
    updateSystemStatsSortIndicators(host);

    const enableTableStriping = (table: HTMLElement | null): void => {
        if (!table) {
            return;
        }
        const body = dom.resolve('tbody', table);
        if (body instanceof HTMLElement) {
            host.owners.pageElements.enableCheckerboard(body, 'tr');
        }
    };

    enableTableStriping(getMetricsCachedUiElement(host, 'pluginHealthList'));
    enableTableStriping(getMetricsCachedUiElement(host, 'modelStatsTable'));
    enableTableStriping(getMetricsCachedUiElement(host, 'apiKeyUsageTable'));
    enableTableStriping(getMetricsCachedUiElement(host, 'frontendMetricsTable'));
    enableTableStriping(getMetricsCachedUiElement(host, 'systemStatsTable'));
};

export { getMetricsCachedUiElement, handleMetricsRootSortAction, initializeMetricsTables, resolveMetricsTableBodyContext };
