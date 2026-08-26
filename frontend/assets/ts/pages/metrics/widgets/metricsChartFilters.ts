/* SoAI - Metrics page chart filters [frontend/assets/ts/pages/metrics/widgets/metricsChartFilters.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { ChartFilters, FILTER_TYPES, initializeHistoryChartFilters, type HistoryChartRuntimeContract } from '@features/charts/public.ts';
import type { MetricTypeOption } from '@pages/metrics/contracts/metricsPageConstants.ts';

interface MetricsChartFiltersDependencies {
    container: HTMLElement;
    chartRuntime: HistoryChartRuntimeContract;
    metricTypeOptions: readonly MetricTypeOption[];
    timeRangeOptions: number[];
    candleIntervals: number[];
    initial: {
        chartType: string;
        metricType: string;
        timeRange: number;
        candleIntervalMinutes: number;
    };
    handlers: {
        onChartTypeChange: (value: string | number) => void;
        onMetricTypeChange: (value: string | number) => void;
        onTimeRangeChange: (value: string | number) => void;
        onCandleIntervalChange: (value: string | number) => void;
    };
}

const initializeMetricsChartFilters = (dependencies: MetricsChartFiltersDependencies): ChartFilters => {
    const { container, chartRuntime, metricTypeOptions, timeRangeOptions, candleIntervals, initial, handlers } = dependencies;
    return initializeHistoryChartFilters({
        container,
        pageId: 'metrics',
        chartRuntime,
        config: {
            showCategory: false,
            showSubcategory: true,
            categories: [{ value: 'metrics', label: i18n.t('metrics.cards.performanceMetrics.title') }],
            subcategories: metricTypeOptions.map((option) => ({ value: option.value, label: option.getLabel() })),
            timeRangeOptions,
            candleIntervals,
            initialChartType: initial.chartType,
            initialCategory: 'metrics',
            initialSubcategory: initial.metricType,
            initialTimeRange: initial.timeRange,
            initialCandleInterval: initial.candleIntervalMinutes,
            filterLabels: {
                [FILTER_TYPES.CATEGORY]: i18n.t('metrics.cards.performanceMetrics.metricFilterLabel'),
                [FILTER_TYPES.SUBCATEGORY]: i18n.t('metrics.cards.performanceMetrics.metricFilterLabel')
            },
            filterIds: { [FILTER_TYPES.SUBCATEGORY]: 'metricTypeSelect' }
        },
        handlers: {
            [FILTER_TYPES.CHART_TYPE]: handlers.onChartTypeChange,
            [FILTER_TYPES.SUBCATEGORY]: handlers.onMetricTypeChange,
            [FILTER_TYPES.TIME_RANGE]: handlers.onTimeRangeChange,
            [FILTER_TYPES.CANDLE_INTERVAL]: handlers.onCandleIntervalChange
        }
    });
};

export { initializeMetricsChartFilters };
