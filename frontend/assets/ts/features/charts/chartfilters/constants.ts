/* SoAI - Charts feature chart filters constants [frontend/assets/ts/features/charts/chartfilters/constants.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getIconSync } from '@core/ui/icons/iconservice/public.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import { DEFAULT_CHART_TYPE_SEQUENCE } from '@core/charts/constants.ts';
import type { FilterOption, FilterType, InternalChartFiltersConfig } from '@features/charts/chartfilters/types.ts';

const FILTER_ICON_NAMES: {
    FILTER: IconName;
    FULLSCREEN_ENTER: IconName;
    FULLSCREEN_EXIT: IconName;
} = {
    FILTER: 'filter',
    FULLSCREEN_ENTER: 'fullscreen',
    FULLSCREEN_EXIT: 'fullscreen-exit'
};

const FILTER_TYPES: {
    CHART_TYPE: FilterType;
    CATEGORY: FilterType;
    SUBCATEGORY: FilterType;
    TIME_RANGE: FilterType;
    CANDLE_INTERVAL: FilterType;
} = {
    CHART_TYPE: 'chartType',
    CATEGORY: 'category',
    SUBCATEGORY: 'subcategory',
    TIME_RANGE: 'timeRange',
    CANDLE_INTERVAL: 'candleInterval'
};

const DEFAULT_CHART_TYPES: FilterOption[] = DEFAULT_CHART_TYPE_SEQUENCE.map((value) => ({
    value
}));

const FILTER_ORDER: FilterType[] = [FILTER_TYPES.CHART_TYPE, FILTER_TYPES.CATEGORY, FILTER_TYPES.SUBCATEGORY, FILTER_TYPES.CANDLE_INTERVAL, FILTER_TYPES.TIME_RANGE];

const DEFAULT_COMPACT_BREAKPOINT = 1024;

const isFilterType = (value: string): value is FilterType => {
    return value === FILTER_TYPES.CHART_TYPE || value === FILTER_TYPES.CATEGORY || value === FILTER_TYPES.SUBCATEGORY || value === FILTER_TYPES.TIME_RANGE || value === FILTER_TYPES.CANDLE_INTERVAL;
};

const getDefaultChartType = (): string => {
    const first = DEFAULT_CHART_TYPE_SEQUENCE[0];
    if (typeof first !== 'string') {
        throw new Error('DEFAULT_CHART_TYPE_SEQUENCE must contain at least one chart type');
    }
    return first;
};

const resolveFilterId = (filterIds: InternalChartFiltersConfig['filterIds'], type: FilterType, fallback: string | null): string | null => {
    const override = filterIds[type];
    if (typeof override === 'string') {
        const normalized = override.trim();
        if (normalized) {
            return normalized;
        }
    }
    return fallback;
};

const resolveIconMarkup = (name: IconName): TrustedHtml => getIconSync(name);

export { DEFAULT_CHART_TYPES, DEFAULT_COMPACT_BREAKPOINT, FILTER_ICON_NAMES, FILTER_ORDER, FILTER_TYPES, getDefaultChartType, isFilterType, resolveFilterId, resolveIconMarkup };
