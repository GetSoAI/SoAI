/* SoAI - Metrics page widgets effects [frontend/assets/ts/pages/metrics/widgets/effects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { measureLayoutBox } from '@core/layout/elementGeometry.ts';
import { toTrustedUiHtml } from '@core/security/public.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { renderContentImmediately, transitionContentElements } from '@core/animations/contentFadeTransition.ts';
import { buildApiKeyRequestDistributionDataset, buildModelRequestDistributionDataset, buildModelTokenDistributionDataset, buildPluginRequestDistributionDataset, type RequestDistributionDataset, type RequestDistributionSource } from '@core/models/requestDistribution.ts';
import { renderRequestDistributionChartMarkup, renderRequestDistributionEmptyStateMarkup } from '@core/models/requestdistributionglass/chartMarkup.ts';
import { EMPTY_REQUEST_DISTRIBUTION_SIGNATURE, claimRequestDistributionRender, computeRequestDistributionChartSignature, computeRequestDistributionLegendSignature } from '@core/models/requestDistributionRenderState.ts';
import { METRICS_REQUEST_DISTRIBUTION_SOURCE_STORAGE_KEY, buildRequestDistributionLegendItems, createRequestDistributionViewState, resolveRequestDistributionEmptyStateText, resolveRequestDistributionPalette, resolveRequestDistributionSourceToggleLabel, resolveRequestDistributionTitle, type RequestDistributionViewState } from '@core/models/requestDistributionRendering.ts';
import { formatCompactNumber } from '@core/primitives/compactNumber.ts';
import { isFiniteNumber } from '@core/typeGuards.ts';
import { requireSortableHeaders, updateSortableTableIndicators } from '@core/ui/tables/sortableTable.ts';
import { SYSTEM_STATS_CONFIG } from '@features/metrics/public.ts';
import { METRICS_REQUEST_DISTRIBUTION_SOURCE_TOGGLE_ID, METRICS_REQUEST_DISTRIBUTION_TITLE_ID } from '@pages/metrics/actions.ts';
import { updateAdaptiveNumber } from '@core/ui/adaptiveNumber.ts';
import type { MetricsPageWidgetHost } from '@pages/metrics/widgets/types.ts';

const updateSortIndicatorsForTable = (host: MetricsPageWidgetHost, tableId: string, activeColumn: string, activeDirection: string): void => {
    const table = host.operations.getCachedUI(tableId);
    if (!table) {
        throw new Error(`Metrics sortable table is missing required element: ${tableId}`);
    }
    updateSortableTableIndicators({
        headers: requireSortableHeaders(table, `Sortable header in ${tableId}`),
        activeColumn,
        activeDirection,
        host: { getIconSync: (name, options) => host.owners.services.getIconSync(name, options) }
    });
};

const updatePluginHealthSortIndicators = (host: MetricsPageWidgetHost): void => {
    updateSortIndicatorsForTable(host, 'pluginHealthList', host.state.pluginHealthSortColumn || 'name', host.state.pluginHealthSortDirection || 'asc');
};

const updateApiKeyUsageSortIndicators = (host: MetricsPageWidgetHost): void => {
    updateSortIndicatorsForTable(host, 'apiKeyUsageTable', host.state.apiKeyUsageSortColumn || 'requests', host.state.apiKeyUsageSortDirection || 'desc');
};

const updateModelTableSortIndicators = (host: MetricsPageWidgetHost): void => {
    updateSortIndicatorsForTable(host, 'modelStatsTable', host.state.modelTableSortColumn || 'requests', host.state.modelTableSortDirection || 'desc');
};

const updateFrontendTelemetrySortIndicators = (host: MetricsPageWidgetHost): void => {
    updateSortIndicatorsForTable(host, 'frontendMetricsTable', host.state.frontendTelemetrySortColumn || 'metric', host.state.frontendTelemetrySortDirection || 'asc');
};

const updateSystemStatsSortIndicators = (host: MetricsPageWidgetHost): void => {
    const table = host.operations.getCachedUI('systemStatsTable');
    if (!table) {
        throw new Error('Metrics sortable table is missing required element: systemStatsTable');
    }
    const headers = requireSortableHeaders(table, 'Sortable header in systemStatsTable');
    const activeColumn = host.state.systemStatsSortColumn || '';
    if (activeColumn !== 'metric' && activeColumn !== 'value') {
        for (const header of headers) {
            header.header.classList.remove('is-active');
            header.indicator.replaceChildren();
            header.header.setAttribute('aria-sort', 'none');
        }
        return;
    }
    updateSortableTableIndicators({
        headers,
        activeColumn,
        activeDirection: host.state.systemStatsSortDirection || 'asc',
        host: { getIconSync: (name, options) => host.owners.services.getIconSync(name, options) }
    });
};

const distributionViewStates = new WeakMap<MetricsPageWidgetHost, RequestDistributionViewState>();

interface UpdateDistributionChartOptions {
    transition?: boolean;
    transitionLegend?: boolean;
}

const getDistributionViewState = (host: MetricsPageWidgetHost): RequestDistributionViewState => {
    const existing = distributionViewStates.get(host);
    if (existing) {
        return existing;
    }
    const created = createRequestDistributionViewState({
        includeApiKeys: host.owners.auth.isAdmin(),
        storageKey: METRICS_REQUEST_DISTRIBUTION_SOURCE_STORAGE_KEY,
        storage: {
            get: (key, defaultValue): JsonValue => host.state.storage.get(key, defaultValue ?? null) ?? null,
            set: (key, value): void => {
                host.state.storage.set(key, value);
            }
        }
    });
    distributionViewStates.set(host, created);
    return created;
};

const syncDistributionSourceUi = (host: MetricsPageWidgetHost, viewState: RequestDistributionViewState): void => {
    const source = viewState.getSource();
    host.owners.pageElements.setValue(METRICS_REQUEST_DISTRIBUTION_TITLE_ID, resolveRequestDistributionTitle(source), { allowNull: true });
    const button = host.operations.getCachedUI(METRICS_REQUEST_DISTRIBUTION_SOURCE_TOGGLE_ID);
    if (!button) {
        return;
    }
    const label = resolveRequestDistributionSourceToggleLabel(viewState.getNextSource());
    host.owners.pageDom.updateAttribute(button, 'aria-label', label);
    host.owners.pageDom.updateAttribute(button, 'data-tooltip', label);
};

const buildDistributionDataset = (host: MetricsPageWidgetHost, source: RequestDistributionSource): RequestDistributionDataset => {
    if (source === 'apiKey') {
        const rows = host.state.currentApiKeyUsageRows?.map((row) => ({
            keyId: row.keyId,
            label: row.label,
            prefix: row.prefix,
            requestCount: row.requestCount
        }));
        return buildApiKeyRequestDistributionDataset(rows);
    }
    if (source === 'token') {
        return buildModelTokenDistributionDataset(host.state.currentMetrics?.billing?.tokensByModel);
    }
    if (source === 'plugin') {
        return buildPluginRequestDistributionDataset(host.state.currentMetrics?.plugins);
    }
    return buildModelRequestDistributionDataset(host.state.currentMetrics?.director?.requestsByModel, host.state.currentMetrics?.director?.requestsByVirtualModel);
};

const updateDistributionChart = (host: MetricsPageWidgetHost, options: UpdateDistributionChartOptions = {}): void => {
    const mount = host.operations.getCachedUI('distributionChart');
    const legendElement = host.operations.getCachedUI('distributionLegend');
    const legendContentElement = host.operations.getCachedUI('distributionLegendInner');
    const viewState = getDistributionViewState(host);
    syncDistributionSourceUi(host, viewState);
    if (!mount) {
        return;
    }
    if (legendElement && !legendContentElement) {
        return;
    }
    const canvasCandidate = mount.closest('.chart-container-sm__canvas');
    const canvas = canvasCandidate instanceof HTMLElement ? canvasCandidate : mount;
    const setEmptyChartLayout = (isEmpty: boolean): void => {
        mount.setAttribute('data-request-distribution-chart-active', isEmpty ? 'false' : 'true');
        mount.closest('.chart-container-sm')?.classList.toggle('chart-container-sm--empty', isEmpty);
    };
    const renderEmptyChart = (): void => {
        setEmptyChartLayout(true);
        if (!claimRequestDistributionRender(mount, EMPTY_REQUEST_DISTRIBUTION_SIGNATURE)) {
            return;
        }
        host.owners.pageDom.updateHtml(mount, renderRequestDistributionEmptyStateMarkup(resolveRequestDistributionEmptyStateText()));
    };
    const renderLegend = (items: Array<{ label: string; value: string; swatchStyle: string }>, signature: string): void => {
        if (!legendContentElement) {
            return;
        }
        if (!claimRequestDistributionRender(legendContentElement, signature, { expectsContent: items.length > 0 })) {
            return;
        }
        if (!items.length) {
            host.owners.pageDom.updateHtml(legendContentElement, '');
            return;
        }
        const markup = items
            .map((item) => {
                const label = host.owners.services.sanitizeText(item.label);
                const value = host.owners.services.sanitizeText(item.value);
                return `<li class="distribution-legend__item"><span class="distribution-legend__swatch" style="${item.swatchStyle}"></span><div class="distribution-legend__text"><span class="distribution-legend__label">${label}</span><span class="distribution-legend__value">${value}</span></div></li>`;
            })
            .join('');
        host.owners.pageDom.updateHtml(legendContentElement, toTrustedUiHtml(`<ul class="distribution-legend">${markup}</ul>`));
    };
    const commitDistributionSurfaces = (renderChart: () => void, renderLegendContent: () => void, nextEmpty: boolean): void => {
        const previousEmpty = mount.getAttribute('data-request-distribution-chart-active') !== 'true';
        if (options.transition === true && options.transitionLegend === true && legendContentElement) {
            if (previousEmpty && nextEmpty) {
                renderChart();
                renderLegendContent();
                return;
            }
            transitionContentElements({
                elements: [canvas, legendElement ?? legendContentElement],
                render: (): void => {
                    renderChart();
                    renderLegendContent();
                }
            });
            return;
        }
        if (options.transition === true) {
            transitionContentElements({ elements: [mount], render: renderChart });
            renderLegendContent();
            return;
        }
        renderContentImmediately({ elements: [mount], render: renderChart });
        renderLegendContent();
    };
    viewState.attachChartKindCycle(mount, () => updateDistributionChart(host, { transition: true }), {
        shouldCycle: () => mount.getAttribute('data-request-distribution-chart-active') === 'true'
    });
    host.state.distributionChartSizeWatcher.observe(mount, () => updateDistributionChart(host));
    let dataset: RequestDistributionDataset;
    try {
        dataset = buildDistributionDataset(host, viewState.getSource());
    } catch (error) {
        errorHandler.warn('MetricsPage', 'Request distribution dataset build failed', ensureError(error));
        commitDistributionSurfaces(renderEmptyChart, () => renderLegend([], EMPTY_REQUEST_DISTRIBUTION_SIGNATURE), true);
        return;
    }
    if (!dataset.entries.length) {
        commitDistributionSurfaces(renderEmptyChart, () => renderLegend([], EMPTY_REQUEST_DISTRIBUTION_SIGNATURE), true);
        return;
    }

    const colors = resolveRequestDistributionPalette((token) => host.owners.services.getStyleProperty(token));
    if (!colors.length) {
        commitDistributionSurfaces(renderEmptyChart, () => renderLegend([], EMPTY_REQUEST_DISTRIBUTION_SIGNATURE), true);
        return;
    }
    const legendSource = buildRequestDistributionLegendItems(dataset.entries, (value) => host.metricsServices.metricsFormatter.number(value, '0'), colors);
    const legendSignature = computeRequestDistributionLegendSignature(legendSource);
    const legendItems = legendSource.map((entry) => ({
        label: host.owners.services.sanitizeText(entry.label),
        value: host.owners.services.sanitizeText(entry.detail),
        swatchStyle: entry.swatchStyle
    }));
    const renderChart = (): void => {
        setEmptyChartLayout(false);
        const rect = measureLayoutBox(mount);
        const width = rect.width;
        const height = rect.height;
        if (width <= 0 || height <= 0 || !isFiniteNumber(width) || !isFiniteNumber(height)) {
            renderEmptyChart();
            return;
        }
        const kind = viewState.getChartKind();
        if (!claimRequestDistributionRender(mount, computeRequestDistributionChartSignature({ kind, width, height, colors, dataset }))) {
            return;
        }
        try {
            host.owners.pageDom.updateHtml(mount, renderRequestDistributionChartMarkup({ width, height, dataset, colors, kind }));
        } catch (error) {
            errorHandler.warn('MetricsPage', 'Request distribution chart render failed', ensureError(error));
            renderEmptyChart();
        }
    };
    const renderLegendContent = (): void => {
        if (mount.getAttribute('data-request-distribution-chart-active') === 'true') {
            renderLegend(legendItems, legendSignature);
            return;
        }
        renderLegend([], EMPTY_REQUEST_DISTRIBUTION_SIGNATURE);
    };
    commitDistributionSurfaces(renderChart, renderLegendContent, false);
};

const toggleMetricsRequestDistributionSource = (host: MetricsPageWidgetHost): void => {
    const viewState = getDistributionViewState(host);
    viewState.toggleSource();
    syncDistributionSourceUi(host, viewState);
    updateDistributionChart(host, { transition: true, transitionLegend: true });
};

const updateSystemStats = (host: MetricsPageWidgetHost): void => {
    for (const field of SYSTEM_STATS_CONFIG) {
        const raw = host.state.currentMetrics ? field.value(host.state.currentMetrics) : 0;
        const value = isFiniteNumber(raw) ? Number(raw) : 0;
        const normalizedValue = field.unit === 'percent' ? Math.round(value * 100) / 100 : value;
        const displayValue = field.unit === 'percent' ? `${host.metricsServices.metricsFormatter.number(normalizedValue, '0')}%` : host.metricsServices.metricsFormatter.number(normalizedValue, '0');
        const compactValue = field.unit === 'percent' ? `${formatCompactNumber(normalizedValue)}%` : formatCompactNumber(normalizedValue);
        const element = host.operations.getCachedUI(field.id);
        if (element) {
            updateAdaptiveNumber({ pageDom: host.owners.pageDom }, element, displayValue, compactValue, 'ui-adaptive-number metrics-adaptive-number');
        }
    }
};

export { toggleMetricsRequestDistributionSource, updateApiKeyUsageSortIndicators, updateDistributionChart, updateFrontendTelemetrySortIndicators, updateModelTableSortIndicators, updatePluginHealthSortIndicators, updateSystemStats, updateSystemStatsSortIndicators };
