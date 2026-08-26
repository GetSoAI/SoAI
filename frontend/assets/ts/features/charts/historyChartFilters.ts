/* SoAI - Charts feature history chart filters [frontend/assets/ts/features/charts/historyChartFilters.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { FILTER_TYPES } from '@features/charts/chartfilters/constants.ts';
import { ChartFilters } from '@features/charts/chartfilters/service.ts';
import type { ChartFiltersConfig, FilterOptionsInput, FilterType } from '@features/charts/chartfilters/types.ts';
import type { HistoryChartRuntimeContract } from '@features/charts/historyChartContracts.ts';
import type { FilterValue } from '@features/charts/chartfilters/filterOptionTypes.ts';

interface HistoryChartFilterChangeHandlers {
    [FILTER_TYPES.CHART_TYPE]?: ((value: FilterValue) => void) | undefined;
    [FILTER_TYPES.CATEGORY]?: ((value: FilterValue) => void) | undefined;
    [FILTER_TYPES.SUBCATEGORY]?: ((value: FilterValue) => void) | undefined;
    [FILTER_TYPES.TIME_RANGE]?: ((value: FilterValue) => void) | undefined;
    [FILTER_TYPES.CANDLE_INTERVAL]?: ((value: FilterValue) => void) | undefined;
}

interface InitializeHistoryChartFiltersOptions {
    container: HTMLElement;
    pageId: string;
    chartRuntime: HistoryChartRuntimeContract;
    config: ChartFiltersConfig;
    handlers?: HistoryChartFilterChangeHandlers | undefined;
}

const filterTypes: readonly FilterType[] = [FILTER_TYPES.CHART_TYPE, FILTER_TYPES.CATEGORY, FILTER_TYPES.SUBCATEGORY, FILTER_TYPES.TIME_RANGE, FILTER_TYPES.CANDLE_INTERVAL];

const resolveOptions = (configured: FilterOptionsInput | undefined, defaults: readonly number[], label: string): FilterOptionsInput => {
    if (configured !== undefined) {
        return [...configured];
    }
    if (defaults.length === 0) {
        throw new Error(`History chart filters require at least one ${label} option`);
    }
    return [...defaults];
};

const initializeHistoryChartFilters = ({ container, pageId, chartRuntime, config, handlers = {} }: InitializeHistoryChartFiltersOptions): ChartFilters => {
    container.dataset['chartFiltersPage'] = pageId;
    container.dataset['chartFiltersLayout'] = 'titlebar-inline';
    const defaults = chartRuntime.getDefaults();
    const resolvedConfig: ChartFiltersConfig = {
        showChartType: true,
        showTimeRange: true,
        showCandleInterval: true,
        compactBreakpoint: 1400,
        ...config
    };
    if (resolvedConfig.showTimeRange !== false) {
        resolvedConfig.timeRangeOptions = resolveOptions(config.timeRangeOptions, defaults.timeRanges, 'time range');
    }
    if (resolvedConfig.showCandleInterval !== false) {
        resolvedConfig.candleIntervals = resolveOptions(config.candleIntervals, defaults.candleIntervals, 'candlestick interval');
    }
    const chartFilters = new ChartFilters({
        container,
        chartRuntime,
        config: resolvedConfig
    });
    chartFilters.render();
    for (const filterType of filterTypes) {
        const handler = handlers[filterType];
        if (!handler) {
            continue;
        }
        chartFilters.onFilterChange(filterType, handler);
    }
    return chartFilters;
};

export { initializeHistoryChartFilters };
export type { HistoryChartFilterChangeHandlers, InitializeHistoryChartFiltersOptions };
