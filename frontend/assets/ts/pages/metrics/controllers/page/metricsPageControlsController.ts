/* SoAI - Metrics page controls controller [frontend/assets/ts/pages/metrics/controllers/page/metricsPageControlsController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { RequestDistributionStorage } from '@core/models/requestDistributionRendering.ts';
import { requirePageControlsStorage, type PageControlsStorage, type PageControlsStorageInput } from '@core/pagecontrols/storageController.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import type { MetricsPageControlState } from '@core/storage/types.ts';
import { isFiniteNumber, isFunction, isObject } from '@core/typeGuards.ts';
import { normalizeStoredSortState } from '@core/ui/tables/sortableTable.ts';
import { API_KEY_USAGE_SORT_COLUMNS, API_KEY_USAGE_SORT_DEFAULT_DIRECTIONS, FRONTEND_TELEMETRY_SORT_COLUMNS, FRONTEND_TELEMETRY_SORT_DEFAULT_DIRECTIONS, MODEL_TABLE_SORT_COLUMNS, MODEL_TABLE_SORT_DEFAULT_DIRECTIONS, PLUGIN_HEALTH_SORT_COLUMNS, PLUGIN_HEALTH_SORT_DEFAULT_DIRECTIONS, SYSTEM_STATS_SORT_COLUMNS, SYSTEM_STATS_SORT_DEFAULT_DIRECTIONS } from '@pages/metrics/widgets/MetricsSortDefinitionsWidget.ts';

interface MetricsPageControlsStorageCandidate {
    getPageControlState?: CallableFunction;
    setPageControlState?: CallableFunction;
}

type MetricsPageControlsStorage = RequestDistributionStorage | MetricsPageControlsStorageCandidate | PageControlsStorageInput;

interface MetricsPageControlHost {
    storage: MetricsPageControlsStorage;
    currentChartType: string;
    currentMetricType: string;
    timeRange: number;
    candlestickIntervalMinutes: number;
    pluginHealthSortColumn: string;
    pluginHealthSortDirection: string;
    apiKeyUsageSortColumn: string;
    apiKeyUsageSortDirection: string;
    modelTableSortColumn: string;
    modelTableSortDirection: string;
    frontendTelemetrySortColumn: string;
    frontendTelemetrySortDirection: string;
    systemStatsSortColumn: string;
    systemStatsSortDirection: string;
}

const positiveIntegerOrFallback = (value: JsonValue, fallback: number): number => {
    return isFiniteNumber(value) && value > 0 ? Math.round(value) : fallback;
};

const isMetricsPageControlsStorageCandidate = <T>(storage: T): storage is T & MetricsPageControlsStorageCandidate => {
    return isObject(storage) && hasMetricsPageControlsStorageMethods(storage);
};

const hasMetricsPageControlsStorageMethods = (storage: MetricsPageControlsStorageCandidate): boolean => {
    return isFunction(storage.getPageControlState) && isFunction(storage.setPageControlState);
};

const requireMetricsPageControlsStorage = (storage: MetricsPageControlsStorage): PageControlsStorage => {
    if (!isMetricsPageControlsStorageCandidate(storage)) {
        throw new Error('Metrics page controls require core.storage page control methods');
    }
    return requirePageControlsStorage(storage);
};

const readMetricsPageControls = (storage: MetricsPageControlsStorage): MetricsPageControlState => {
    return requireMetricsPageControlsStorage(storage).getPageControlState('metrics');
};

const applyMetricsPageControls = (host: MetricsPageControlHost): void => {
    const state = readMetricsPageControls(host.storage);
    host.currentChartType = state.chartType || 'area';
    host.currentMetricType = state.subcategory || 'requests';
    host.timeRange = positiveIntegerOrFallback(state.timeRange, 120);
    host.candlestickIntervalMinutes = positiveIntegerOrFallback(state.candleInterval, 1);
    const pluginSort = normalizeStoredSortState({ state: state.pluginHealthSort, columns: PLUGIN_HEALTH_SORT_COLUMNS, fallback: { column: 'name', direction: 'asc' }, defaultDirections: PLUGIN_HEALTH_SORT_DEFAULT_DIRECTIONS });
    host.pluginHealthSortColumn = pluginSort.column;
    host.pluginHealthSortDirection = pluginSort.direction;
    const apiKeySort = normalizeStoredSortState({ state: state.apiKeyUsageSort, columns: API_KEY_USAGE_SORT_COLUMNS, fallback: { column: 'requests', direction: 'desc' }, defaultDirections: API_KEY_USAGE_SORT_DEFAULT_DIRECTIONS });
    host.apiKeyUsageSortColumn = apiKeySort.column;
    host.apiKeyUsageSortDirection = apiKeySort.direction;
    const modelSort = normalizeStoredSortState({ state: state.modelTableSort, columns: MODEL_TABLE_SORT_COLUMNS, fallback: { column: 'requests', direction: 'desc' }, defaultDirections: MODEL_TABLE_SORT_DEFAULT_DIRECTIONS });
    host.modelTableSortColumn = modelSort.column;
    host.modelTableSortDirection = modelSort.direction;
    const telemetrySort = normalizeStoredSortState({ state: state.frontendTelemetrySort, columns: FRONTEND_TELEMETRY_SORT_COLUMNS, fallback: { column: 'metric', direction: 'asc' }, defaultDirections: FRONTEND_TELEMETRY_SORT_DEFAULT_DIRECTIONS });
    host.frontendTelemetrySortColumn = telemetrySort.column;
    host.frontendTelemetrySortDirection = telemetrySort.direction;
    const systemStatsSort = normalizeStoredSortState({ state: state.systemStatsSort, columns: SYSTEM_STATS_SORT_COLUMNS, fallback: { column: '', direction: 'asc' }, defaultDirections: SYSTEM_STATS_SORT_DEFAULT_DIRECTIONS });
    host.systemStatsSortColumn = systemStatsSort.column;
    host.systemStatsSortDirection = systemStatsSort.direction;
};

const persistMetricsPageControls = (host: MetricsPageControlHost): void => {
    requireMetricsPageControlsStorage(host.storage).setPageControlState('metrics', {
        chartType: host.currentChartType || 'area',
        category: 'metrics',
        subcategory: host.currentMetricType || 'requests',
        timeRange: host.timeRange,
        candleInterval: host.candlestickIntervalMinutes,
        pluginHealthSort: { column: host.pluginHealthSortColumn, direction: host.pluginHealthSortDirection === 'desc' ? 'desc' : 'asc' },
        apiKeyUsageSort: { column: host.apiKeyUsageSortColumn, direction: host.apiKeyUsageSortDirection === 'asc' ? 'asc' : 'desc' },
        modelTableSort: { column: host.modelTableSortColumn, direction: host.modelTableSortDirection === 'asc' ? 'asc' : 'desc' },
        frontendTelemetrySort: { column: host.frontendTelemetrySortColumn, direction: host.frontendTelemetrySortDirection === 'desc' ? 'desc' : 'asc' },
        systemStatsSort: { column: host.systemStatsSortColumn, direction: host.systemStatsSortDirection === 'desc' ? 'desc' : 'asc' }
    });
};

export { applyMetricsPageControls, persistMetricsPageControls };
export type { MetricsPageControlHost };
