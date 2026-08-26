/* SoAI - Metrics page widgets events [frontend/assets/ts/pages/metrics/widgets/events.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getCurrentLocale } from '@core/languageservice/service.ts';
import { applyAdaptiveNumbers, resolveAdaptiveNumberText } from '@core/ui/adaptiveNumber.ts';
import { updateFrontendTelemetrySortIndicators, updateModelTableSortIndicators, updatePluginHealthSortIndicators, updateSystemStatsSortIndicators } from '@pages/metrics/widgets/effects.ts';
import { updateModelTable, updatePluginHealth } from '@pages/metrics/widgets/service.ts';
import { FRONTEND_TELEMETRY_SORT_COLUMNS, FRONTEND_TELEMETRY_SORT_DEFAULT_DIRECTIONS, MODEL_TABLE_SORT_COLUMNS, MODEL_TABLE_SORT_DEFAULT_DIRECTIONS, PLUGIN_HEALTH_SORT_COLUMNS, PLUGIN_HEALTH_SORT_DEFAULT_DIRECTIONS, SYSTEM_STATS_SORT_COLUMNS, SYSTEM_STATS_SORT_DEFAULT_DIRECTIONS, resolveMetricsNextSortState } from '@pages/metrics/widgets/MetricsSortDefinitionsWidget.ts';
import type { MetricsPageWidgetHost } from '@pages/metrics/widgets/types.ts';

const handlePluginHealthSort = (host: MetricsPageWidgetHost, column: string): void => {
    const next = resolveMetricsNextSortState(host.state.pluginHealthSortColumn, host.state.pluginHealthSortDirection, column, PLUGIN_HEALTH_SORT_COLUMNS, PLUGIN_HEALTH_SORT_DEFAULT_DIRECTIONS, 'plugin health');
    host.state.pluginHealthSortColumn = next.column;
    host.state.pluginHealthSortDirection = next.direction;
    updatePluginHealth(host);
};

const handleModelTableSort = (host: MetricsPageWidgetHost, column: string): void => {
    const next = resolveMetricsNextSortState(host.state.modelTableSortColumn, host.state.modelTableSortDirection, column, MODEL_TABLE_SORT_COLUMNS, MODEL_TABLE_SORT_DEFAULT_DIRECTIONS, 'model metrics');
    host.state.modelTableSortColumn = next.column;
    host.state.modelTableSortDirection = next.direction;
    updateModelTable(host);
};

const applyFrontendTelemetrySort = (host: MetricsPageWidgetHost): void => {
    const context = host.operations.resolveTableBodyContext('frontendMetricsTable');
    if (!context) {
        return;
    }
    const { bodyElement, rows } = context;
    const column = host.state.frontendTelemetrySortColumn || 'metric';
    const direction = host.state.frontendTelemetrySortDirection === 'desc' ? -1 : 1;
    const valueForRow = (row: HTMLTableRowElement): string => {
        if (!row.cells || row.cells.length < 2) {
            return '';
        }
        const cell0 = row.cells[0];
        const cell1 = row.cells[1];
        if (!cell0 || !cell1) {
            return '';
        }
        if (column === 'value') {
            return (cell1.textContent || '').trim();
        }
        return (cell0.textContent || '').trim();
    };

    const sorted = [...rows].sort((firstValue, secondValue) => {
        const av = valueForRow(firstValue);
        const bv = valueForRow(secondValue);
        return direction * av.localeCompare(bv, getCurrentLocale(), { sensitivity: 'base', numeric: true });
    });

    for (const row of sorted) {
        bodyElement.appendChild(row);
    }
    updateFrontendTelemetrySortIndicators(host);
    host.owners.pageElements.enableCheckerboard(bodyElement, 'tr');
    applyAdaptiveNumbers(bodyElement);
};

const handleFrontendTelemetrySort = (host: MetricsPageWidgetHost, column: string): void => {
    const next = resolveMetricsNextSortState(host.state.frontendTelemetrySortColumn, host.state.frontendTelemetrySortDirection, column, FRONTEND_TELEMETRY_SORT_COLUMNS, FRONTEND_TELEMETRY_SORT_DEFAULT_DIRECTIONS, 'frontend telemetry');
    host.state.frontendTelemetrySortColumn = next.column;
    host.state.frontendTelemetrySortDirection = next.direction;
    applyFrontendTelemetrySort(host);
};

const applySystemStatsSort = (host: MetricsPageWidgetHost): void => {
    const context = host.operations.resolveTableBodyContext('systemStatsTable');
    if (!context) {
        return;
    }
    const { bodyElement, rows } = context;
    const column = host.state.systemStatsSortColumn || '';
    if (column !== 'metric' && column !== 'value') {
        updateSystemStatsSortIndicators(host);
        host.owners.pageElements.enableCheckerboard(bodyElement, 'tr');
        applyAdaptiveNumbers(bodyElement);
        return;
    }
    const direction = host.state.systemStatsSortDirection === 'desc' ? -1 : 1;
    const valueForRow = (row: HTMLTableRowElement): { label: string; numeric: number } => {
        if (!row.cells || row.cells.length < 2) {
            return { label: '', numeric: 0 };
        }
        const cell0 = row.cells[0];
        const cell1 = row.cells[1];
        if (!cell0 || !cell1) {
            return { label: '', numeric: 0 };
        }
        const label = (cell0.textContent || '').trim();
        const valueText = resolveAdaptiveNumberText(cell1);
        const numeric = Number.parseFloat(valueText.replace(/[^0-9.+-]/g, ''));
        return { label, numeric: Number.isFinite(numeric) ? numeric : 0 };
    };

    const sorted = [...rows].sort((firstValue, secondValue) => {
        const av = valueForRow(firstValue);
        const bv = valueForRow(secondValue);
        if (column === 'value') {
            if (av.numeric !== bv.numeric) {
                return direction * (av.numeric - bv.numeric);
            }
            return direction * av.label.localeCompare(bv.label, getCurrentLocale(), { sensitivity: 'base', numeric: true });
        }
        return direction * av.label.localeCompare(bv.label, getCurrentLocale(), { sensitivity: 'base', numeric: true });
    });

    for (const row of sorted) {
        bodyElement.appendChild(row);
    }
    updateSystemStatsSortIndicators(host);
    host.owners.pageElements.enableCheckerboard(bodyElement, 'tr');
    applyAdaptiveNumbers(bodyElement);
};

const handleSystemStatsSort = (host: MetricsPageWidgetHost, column: string): void => {
    const next = resolveMetricsNextSortState(host.state.systemStatsSortColumn, host.state.systemStatsSortDirection, column, SYSTEM_STATS_SORT_COLUMNS, SYSTEM_STATS_SORT_DEFAULT_DIRECTIONS, 'system stats');
    host.state.systemStatsSortColumn = next.column;
    host.state.systemStatsSortDirection = next.direction;
    applySystemStatsSort(host);
};

export { applyFrontendTelemetrySort, applySystemStatsSort, handleFrontendTelemetrySort, handleModelTableSort, handlePluginHealthSort, handleSystemStatsSort, updateFrontendTelemetrySortIndicators, updateModelTableSortIndicators, updatePluginHealthSortIndicators, updateSystemStatsSortIndicators };
