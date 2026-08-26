/* SoAI - Charts feature chart filters state [frontend/assets/ts/features/charts/chartfilters/state.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isArray, isObject, isString } from '@core/typeGuards.ts';
import { normalizeChartTypeToken } from '@features/charts/chartTypeNormalization.ts';
import { DEFAULT_CHART_TYPES, DEFAULT_COMPACT_BREAKPOINT, FILTER_TYPES, FILTER_ORDER, getDefaultChartType } from '@features/charts/chartfilters/constants.ts';
import type { ChartFiltersConfig, ChartFiltersState, FilterIdMap, FilterLabelMap, FilterType, FilterValue, InternalChartFiltersConfig } from '@features/charts/chartfilters/types.ts';

const resolveFilterLabels = (config: ChartFiltersConfig['filterLabels']): FilterLabelMap => {
    const resolved: FilterLabelMap = {};
    if (!isObject(config)) {
        return resolved;
    }
    for (const type of FILTER_ORDER) {
        const value = config[type];
        if (isString(value)) {
            const normalized = value.trim();
            if (normalized) {
                resolved[type] = normalized;
            }
        }
    }
    return resolved;
};

const resolveCompactMode = (mode: ChartFiltersConfig['compactMode']): InternalChartFiltersConfig['compactMode'] => (mode === 'always' ? 'always' : 'auto');

const resolveCompactBreakpoint = (value: ChartFiltersConfig['compactBreakpoint']): number => {
    if (typeof value === 'number' && Number.isFinite(value) && value > 0) {
        return Math.round(value);
    }
    return DEFAULT_COMPACT_BREAKPOINT;
};

const resolveFilterIdMap = (config?: ChartFiltersConfig['filterIds']): FilterIdMap => {
    const normalized: FilterIdMap = {};
    if (!isObject(config)) {
        return normalized;
    }
    for (const type of FILTER_ORDER) {
        const value = config[type];
        if (isString(value)) {
            normalized[type] = value;
        }
    }
    return normalized;
};

const resolveFilterTypeList = <T>(value: T[] | undefined, fallback: readonly T[]): T[] => (isArray(value) && value.length > 0 ? [...value] : [...fallback]);

const createChartFiltersConfig = (config: ChartFiltersConfig = {}): InternalChartFiltersConfig => ({
    showChartType: config.showChartType !== false,
    showCategory: config.showCategory !== false,
    showSubcategory: config.showSubcategory !== false,
    showTimeRange: config.showTimeRange !== false,
    showCandleInterval: config.showCandleInterval !== false,
    showFullscreen: config.showFullscreen !== false,
    fullscreenTarget: config.fullscreenTarget ?? null,
    compactMode: resolveCompactMode(config.compactMode),
    compactBreakpoint: resolveCompactBreakpoint(config.compactBreakpoint),
    chartTypes: resolveFilterTypeList(config.chartTypes, DEFAULT_CHART_TYPES),
    categories: isArray(config.categories) ? [...config.categories] : [],
    subcategories: isArray(config.subcategories) ? [...config.subcategories] : [],
    timeRangeOptions: isArray(config.timeRangeOptions) ? [...config.timeRangeOptions] : [],
    candleIntervals: isArray(config.candleIntervals) ? [...config.candleIntervals] : [],
    filterIds: resolveFilterIdMap(config.filterIds),
    filterLabels: resolveFilterLabels(config.filterLabels)
});

const createChartFiltersState = (config: ChartFiltersConfig = {}): ChartFiltersState => ({
    chartType: resolveChartTypeValue(config.initialChartType ?? getDefaultChartType()),
    category: config.initialCategory ?? null,
    subcategory: config.initialSubcategory ?? null,
    timeRange: config.initialTimeRange === null || config.initialTimeRange === undefined ? null : resolvePositiveNumberValue(config.initialTimeRange, FILTER_TYPES.TIME_RANGE),
    candleInterval: config.initialCandleInterval === null || config.initialCandleInterval === undefined ? null : resolvePositiveNumberValue(config.initialCandleInterval, FILTER_TYPES.CANDLE_INTERVAL)
});

const resolveChartTypeValue = (value: FilterValue): string => {
    const normalized = normalizeChartTypeToken(value);
    if (!normalized) {
        throw new TypeError('Chart type filter requires a non-empty string value');
    }
    return normalized;
};

const resolveStringValue = (value: FilterValue | null): string | null => {
    if (value === null) {
        return null;
    }
    const normalized = String(value).trim();
    if (!normalized) {
        throw new TypeError('Chart text filter requires a non-empty value');
    }
    return normalized;
};

const resolvePositiveNumberValue = (value: FilterValue, type: FilterType): number => {
    const normalized = Math.round(Number(value));
    if (!Number.isFinite(normalized) || normalized <= 0) {
        throw new TypeError(`Chart ${type} filter requires a positive numeric value`);
    }
    return normalized;
};

const updateFilterState = (state: ChartFiltersState, type: FilterType, value: FilterValue | null): void => {
    if (type === FILTER_TYPES.CHART_TYPE) {
        if (value !== null) {
            state.chartType = resolveChartTypeValue(value);
        }
        return;
    }
    if (type === FILTER_TYPES.CATEGORY) {
        state.category = resolveStringValue(value);
        return;
    }
    if (type === FILTER_TYPES.SUBCATEGORY) {
        state.subcategory = resolveStringValue(value);
        return;
    }
    if (type === FILTER_TYPES.TIME_RANGE) {
        state.timeRange = value === null ? null : resolvePositiveNumberValue(value, type);
        return;
    }
    if (type === FILTER_TYPES.CANDLE_INTERVAL) {
        state.candleInterval = value === null ? null : resolvePositiveNumberValue(value, type);
    }
};

const readFilterValue = (state: ChartFiltersState, type: FilterType): FilterValue | null => {
    if (type === FILTER_TYPES.CHART_TYPE) return state.chartType;
    if (type === FILTER_TYPES.CATEGORY) return state.category;
    if (type === FILTER_TYPES.SUBCATEGORY) return state.subcategory;
    if (type === FILTER_TYPES.TIME_RANGE) return state.timeRange;
    if (type === FILTER_TYPES.CANDLE_INTERVAL) return state.candleInterval;
    return null;
};

const resolveInitialSelection = <T extends FilterValue>(stateValue: T | null | undefined, values: readonly FilterValue[]): FilterValue => {
    if (stateValue !== null && stateValue !== undefined) {
        return stateValue;
    }
    const first = values[0];
    return first === undefined ? '' : first;
};

export { createChartFiltersConfig, createChartFiltersState, readFilterValue, updateFilterState, resolveInitialSelection };
