/* SoAI - Frontend operational preference persistence serialization [frontend/assets/ts/core/storage/persistence/operationalPreferenceSerialization.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { FiltersCache, HardwareCache, HardwarePageControlState, MetricsPageControlState, PageControlStates, PageSortState } from '@core/storage/types.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';

const serializeSortState = (state: PageSortState): JsonObject => ({
    column: state.column,
    direction: state.direction
});

const serializeChartState = (state: MetricsPageControlState | HardwarePageControlState): JsonObject => ({
    'chart_type': state.chartType,
    category: state.category,
    subcategory: state.subcategory,
    'time_range': state.timeRange,
    'candle_interval': state.candleInterval
});

const serializeMetricsState = (state: MetricsPageControlState): JsonObject => ({
    ...serializeChartState(state),
    'plugin_health_sort': serializeSortState(state.pluginHealthSort),
    'api_key_usage_sort': serializeSortState(state.apiKeyUsageSort),
    'model_table_sort': serializeSortState(state.modelTableSort),
    'frontend_telemetry_sort': serializeSortState(state.frontendTelemetrySort),
    'system_stats_sort': serializeSortState(state.systemStatsSort)
});

const serializeHardwarePageState = (state: HardwarePageControlState): JsonObject => ({
    ...serializeChartState(state),
    'process_sort': serializeSortState(state.processSort)
});

const serializePageControlStates = (states: PageControlStates): JsonObject => ({
    models: {
        'filter_provider': states.models.filterProvider,
        'sort_by': states.models.sortBy,
        'sort_order': states.models.sortOrder
    },
    plugins: {
        'filter_provider': states.plugins.filterProvider,
        'filter_status': states.plugins.filterStatus,
        'sort_by': states.plugins.sortBy,
        'sort_order': states.plugins.sortOrder
    },
    prompts: {
        'sort_by': states.prompts.sortBy,
        'sort_order': states.prompts.sortOrder
    },
    fileExplorer: {
        'sort_by': states.fileExplorer.sortBy,
        'sort_order': states.fileExplorer.sortOrder
    },
    modelDetail: {
        'parameter_filter': states.modelDetail.parameterFilter
    },
    logs: {
        source: states.logs.source
    },
    metrics: serializeMetricsState(states.metrics),
    hardware: serializeHardwarePageState(states.hardware),
    osNetwork: serializeSortState(states.osNetwork),
    osStorage: serializeSortState(states.osStorage),
    updates: serializeSortState(states.updates)
});

const serializeFiltersCache = (cache: FiltersCache): JsonObject => ({
    'page_controls': serializePageControlStates(cache.pageControls)
});

const serializeHardwareCache = (cache: HardwareCache): JsonObject => ({
    'refresh_interval': cache.refreshInterval,
    'show_graphs': cache.showGraphs,
    'graph_time_range': cache.graphTimeRange,
    'gpu_settings': cache.gpuSettings
});

export { serializeFiltersCache, serializeHardwareCache, serializePageControlStates };
