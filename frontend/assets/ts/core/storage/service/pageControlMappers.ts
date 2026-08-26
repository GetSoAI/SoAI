/* SoAI - Shared storage page control mappers [frontend/assets/ts/core/storage/service/pageControlMappers.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ChartPageControlState, HardwarePageControlState, MetricsPageControlState, PageControlPageId, PageControlStates, PageSortState } from '@core/storage/types.ts';
import { isFiniteNumber, isObject, isString } from '@core/typeGuards.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';

const readString = (value: JsonValue | null | undefined, current: string): string => (isString(value) && value.trim() ? value.trim() : current);

const readPositiveInteger = (value: JsonValue | null | undefined, current: number): number => (isFiniteNumber(value) && value > 0 ? Math.round(value) : current);

const readSortDirection = (value: JsonValue | null | undefined, current: PageSortState['direction']): PageSortState['direction'] => (value === 'desc' ? 'desc' : value === 'asc' ? 'asc' : current);

const applySortStatePatch = (patch: JsonValue | null | undefined, target: PageSortState): void => {
    if (!isObject(patch)) {
        return;
    }
    target.column = readString(patch['column'], target.column);
    target.direction = readSortDirection(patch['direction'], target.direction);
};

const applyChartStatePatch = (patch: JsonValue | null | undefined, target: ChartPageControlState): void => {
    if (!isObject(patch)) {
        return;
    }
    target.chartType = readString(patch['chart_type'], target.chartType);
    target.category = readString(patch['category'], target.category);
    target.subcategory = readString(patch['subcategory'], target.subcategory);
    target.timeRange = readPositiveInteger(patch['time_range'], target.timeRange);
    target.candleInterval = readPositiveInteger(patch['candle_interval'], target.candleInterval);
};

const applyChartStateUpdate = (patch: JsonValue | null | undefined, target: ChartPageControlState): void => {
    if (!isObject(patch)) {
        return;
    }
    target.chartType = readString(patch['chartType'], target.chartType);
    target.category = readString(patch['category'], target.category);
    target.subcategory = readString(patch['subcategory'], target.subcategory);
    target.timeRange = readPositiveInteger(patch['timeRange'], target.timeRange);
    target.candleInterval = readPositiveInteger(patch['candleInterval'], target.candleInterval);
};

const applyMetricsPatch = (patch: JsonValue | null | undefined, target: MetricsPageControlState): void => {
    if (!isObject(patch)) {
        return;
    }
    applyChartStatePatch(patch, target);
    applySortStatePatch(patch['plugin_health_sort'], target.pluginHealthSort);
    applySortStatePatch(patch['api_key_usage_sort'], target.apiKeyUsageSort);
    applySortStatePatch(patch['model_table_sort'], target.modelTableSort);
    applySortStatePatch(patch['frontend_telemetry_sort'], target.frontendTelemetrySort);
    applySortStatePatch(patch['system_stats_sort'], target.systemStatsSort);
};

const applyHardwarePatch = (patch: JsonValue | null | undefined, target: HardwarePageControlState): void => {
    if (!isObject(patch)) {
        return;
    }
    applyChartStatePatch(patch, target);
    applySortStatePatch(patch['process_sort'], target.processSort);
};

const applyMetricsUpdate = (patch: JsonValue | null | undefined, target: MetricsPageControlState): void => {
    if (!isObject(patch)) {
        return;
    }
    applyChartStateUpdate(patch, target);
    applySortStatePatch(patch['pluginHealthSort'], target.pluginHealthSort);
    applySortStatePatch(patch['apiKeyUsageSort'], target.apiKeyUsageSort);
    applySortStatePatch(patch['modelTableSort'], target.modelTableSort);
    applySortStatePatch(patch['frontendTelemetrySort'], target.frontendTelemetrySort);
    applySortStatePatch(patch['systemStatsSort'], target.systemStatsSort);
};

const applyHardwareUpdate = (patch: JsonValue | null | undefined, target: HardwarePageControlState): void => {
    if (!isObject(patch)) {
        return;
    }
    applyChartStateUpdate(patch, target);
    applySortStatePatch(patch['processSort'], target.processSort);
};

const applyPageControlStateUpdate = (pageId: PageControlPageId, patch: JsonValue | null | undefined, target: PageControlStates): void => {
    if (!isObject(patch)) {
        return;
    }
    if (pageId === 'models') {
        target.models.filterProvider = readString(patch['filterProvider'], target.models.filterProvider);
        target.models.sortBy = readString(patch['sortBy'], target.models.sortBy);
        target.models.sortOrder = readSortDirection(patch['sortOrder'], target.models.sortOrder);
        return;
    }
    if (pageId === 'plugins') {
        target.plugins.filterProvider = readString(patch['filterProvider'], target.plugins.filterProvider);
        target.plugins.filterStatus = readString(patch['filterStatus'], target.plugins.filterStatus);
        target.plugins.sortBy = readString(patch['sortBy'], target.plugins.sortBy);
        target.plugins.sortOrder = readSortDirection(patch['sortOrder'], target.plugins.sortOrder);
        return;
    }
    if (pageId === 'prompts') {
        target.prompts.sortBy = readString(patch['sortBy'], target.prompts.sortBy);
        target.prompts.sortOrder = readSortDirection(patch['sortOrder'], target.prompts.sortOrder);
        return;
    }
    if (pageId === 'fileExplorer') {
        target.fileExplorer.sortBy = readString(patch['sortBy'], target.fileExplorer.sortBy);
        target.fileExplorer.sortOrder = readSortDirection(patch['sortOrder'], target.fileExplorer.sortOrder);
        return;
    }
    if (pageId === 'modelDetail') {
        target.modelDetail.parameterFilter = readString(patch['parameterFilter'], target.modelDetail.parameterFilter);
        return;
    }
    if (pageId === 'logs') {
        target.logs.source = readString(patch['source'], target.logs.source);
        return;
    }
    if (pageId === 'metrics') {
        applyMetricsUpdate(patch, target.metrics);
        return;
    }
    if (pageId === 'hardware') {
        applyHardwareUpdate(patch, target.hardware);
        return;
    }
    if (pageId === 'osNetwork' || pageId === 'osStorage' || pageId === 'updates') {
        applySortStatePatch(patch, target[pageId]);
        return;
    }
    const unsupportedPageId: never = pageId;
    throw new Error(`Unsupported page control page: ${unsupportedPageId}`);
};

const applySerializedPageControlStatePatch = (pageId: PageControlPageId, patch: JsonValue | null | undefined, target: PageControlStates): void => {
    if (!isObject(patch)) {
        return;
    }
    if (pageId === 'models') {
        target.models.filterProvider = readString(patch['filter_provider'], target.models.filterProvider);
        target.models.sortBy = readString(patch['sort_by'], target.models.sortBy);
        target.models.sortOrder = readSortDirection(patch['sort_order'], target.models.sortOrder);
        return;
    }
    if (pageId === 'plugins') {
        target.plugins.filterProvider = readString(patch['filter_provider'], target.plugins.filterProvider);
        target.plugins.filterStatus = readString(patch['filter_status'], target.plugins.filterStatus);
        target.plugins.sortBy = readString(patch['sort_by'], target.plugins.sortBy);
        target.plugins.sortOrder = readSortDirection(patch['sort_order'], target.plugins.sortOrder);
        return;
    }
    if (pageId === 'prompts') {
        target.prompts.sortBy = readString(patch['sort_by'], target.prompts.sortBy);
        target.prompts.sortOrder = readSortDirection(patch['sort_order'], target.prompts.sortOrder);
        return;
    }
    if (pageId === 'fileExplorer') {
        target.fileExplorer.sortBy = readString(patch['sort_by'], target.fileExplorer.sortBy);
        target.fileExplorer.sortOrder = readSortDirection(patch['sort_order'], target.fileExplorer.sortOrder);
        return;
    }
    if (pageId === 'modelDetail') {
        target.modelDetail.parameterFilter = readString(patch['parameter_filter'], target.modelDetail.parameterFilter);
        return;
    }
    if (pageId === 'logs') {
        target.logs.source = readString(patch['source'], target.logs.source);
        return;
    }
    if (pageId === 'metrics') {
        applyMetricsPatch(patch, target.metrics);
        return;
    }
    if (pageId === 'hardware') {
        applyHardwarePatch(patch, target.hardware);
        return;
    }
    if (pageId === 'osNetwork') {
        applySortStatePatch(patch, target.osNetwork);
        return;
    }
    if (pageId === 'osStorage') {
        applySortStatePatch(patch, target.osStorage);
        return;
    }
    if (pageId === 'updates') {
        applySortStatePatch(patch, target.updates);
        return;
    }
    const unsupportedPageId: never = pageId;
    throw new Error(`Unsupported page control page: ${unsupportedPageId}`);
};

const applyPageControlStatesPatch = (patch: JsonValue | null | undefined, target: PageControlStates): void => {
    if (!isObject(patch)) {
        return;
    }
    applySerializedPageControlStatePatch('models', patch['models'], target);
    applySerializedPageControlStatePatch('plugins', patch['plugins'], target);
    applySerializedPageControlStatePatch('prompts', patch['prompts'], target);
    applySerializedPageControlStatePatch('fileExplorer', patch['fileExplorer'], target);
    applySerializedPageControlStatePatch('modelDetail', patch['modelDetail'], target);
    applySerializedPageControlStatePatch('logs', patch['logs'], target);
    applySerializedPageControlStatePatch('metrics', patch['metrics'], target);
    applySerializedPageControlStatePatch('hardware', patch['hardware'], target);
    applySerializedPageControlStatePatch('osNetwork', patch['osNetwork'], target);
    applySerializedPageControlStatePatch('osStorage', patch['osStorage'], target);
    applySerializedPageControlStatePatch('updates', patch['updates'], target);
};

export { applyPageControlStateUpdate, applyPageControlStatesPatch };
