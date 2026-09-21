/* SoAI - Dashboard page requests section [frontend/assets/ts/pages/dashboard/controllers/dashboardRequestsSection.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { measureElementLayoutDimensions } from '@core/layout/elementGeometry.ts';
import { narrowHTMLElement } from '@core/dom/narrowElement.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { renderContentImmediately, transitionContentElements } from '@core/animations/contentFadeTransition.ts';
import { buildApiKeyRequestDistributionDataset, buildModelRequestDistributionDataset, buildModelTokenDistributionDataset, buildPluginRequestDistributionDataset, type RequestDistributionDataset, type RequestDistributionSource } from '@core/models/requestDistribution.ts';
import type { RequestDistributionChartSizeWatcher } from '@core/models/requestDistributionChartSizing.ts';
import { renderRequestDistributionChartMarkup, renderRequestDistributionEmptyStateMarkup } from '@core/models/requestdistributionglass/chartMarkup.ts';
import { EMPTY_REQUEST_DISTRIBUTION_SIGNATURE, claimRequestDistributionRender, computeRequestDistributionChartSignature, computeRequestDistributionLegendSignature } from '@core/models/requestDistributionRenderState.ts';
import { buildRequestDistributionPresentation, resolveRequestDistributionEmptyStateText, resolveRequestDistributionOthersColor, resolveRequestDistributionPalette, resolveRequestDistributionSourceToggleLabel, resolveRequestDistributionTitle, type RequestDistributionLegendItem, type RequestDistributionViewState } from '@core/models/requestDistributionRendering.ts';
import { formatCompactNumber } from '@core/primitives/compactNumber.ts';
import { isJsonObject, isJsonValue, type JsonValue } from '@core/types/jsonValues.ts';
import { setTooltipText } from '@core/ui/tooltips/tooltipAttributes.ts';
import { DASHBOARD_REQUEST_DISTRIBUTION_SOURCE_TOGGLE_ID } from '@pages/dashboard/actions.ts';
import type { DashboardHost } from '@core/edition/dashboardContribution.ts';
import { renderDashboardSectionState } from '@pages/dashboard/controllers/dashboardSectionStateController.ts';

interface DashboardRequestsRendererDependencies {
    host: DashboardHost;
    chartSizeWatcher: RequestDistributionChartSizeWatcher;
    getMetrics: () => JsonValue;
    getApiKeyUsage: () => JsonValue | null;
    hasApiKeyUsage: () => boolean;
    hasMetrics: () => boolean;
    requestApiKeyUsage: () => void;
    viewState: RequestDistributionViewState;
}

interface DashboardRequestsRenderOptions {
    transition?: boolean;
}

interface DashboardRequestsSurfaces {
    chart: HTMLElement;
    mount: HTMLElement;
    legend: HTMLElement;
}

const syncDashboardRequestDistributionSourceToggle = (host: DashboardHost, viewState: RequestDistributionViewState): void => {
    const source = viewState.getSource();
    const title = host.optionalHTMLElement('.dashboard-section[data-section-id="requests"] .section-title');
    if (title) {
        title.textContent = resolveRequestDistributionTitle(source);
    }
    const button = host.optionalHTMLElement(`#${DASHBOARD_REQUEST_DISTRIBUTION_SOURCE_TOGGLE_ID}`);
    if (!button) {
        return;
    }
    const label = resolveRequestDistributionSourceToggleLabel(viewState.getNextSource());
    button.setAttribute('aria-label', label);
    setTooltipText(button, label);
    button.setAttribute('aria-pressed', source === 'model' ? 'false' : 'true');
};

const buildDashboardRequestDistributionDataset = (metrics: JsonValue, apiKeyUsage: JsonValue | null, source: RequestDistributionSource): RequestDistributionDataset => {
    if (source === 'apiKey') {
        return buildApiKeyRequestDistributionDataset(isJsonValue(apiKeyUsage) ? apiKeyUsage : undefined);
    }
    const metricsObject = isJsonObject(metrics) ? metrics : {};
    if (source === 'token') {
        const billing = metricsObject['billing'];
        const billingObject = isJsonObject(billing) ? billing : {};
        return buildModelTokenDistributionDataset(billingObject['tokensByModel']);
    }
    if (source === 'plugin') {
        return buildPluginRequestDistributionDataset(metricsObject['plugins']);
    }
    const director = metricsObject['director'];
    const directorObject = isJsonObject(director) ? director : {};
    return buildModelRequestDistributionDataset(directorObject['requestsByModel'], directorObject['requestsByVirtualModel']);
};

const buildDashboardRequestsLegendList = (host: DashboardHost, legendItems: readonly RequestDistributionLegendItem[]): HTMLElement => {
    const legendList = host.createElement('ul', { className: 'distribution-legend' });
    const legendListElement = narrowHTMLElement(legendList, 'requests legend list');
    legendItems.forEach((entry) => {
        const label = host.sanitizeText(entry.label);
        const detail = host.sanitizeText(entry.detail);
        const item = host.createElement('li', { className: entry.separatorBefore === true ? 'distribution-legend__item distribution-legend__item--others-boundary' : 'distribution-legend__item' });
        const itemElement = narrowHTMLElement(item, 'requests legend item');
        const swatch = host.createElement('span', { className: 'distribution-legend__swatch' });
        const swatchElement = narrowHTMLElement(swatch, 'requests legend swatch');
        swatchElement.style.setProperty('--distribution-legend-swatch-color', entry.swatchColor);
        const textWrapper = host.createElement('div', { className: 'distribution-legend__text' });
        const textWrapperElement = narrowHTMLElement(textWrapper, 'requests legend text wrapper');
        const labelNode = host.createElement('span', { className: 'distribution-legend__label' }, label);
        const valueNode = host.createElement('span', { className: 'distribution-legend__value' }, detail);
        textWrapperElement.append(narrowHTMLElement(labelNode, 'requests legend label'), narrowHTMLElement(valueNode, 'requests legend value'));
        itemElement.append(swatchElement, narrowHTMLElement(textWrapperElement, 'requests legend text wrapper'));
        legendListElement.appendChild(itemElement);
    });
    return legendListElement;
};

const resolveDashboardRequestsSurfaces = (host: DashboardHost, contentElement: HTMLElement): DashboardRequestsSurfaces => {
    const existingMount = host.optionalHTMLElement('.request-distribution-chart__mount', contentElement);
    const existingLegend = host.optionalHTMLElement('.request-distribution-legend', contentElement);
    const existingChart = existingMount?.closest('.request-distribution-chart') ?? null;
    if (existingMount && existingLegend && existingChart instanceof HTMLElement) {
        return { chart: existingChart, mount: existingMount, legend: existingLegend };
    }

    const container = host.createElement('div', { className: 'request-distribution-container' });
    const containerElement = narrowHTMLElement(container, 'requests container');
    const chartWrapper = host.createElement('div', { className: 'request-distribution-chart' });
    const chartWrapperElement = narrowHTMLElement(chartWrapper, 'requests chart wrapper');
    const mount = host.createElement('div', { id: 'requests-chart', className: 'request-distribution-chart__mount' });
    const mountElement = narrowHTMLElement(mount, 'requests chart mount');
    chartWrapperElement.appendChild(mountElement);
    containerElement.appendChild(chartWrapperElement);
    const legendWrapper = host.createElement('div', { className: 'request-distribution-legend' });
    const legendWrapperElement = narrowHTMLElement(legendWrapper, 'requests legend wrapper');
    containerElement.appendChild(legendWrapperElement);
    host.replaceElementContent(contentElement, containerElement, { escape: false });
    host.flushDOMUpdates();
    return { chart: chartWrapperElement, mount: mountElement, legend: legendWrapperElement };
};

const createDashboardRequestsSectionRenderer = (dependencies: DashboardRequestsRendererDependencies): ((options?: DashboardRequestsRenderOptions) => void) => {
    const host = dependencies.host;

    const renderRequestsSection = (options: DashboardRequestsRenderOptions = {}): void => {
        const content = host.requireUI('requests-content');
        const contentElement = narrowHTMLElement(content, 'Dashboard requests content');
        syncDashboardRequestDistributionSourceToggle(host, dependencies.viewState);

        if (dependencies.viewState.getSource() === 'apiKey' && !dependencies.hasApiKeyUsage()) {
            renderDashboardSectionState(host, contentElement, 'section-loading', i18n.t('common.loading'));
            dependencies.requestApiKeyUsage();
            return;
        }

        if (!dependencies.hasMetrics()) {
            renderDashboardSectionState(host, contentElement, 'section-loading', i18n.t('common.loading'));
            return;
        }

        const surfaces = resolveDashboardRequestsSurfaces(host, contentElement);
        dependencies.chartSizeWatcher.observe(surfaces.mount, () => renderRequestsSection());
        const metrics = dependencies.getMetrics();
        let dataset: RequestDistributionDataset | null = null;
        try {
            dataset = buildDashboardRequestDistributionDataset(metrics, dependencies.getApiKeyUsage(), dependencies.viewState.getSource());
        } catch (error) {
            errorHandler.warn('DashboardPage', 'Request distribution dataset build failed', ensureError(error));
        }

        const legendColors = resolveRequestDistributionPalette((token) => host.getStyleProp(token));
        const kind = dependencies.viewState.getChartKind();
        const rect = measureElementLayoutDimensions(surfaces.mount);
        const chartSize = Math.min(rect.width, rect.height);
        const presentation =
            dataset === null || chartSize <= 0
                ? null
                : buildRequestDistributionPresentation(
                      dataset,
                      kind,
                      chartSize,
                      chartSize,
                      (value) => formatCompactNumber(value),
                      legendColors,
                      resolveRequestDistributionOthersColor((token) => host.getStyleProp(token))
                  );
        const chartDataset = presentation?.chartDataset ?? null;
        const legendItems = presentation?.legendItems ?? [];
        const legendSignature = computeRequestDistributionLegendSignature(legendItems);

        const setEmptyChartLayout = (isEmpty: boolean): void => {
            surfaces.mount.setAttribute('data-request-distribution-chart-active', isEmpty ? 'false' : 'true');
            surfaces.mount.closest('.request-distribution-container')?.classList.toggle('request-distribution-container--empty', isEmpty);
        };
        const renderEmptyChart = (): void => {
            setEmptyChartLayout(true);
            if (!claimRequestDistributionRender(surfaces.mount, EMPTY_REQUEST_DISTRIBUTION_SIGNATURE)) {
                return;
            }
            host.replaceElementContent(surfaces.mount, renderRequestDistributionEmptyStateMarkup(resolveRequestDistributionEmptyStateText()), { escape: false });
        };
        const renderChart = (): void => {
            if (chartDataset === null || !chartDataset.entries.length || !legendColors.length) {
                renderEmptyChart();
                return;
            }
            setEmptyChartLayout(false);
            if (chartSize <= 0) {
                renderEmptyChart();
                return;
            }
            if (!claimRequestDistributionRender(surfaces.mount, computeRequestDistributionChartSignature({ kind, width: chartSize, height: chartSize, colors: legendColors, dataset: chartDataset }))) {
                return;
            }
            try {
                const markup = renderRequestDistributionChartMarkup({ width: chartSize, height: chartSize, dataset: chartDataset, colors: legendColors, kind });
                host.replaceElementContent(surfaces.mount, markup, { escape: false });
            } catch (error) {
                errorHandler.warn('DashboardPage', 'Request distribution chart render failed', ensureError(error));
                renderEmptyChart();
            }
        };
        const renderLegend = (): void => {
            const isChartActive = surfaces.mount.getAttribute('data-request-distribution-chart-active') === 'true';
            const items = isChartActive ? legendItems : [];
            const signature = items.length ? legendSignature : EMPTY_REQUEST_DISTRIBUTION_SIGNATURE;
            if (!claimRequestDistributionRender(surfaces.legend, signature, { expectsContent: items.length > 0 })) {
                return;
            }
            if (!items.length) {
                host.replaceElementContent(surfaces.legend, '');
                return;
            }
            host.replaceElementContent(surfaces.legend, buildDashboardRequestsLegendList(host, items), { escape: false });
        };
        const renderChartAndLegend = (): void => {
            renderChart();
            renderLegend();
        };
        const commitChartAndLegend = (): void => {
            if (options.transition === true) {
                surfaces.chart.style.removeProperty('opacity');
                transitionContentElements({ elements: [surfaces.mount, surfaces.legend], render: renderChartAndLegend });
                return;
            }
            renderContentImmediately({ elements: [surfaces.chart, surfaces.legend, surfaces.mount], render: renderChartAndLegend });
        };
        dependencies.viewState.attachChartKindCycle(
            surfaces.mount,
            () => {
                renderRequestsSection({ transition: true });
            },
            {
                shouldCycle: () => surfaces.mount.getAttribute('data-request-distribution-chart-active') === 'true'
            }
        );
        commitChartAndLegend();
    };

    return renderRequestsSection;
};

export { buildDashboardRequestDistributionDataset, createDashboardRequestsSectionRenderer, syncDashboardRequestDistributionSourceToggle };
export type { DashboardRequestsRenderOptions, DashboardRequestsRendererDependencies };
