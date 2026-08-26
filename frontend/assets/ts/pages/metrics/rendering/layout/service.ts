/* SoAI - Metrics page layout service [frontend/assets/ts/pages/metrics/rendering/layout/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { TrustedHtml } from '@core/security/public.ts';
import { i18n } from '@core/i18n/index.ts';
import type { MovableSectionLayoutConfig } from '@core/routing/pages/movablesections/types.ts';
import { joinUiHtml, uiAttr, uiHtml } from '@core/security/uiHtml.ts';
import { renderIconSlot } from '@core/ui/icons/view.ts';
import { resolveSortableAriaSortValue } from '@core/ui/tables/sortableTable.ts';
import { SYSTEM_STATS_CONFIG } from '@features/metrics/public.ts';
import { METRICS_ACTION_REQUEST_DISTRIBUTION_SOURCE_TOGGLE, METRICS_ACTION_SORT, METRICS_REQUEST_DISTRIBUTION_SOURCE_TOGGLE_ID, METRICS_REQUEST_DISTRIBUTION_TITLE_ID } from '@pages/metrics/actions.ts';
import { FRONTEND_TELEMETRY_ROW_CONFIG } from '@pages/metrics/contracts/metricsPageConstants.ts';
import { METRICS_GRID_SETTINGS } from '@pages/metrics/rendering/layout/constants.ts';
import type { MetricsLayoutPermissions, MetricsPanelBlueprint, MetricsPanelId } from '@pages/metrics/rendering/layout/types.ts';

const isMetricsPanelId = (value: string): value is MetricsPanelId => {
    switch (value) {
        case 'performance':
        case 'pluginHealth':
        case 'requestDistribution':
        case 'modelUsage':
        case 'apiKeyUsage':
        case 'systemPerformance':
        case 'frontendTelemetry':
            return true;
        default:
            return false;
    }
};

const resolveMetricsSectionTitle = (sectionId: MetricsPanelId): string => {
    switch (sectionId) {
        case 'performance':
            return i18n.t('metrics.cards.performanceMetrics.title');
        case 'pluginHealth':
            return i18n.t('metrics.cards.plugin_health.title');
        case 'requestDistribution':
            return i18n.t('metrics.cards.requestDistribution.titles.models');
        case 'modelUsage':
            return i18n.t('metrics.cards.modelUsage.title');
        case 'apiKeyUsage':
            return i18n.t('metrics.cards.apiKeyUsage.title');
        case 'systemPerformance':
            return i18n.t('metrics.cards.systemPerformance.title');
        case 'frontendTelemetry':
            return i18n.t('metrics.cards.frontendMetrics.title');
    }
    const unhandledSectionId: never = sectionId;
    return unhandledSectionId;
};

const createMetricsMovableLayoutConfig = (): MovableSectionLayoutConfig<MetricsPanelId> => ({
    logLabel: 'MetricsLayout',
    gridSelector: '#metrics-grid',
    sectionSelector: '.metrics-section',
    sectionClassName: 'card metrics-panel metrics-section movable-section',
    sectionIdAttribute: 'data-section-id',
    dragHandleSelector: '[data-section-handle]',
    invalidDragSelector: '.section-controls',
    settings: METRICS_GRID_SETTINGS,
    isSectionId: isMetricsPanelId,
    resolveTitle: resolveMetricsSectionTitle,
    resolveSubtitle: () => ''
});

const renderSortableHeader = (label: string, column: string, defaultSort: 'none' | 'asc' | 'desc' = 'none'): TrustedHtml => uiHtml`<th class="sortable" data-action="${METRICS_ACTION_SORT}" data-sort="${uiAttr(column)}" tabindex="0" role="columnheader" aria-sort="${resolveSortableAriaSortValue(defaultSort)}" aria-label="${uiAttr(label)}" data-tooltip="${uiAttr(label)}">${label} <span class="sort-indicator"></span></th>`;

const renderMetricsTableStateRow = (text: string, columnCount: number): TrustedHtml => uiHtml`<tr><td colspan="${uiAttr(String(columnCount))}" class="metrics-table-state">${text}</td></tr>`;

const createMetricsPanelBlueprints = (permissions: MetricsLayoutPermissions, dependencies: { requestDistributionSourceIcon: TrustedHtml }): Map<MetricsPanelId, MetricsPanelBlueprint> => {
    const requestDistributionSourceLabel = i18n.t('metrics.cards.requestDistribution.actions.showPlugins');
    const requestDistributionSourceIcon = renderIconSlot(dependencies.requestDistributionSourceIcon);
    const frontendTelemetryRows = joinUiHtml(FRONTEND_TELEMETRY_ROW_CONFIG.map((row) => uiHtml`<tr><td>${row.getLabel()}</td><td id="${uiAttr(row.id)}">${row.getInitialValue()}</td></tr>`));
    const systemStatsPlaceholder = i18n.t('common.notAvailableShort');
    const systemStatRows = joinUiHtml(SYSTEM_STATS_CONFIG.map((stat) => uiHtml`<tr><td>${stat.getLabel()}</td><td id="${uiAttr(stat.id)}">${systemStatsPlaceholder}</td></tr>`));
    const blueprints = new Map<MetricsPanelId, MetricsPanelBlueprint>();
    blueprints.set('performance', {
        rootId: 'metricsChartCard',
        className: 'history-chart-card',
        layout: { x: 0, y: 0, width: 2, height: 1 },
        showSubtitle: false,
        controls: () => uiHtml`<div id="metricsChartFilters"></div>`,
        content: uiHtml`<div class="history-chart-shell" data-card-content id="mainChartContainer"></div>`
    });
    blueprints.set('pluginHealth', {
        rootId: 'pluginHealthCard',
        className: '',
        layout: { x: 0, y: 1, width: 1, height: 1 },
        showSubtitle: false,
        controls: () => uiHtml`<span class="u-text-muted" id="pluginHealthCount">${i18n.t('metrics.cards.plugin_health.countDefault')}</span>`,
        content: uiHtml`<div class="metrics-card-content metrics-card-content--table data-table-wrapper metrics-table-wrapper has-scroll" data-card-content><table class="table table-hover table-compact plugin-health-list" id="pluginHealthList"><thead><tr>${renderSortableHeader(i18n.t('metrics.cards.plugin_health.tableHeaders.plugin'), 'name')}${renderSortableHeader(i18n.t('metrics.cards.plugin_health.tableHeaders.requests'), 'requests')}${renderSortableHeader(i18n.t('metrics.cards.plugin_health.tableHeaders.tokens'), 'tokens')}${renderSortableHeader(i18n.t('metrics.cards.plugin_health.tableHeaders.status'), 'status')}</tr></thead><tbody id="pluginHealthBody">${renderMetricsTableStateRow(i18n.t('metrics.cards.plugin_health.loadingStatus'), 4)}</tbody></table></div>`
    });
    blueprints.set('requestDistribution', {
        rootId: 'requestDistributionCard',
        className: '',
        layout: { x: 1, y: 1, width: 1, height: 1 },
        showSubtitle: false,
        controls: () => uiHtml`<button type="button" id="${METRICS_REQUEST_DISTRIBUTION_SOURCE_TOGGLE_ID}" class="ui-icon-button ui-icon-button--titlebar ui-variant-neutral" data-action="${METRICS_ACTION_REQUEST_DISTRIBUTION_SOURCE_TOGGLE}" aria-label="${uiAttr(requestDistributionSourceLabel)}" data-tooltip="${uiAttr(requestDistributionSourceLabel)}">${requestDistributionSourceIcon}</button>`,
        content: uiHtml`<h3 class="visually-hidden" id="${METRICS_REQUEST_DISTRIBUTION_TITLE_ID}">${i18n.t('metrics.cards.requestDistribution.titles.models')}</h3><div class="metrics-card-content metrics-card-content--chart-sm" data-card-content><div class="chart-container-sm"><div class="chart-container-sm__canvas"><div class="distribution-chart-3d" id="distributionChart"></div></div><div class="chart-container-sm__legend" id="distributionLegend"><div class="chart-container-sm__legend-inner" id="distributionLegendInner"></div></div></div></div>`
    });
    blueprints.set('modelUsage', {
        rootId: 'modelUsageCard',
        className: 'metrics-panel--wide',
        layout: { x: 0, y: 2, width: 2, height: 1 },
        showSubtitle: false,
        controls: () => uiHtml`<span class="u-text-muted" id="modelUsageCount">${i18n.t('metrics.cards.modelUsage.countDefault')}</span>`,
        content: uiHtml`<div class="metrics-card-content metrics-card-content--table data-table-wrapper metrics-table-wrapper has-scroll" data-card-content><table class="table table-hover table-compact model-stats-table" id="modelStatsTable"><thead><tr>${renderSortableHeader(i18n.t('metrics.cards.modelUsage.tableHeaders.model'), 'model')}${renderSortableHeader(i18n.t('metrics.cards.modelUsage.tableHeaders.requests'), 'requests')}${renderSortableHeader(i18n.t('metrics.cards.modelUsage.tableHeaders.tokens'), 'tokens')}${renderSortableHeader(i18n.t('metrics.cards.modelUsage.tableHeaders.status'), 'status')}</tr></thead><tbody id="modelStatsBody">${renderMetricsTableStateRow(i18n.t('metrics.cards.modelUsage.loadingStats'), 4)}</tbody></table></div>`
    });
    if (permissions.isAdmin) {
        blueprints.set('apiKeyUsage', {
            rootId: 'apiKeyUsageCard',
            className: 'metrics-panel--wide',
            layout: { x: 0, y: 3, width: 2, height: 1 },
            showSubtitle: false,
            content: uiHtml`<div class="metrics-card-content metrics-card-content--table data-table-wrapper metrics-table-wrapper has-scroll" data-card-content><table class="table table-hover table-compact api-key-usage-table" id="apiKeyUsageTable"><thead><tr>${renderSortableHeader(i18n.t('metrics.cards.apiKeyUsage.tableHeaders.key'), 'label')}${renderSortableHeader(i18n.t('metrics.cards.apiKeyUsage.tableHeaders.prefix'), 'prefix')}${renderSortableHeader(i18n.t('metrics.cards.apiKeyUsage.tableHeaders.status'), 'status')}${renderSortableHeader(i18n.t('metrics.cards.apiKeyUsage.tableHeaders.requests'), 'requests', 'desc')}${renderSortableHeader(i18n.t('metrics.cards.apiKeyUsage.tableHeaders.rateLimited'), 'rateLimited')}${renderSortableHeader(i18n.t('metrics.cards.apiKeyUsage.tableHeaders.lastUsed'), 'lastUsed')}</tr></thead><tbody id="apiKeyUsageBody">${renderMetricsTableStateRow(i18n.t('metrics.cards.apiKeyUsage.loading'), 6)}</tbody></table></div>`
        });
    }
    blueprints.set('systemPerformance', {
        rootId: 'systemPerformanceCard',
        className: '',
        layout: { x: 0, y: 4, width: 1, height: 1 },
        showSubtitle: false,
        content: uiHtml`<div class="metrics-card-content metrics-card-content--table data-table-wrapper metrics-table-wrapper has-scroll" data-card-content><table class="table table-hover table-compact system-stats-table" id="systemStatsTable"><thead><tr>${renderSortableHeader(i18n.t('metrics.cards.frontendMetrics.tableHeaders.metric'), 'metric')}${renderSortableHeader(i18n.t('metrics.cards.frontendMetrics.tableHeaders.value'), 'value')}</tr></thead><tbody>${systemStatRows}</tbody></table></div>`
    });
    blueprints.set('frontendTelemetry', {
        rootId: 'frontendTelemetryCard',
        className: '',
        layout: { x: 1, y: 4, width: 1, height: 1 },
        showSubtitle: false,
        content: uiHtml`<div class="metrics-card-content metrics-card-content--table data-table-wrapper metrics-table-wrapper has-scroll" data-card-content><table class="table table-hover table-compact frontend-metrics-table" id="frontendMetricsTable"><thead><tr>${renderSortableHeader(i18n.t('metrics.cards.frontendMetrics.tableHeaders.metric'), 'metric', 'asc')}${renderSortableHeader(i18n.t('metrics.cards.frontendMetrics.tableHeaders.value'), 'value')}</tr></thead><tbody>${frontendTelemetryRows}</tbody></table></div>`
    });
    return blueprints;
};

export { createMetricsMovableLayoutConfig, createMetricsPanelBlueprints, isMetricsPanelId, renderMetricsTableStateRow };
