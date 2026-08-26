/* SoAI - Charts feature chart filters contracts [frontend/assets/ts/features/charts/chartfilters/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { HistoryChartFormattingRuntimeContract } from '@features/charts/historyChartContracts.ts';
import type { FilterIdMap, FilterLabelMap, FilterOption, FilterOptionInput, FilterOptionsInput, FilterType, FilterValue } from '@features/charts/chartfilters/filterOptionTypes.ts';

interface ChartFiltersState {
    chartType: string;
    category: string | null;
    subcategory: string | null;
    timeRange: number | null;
    candleInterval: number | null;
}

interface ChartModulesData {
    formatTimeRangeMinutes?: (minutes: number) => string;
}

type ChartRuntimeContract = HistoryChartFormattingRuntimeContract & {
    getCachedModules?: () => { data?: ChartModulesData } | null | undefined;
};

interface ChartFiltersConfig {
    showChartType?: boolean | undefined;
    showCategory?: boolean | undefined;
    showSubcategory?: boolean | undefined;
    showTimeRange?: boolean | undefined;
    showCandleInterval?: boolean | undefined;
    showFullscreen?: boolean | undefined;
    fullscreenTarget?: string | Element | null | undefined;
    compactMode?: 'always' | 'auto' | undefined;
    compactBreakpoint?: number | undefined;
    chartTypes?: FilterOption[] | undefined;
    categories?: FilterOption[] | undefined;
    subcategories?: FilterOption[] | undefined;
    timeRangeOptions?: FilterOptionsInput | undefined;
    candleIntervals?: FilterOptionsInput | undefined;
    filterIds?: FilterIdMap | undefined;
    filterLabels?: FilterLabelMap | undefined;
    initialChartType?: string | undefined;
    initialCategory?: string | null | undefined;
    initialSubcategory?: string | null | undefined;
    initialTimeRange?: number | null | undefined;
    initialCandleInterval?: number | null | undefined;
}

interface InternalChartFiltersConfig {
    showChartType: boolean;
    showCategory: boolean;
    showSubcategory: boolean;
    showTimeRange: boolean;
    showCandleInterval: boolean;
    showFullscreen: boolean;
    fullscreenTarget: string | Element | null;
    compactMode: 'always' | 'auto';
    compactBreakpoint: number;
    chartTypes: FilterOption[];
    categories: FilterOption[];
    subcategories: FilterOption[];
    timeRangeOptions: FilterOptionsInput;
    candleIntervals: FilterOptionsInput;
    filterIds: FilterIdMap;
    filterLabels: FilterLabelMap;
}

interface ChartFiltersCallbacks {
    [key: string]: ((value: FilterValue, type: FilterType) => void) | undefined;
}

interface ChartFiltersElements {
    compactTrigger: HTMLButtonElement | null;
    compactPanel: HTMLDivElement | null;
    fullscreenBtn: HTMLButtonElement | null;
    filters: Partial<Record<FilterType, HTMLSelectElement | HTMLDivElement>>;
}

interface ChartFiltersOptions {
    container: Element;
    chartRuntime?: ChartRuntimeContract | undefined;
    config?: ChartFiltersConfig | undefined;
}

type FilterValueChangeHandler = (type: FilterType, value: FilterValue) => void;

interface FilterBuildOptions {
    type: FilterType;
    options: FilterOptionsInput;
    selected: FilterValue | null;
    useButtonGroup: boolean;
    onChange: FilterValueChangeHandler;
    onSync: (type: FilterType) => void;
    formatValue?: ((value: FilterValue) => string) | undefined;
}

interface RefreshFilterOptions {
    type: FilterType;
    control: HTMLSelectElement | HTMLDivElement;
    options: FilterOptionsInput;
    selected: FilterValue | null;
    formatValue?: ((value: FilterValue) => string) | undefined;
}

export type { ChartFiltersCallbacks, ChartFiltersConfig, ChartFiltersElements, ChartFiltersOptions, ChartFiltersState, ChartRuntimeContract, FilterBuildOptions, FilterIdMap, FilterLabelMap, FilterOption, FilterOptionInput, FilterOptionsInput, FilterType, FilterValue, FilterValueChangeHandler, InternalChartFiltersConfig, RefreshFilterOptions };
