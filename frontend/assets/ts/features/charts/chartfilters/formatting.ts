/* SoAI - Charts feature formatting [frontend/assets/ts/features/charts/chartfilters/formatting.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { isFunction } from '@core/typeGuards.ts';
import { FILTER_TYPES } from '@features/charts/chartfilters/constants.ts';
import type { ChartRuntimeContract, FilterLabelMap, FilterType, FilterValue } from '@features/charts/chartfilters/types.ts';
import { formatBucketedTimeRangeMinutes } from '@features/charts/timeRangeFormatting.ts';

const resolveChartFilterLabel = (type: FilterType, overrides: FilterLabelMap): string => {
    const override = overrides[type];
    if (typeof override === 'string' && override) {
        return override;
    }
    switch (type) {
        case FILTER_TYPES.CHART_TYPE:
            return i18n.t('charts.filters.chartType.label');
        case FILTER_TYPES.CATEGORY:
            return i18n.t('charts.filters.category.label');
        case FILTER_TYPES.SUBCATEGORY:
            return i18n.t('charts.filters.subcategory.label');
        case FILTER_TYPES.TIME_RANGE:
            return i18n.t('charts.filters.timeRange.label');
        case FILTER_TYPES.CANDLE_INTERVAL:
            return i18n.t('charts.filters.candleInterval.label');
        default:
            throw new Error(`ChartFilters cannot resolve label for type "${String(type)}"`);
    }
};

const formatTimeRangeMinutes = (minutes: number, chartRuntime: ChartRuntimeContract | null | undefined): string => {
    const modules = chartRuntime?.getCachedModules?.()?.data;
    if (isFunction(modules?.formatTimeRangeMinutes)) {
        return modules.formatTimeRangeMinutes(minutes);
    }
    return formatBucketedTimeRangeMinutes(minutes);
};

const resolveChartTypeLabel = (value: FilterValue): string => {
    const normalized = String(value);
    switch (normalized) {
        case 'line':
            return i18n.t('charts.filters.chartType.line');
        case 'precision-line':
            return i18n.t('charts.filters.chartType.precision-line');
        case 'area':
            return i18n.t('charts.filters.chartType.area');
        case 'deviation':
            return i18n.t('charts.filters.chartType.deviation');
        case 'bar':
            return i18n.t('charts.filters.chartType.bar');
        case 'candlestick':
            return i18n.t('charts.filters.chartType.candlestick');
        default:
            return normalized;
    }
};

export { formatTimeRangeMinutes, resolveChartFilterLabel, resolveChartTypeLabel };
