/* SoAI - Charts feature chart filters effects [frontend/assets/ts/features/charts/chartfilters/effects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isFunction } from '@core/typeGuards.ts';
import { refreshFilterControl } from '@features/charts/chartfilters/actions.ts';
import { FILTER_TYPES } from '@features/charts/chartfilters/constants.ts';
import { updateFilterState } from '@features/charts/chartfilters/state.ts';
import type { ChartFiltersElements, ChartFiltersState, FilterOption, FilterOptionsInput, FilterType, FilterValue, InternalChartFiltersConfig } from '@features/charts/chartfilters/types.ts';

interface ApplyCategoryOptionsInput {
    config: InternalChartFiltersConfig;
    state: ChartFiltersState;
    elements: ChartFiltersElements;
    categories: FilterOption[];
    syncFilter: (type: FilterType) => void;
}

interface ApplySubcategoryOptionsInput {
    config: InternalChartFiltersConfig;
    state: ChartFiltersState;
    elements: ChartFiltersElements;
    subcategories: FilterOption[];
    syncFilter: (type: FilterType) => void;
}

interface ApplyTimeRangeOptionsInput {
    config: InternalChartFiltersConfig;
    state: ChartFiltersState;
    elements: ChartFiltersElements;
    options: FilterOptionsInput;
    formatValue: (value: number) => string;
}

interface ApplyCandleIntervalsInput {
    config: InternalChartFiltersConfig;
    state: ChartFiltersState;
    elements: ChartFiltersElements;
    intervals: FilterOptionsInput;
    formatValue: (value: number) => string;
}

interface ApplyStatePatchInput {
    state: ChartFiltersState;
    nextState: Partial<ChartFiltersState>;
    syncFilter: (type: FilterType) => void;
}

const resolveStringOptionsValues = (options: FilterOption[]): string[] => options.map((option) => String(option.value));

const reconcileSelectedStringValue = (options: string[], current: string | null): string | null => {
    if (options.length === 0) {
        return current;
    }
    if (current && options.includes(current)) {
        return current;
    }
    return options[0] ?? null;
};

const refreshSelectOptions = (input: { type: FilterType; state: ChartFiltersState; control: HTMLSelectElement; options: FilterOption[]; selected: string | null; syncFilter: (type: FilterType) => void }): void => {
    const current = input.selected;
    refreshFilterControl({
        type: input.type,
        control: input.control,
        options: input.options,
        selected: current
    });
    const values = resolveStringOptionsValues(input.options);
    const next = reconcileSelectedStringValue(values, current);
    if (next !== current && next !== null) {
        updateFilterState(input.state, input.type, next);
        input.control.value = next;
        input.syncFilter(input.type);
    }
};

const applyCategoryOptions = (input: ApplyCategoryOptionsInput): void => {
    input.config.categories = input.categories;
    const control = input.elements.filters[FILTER_TYPES.CATEGORY];
    if (control instanceof HTMLSelectElement) {
        refreshSelectOptions({
            type: FILTER_TYPES.CATEGORY,
            state: input.state,
            control,
            options: input.categories,
            selected: input.state.category,
            syncFilter: input.syncFilter
        });
    }
};

const applySubcategoryOptions = (input: ApplySubcategoryOptionsInput): void => {
    input.config.subcategories = input.subcategories;
    const control = input.elements.filters[FILTER_TYPES.SUBCATEGORY];
    if (control instanceof HTMLSelectElement) {
        refreshSelectOptions({
            type: FILTER_TYPES.SUBCATEGORY,
            state: input.state,
            control,
            options: input.subcategories,
            selected: input.state.subcategory,
            syncFilter: input.syncFilter
        });
    }
};

const applyTimeRangeOptions = (input: ApplyTimeRangeOptionsInput): void => {
    input.config.timeRangeOptions = input.options;
    const control = input.elements.filters[FILTER_TYPES.TIME_RANGE];
    if (control) {
        refreshFilterControl({
            type: FILTER_TYPES.TIME_RANGE,
            control,
            options: input.options,
            selected: input.state.timeRange,
            formatValue: (value) => input.formatValue(Number(value))
        });
    }
};

const applyCandleIntervals = (input: ApplyCandleIntervalsInput): void => {
    input.config.candleIntervals = input.intervals;
    const control = input.elements.filters[FILTER_TYPES.CANDLE_INTERVAL];
    if (control instanceof HTMLSelectElement) {
        refreshFilterControl({
            type: FILTER_TYPES.CANDLE_INTERVAL,
            control,
            options: input.intervals,
            selected: input.state.candleInterval,
            formatValue: (value) => input.formatValue(Number(value))
        });
    }
};

const applyStatePatch = (input: ApplyStatePatchInput): void => {
    const patch = input.nextState;
    if (patch.chartType !== undefined) {
        updateFilterState(input.state, FILTER_TYPES.CHART_TYPE, patch.chartType);
        input.syncFilter(FILTER_TYPES.CHART_TYPE);
    }
    if (patch.category !== undefined) {
        updateFilterState(input.state, FILTER_TYPES.CATEGORY, patch.category);
        input.syncFilter(FILTER_TYPES.CATEGORY);
    }
    if (patch.subcategory !== undefined) {
        updateFilterState(input.state, FILTER_TYPES.SUBCATEGORY, patch.subcategory);
        input.syncFilter(FILTER_TYPES.SUBCATEGORY);
    }
    if (patch.timeRange !== undefined) {
        updateFilterState(input.state, FILTER_TYPES.TIME_RANGE, patch.timeRange);
        input.syncFilter(FILTER_TYPES.TIME_RANGE);
    }
    if (patch.candleInterval !== undefined) {
        updateFilterState(input.state, FILTER_TYPES.CANDLE_INTERVAL, patch.candleInterval);
        input.syncFilter(FILTER_TYPES.CANDLE_INTERVAL);
    }
};

const registerFilterCallback = (callbacks: Record<string, ((value: FilterValue, type: FilterType) => void) | undefined>, type: FilterType, callback: (value: FilterValue) => void): void => {
    if (isFunction(callback)) {
        callbacks[type] = callback;
    }
};

export { applyCandleIntervals, applyCategoryOptions, applyStatePatch, applySubcategoryOptions, applyTimeRangeOptions, registerFilterCallback };
