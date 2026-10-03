/* SoAI - Metrics page state [frontend/assets/ts/pages/metrics/controllers/page/state.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { CHART_FULL_VALUE_LIMIT } from '@core/charts/constants.ts';
import { formatInvariantNumber } from '@core/localization/public.ts';
import { formatCompactNumber } from '@core/primitives/compactNumber.ts';
import { serverEpochMs } from '@core/time/clock.ts';
import { isFiniteNumber } from '@core/typeGuards.ts';
import { buildChartColorContext } from '@core/ui/chartColors.ts';
import { computeHistoryChartPointBudget, isCandlestickModeActive, resolveCandlestickIntervalMs, resolveHistoryChartPlotWidthPx, type HistoryChartPointBudgetConfig } from '@features/charts/public.ts';
import { METRIC_HISTORY_AGGREGATIONS, METRIC_HISTORY_KEYS, METRIC_HISTORY_OHLC_AGGREGATIONS, METRIC_SCALE_BOUNDS, resolveMetricsCurrentTokenRateOrNull, type ScaleBound } from '@features/metrics/public.ts';
import { METRIC_TYPE_OPTIONS } from '@pages/metrics/contracts/metricsPageConstants.ts';
import type { MetricsPageBudgetHost, MetricsPageStateHost } from '@pages/metrics/controllers/page/contracts.ts';
import type { MetricsData, ScaleBounds } from '@pages/metrics/types.ts';

const updateMetricsChartConfiguration = (host: MetricsPageStateHost): void => {
    const chart = host.state.mainChart;
    chart?.settings.update({
        scaleBounds: getMetricsMetricScaleBounds(host.state.currentMetricType),
        chartColorContext: buildChartColorContext({
            device: 'metrics',
            deviceOptions: [{ value: 'metrics' }],
            metric: host.state.currentMetricType,
            metricOptions: METRIC_TYPE_OPTIONS
        })
    });
    if (!chart) {
        return;
    }
    chart.settings.setMetricName(getMetricsMetricDisplayName(host.state.currentMetricType));
    chart.settings.setValueFormatter((value: number) => formatMetricsMetricValue(host, host.state.currentMetricType, value));
};

const isMetricsCandlestickActive = (host: MetricsPageStateHost): boolean => isCandlestickModeActive({ chartType: host.state.currentChartType, chart: host.state.mainChart ?? undefined });

const getEffectiveMetricsCandlestickIntervalMs = (host: MetricsPageStateHost): number => {
    const resolved = resolveCandlestickIntervalMs({
        controlsManager: host.state.historyControlsManager,
        metadataIntervalMs: host.state.candlestickMetadata?.intervalMs,
        lastResolvedIntervalMs: host.state.lastResolvedCandlestickIntervalMs ?? undefined,
        requestedIntervalMinutes: host.state.candlestickIntervalMinutes,
        supportedHistoryIntervalsMs: host.state.supportedHistoryIntervalsMs ?? undefined,
        monitoringIntervalMs: host.state.monitoringIntervalMs
    });
    host.state.lastResolvedCandlestickIntervalMs = resolved;
    return resolved;
};

const resolveMetricsValueIntervalMs = (host: Pick<MetricsPageStateHost, 'state'>): number => host.state.historyIntervalMs ?? host.state.monitoringIntervalMs;

const getMetricsHistoryPointBudgetConfig = (host: MetricsPageBudgetHost): HistoryChartPointBudgetConfig => ({
    monitoringIntervalMs: host.operations.normalizeMetricsInt(host.state.monitoringIntervalMs, 1),
    chartHardLimit: host.state.chartHardLimit,
    historyApiPointCap: host.state.historyApiPointCap,
    maxHistoryPoints: host.state.maxHistoryPoints,
    maxRetentionMinutes: host.state.maxRetentionMinutes,
    candlestickActive: isMetricsCandlestickActive(host),
    candlestickIntervalMinutes: host.state.candlestickIntervalMinutes,
    plotWidthPx: resolveHistoryChartPlotWidthPx(host.state.mainChart)
});

const recalculateMetricsHistoryPointBudget = (host: MetricsPageBudgetHost): void => {
    const config = getMetricsHistoryPointBudgetConfig(host);
    host.state.currentHistoryPointBudget = computeHistoryChartPointBudget(config, Math.max(config.monitoringIntervalMs, Math.round(host.state.timeRange * 60_000)));
};

const getMetricsHistoryKey = (host: MetricsPageStateHost, metricType: string = host.state.currentMetricType): string | null => {
    switch (metricType) {
        case 'requests':
            return METRIC_HISTORY_KEYS.requests;
        case 'latency':
            return METRIC_HISTORY_KEYS.latency;
        case 'tokens':
            return METRIC_HISTORY_KEYS.tokens;
        case 'queue':
            return METRIC_HISTORY_KEYS.queue;
        case 'throughput':
            return METRIC_HISTORY_KEYS.throughput;
        default:
            return null;
    }
};

const getMetricsHistoryAggregation = (host: MetricsPageStateHost, metricType: string = host.state.currentMetricType): string => {
    switch (metricType) {
        case 'requests':
            return METRIC_HISTORY_AGGREGATIONS.requests;
        case 'latency':
            return METRIC_HISTORY_AGGREGATIONS.latency;
        case 'tokens':
            return METRIC_HISTORY_AGGREGATIONS.tokens;
        case 'queue':
            return METRIC_HISTORY_AGGREGATIONS.queue;
        case 'throughput':
            return METRIC_HISTORY_AGGREGATIONS.throughput;
        default:
            return 'avg';
    }
};

const getMetricsHistoryOhlcAggregation = (host: MetricsPageStateHost, metricType: string = host.state.currentMetricType): string => {
    switch (metricType) {
        case 'requests':
            return METRIC_HISTORY_OHLC_AGGREGATIONS.requests;
        case 'latency':
            return METRIC_HISTORY_OHLC_AGGREGATIONS.latency;
        case 'tokens':
            return METRIC_HISTORY_OHLC_AGGREGATIONS.tokens;
        case 'queue':
            return METRIC_HISTORY_OHLC_AGGREGATIONS.queue;
        case 'throughput':
            return METRIC_HISTORY_OHLC_AGGREGATIONS.throughput;
        default:
            return 'ohlc';
    }
};

const getMetricsMetricTransform = (_host: MetricsPageStateHost, metricType: string): ((value: number) => number) => {
    if (metricType === 'latency') {
        return (value: number): number => value;
    }
    return (value: number): number => value;
};

const getMetricsMetricDisplayName = (metricType: string): string => {
    return METRIC_TYPE_OPTIONS.find((option) => option.value === metricType)?.getLabel() ?? metricType;
};

const getMetricsMetricScaleBounds = (metricType: string): ScaleBounds | null => {
    let bounds: ScaleBound | null = null;
    switch (metricType) {
        case 'requests':
            bounds = METRIC_SCALE_BOUNDS.requests;
            break;
        case 'latency':
            bounds = METRIC_SCALE_BOUNDS.latency;
            break;
        case 'tokens':
            bounds = METRIC_SCALE_BOUNDS.tokens;
            break;
        case 'queue':
            bounds = METRIC_SCALE_BOUNDS.queue;
            break;
        case 'throughput':
            bounds = METRIC_SCALE_BOUNDS.throughput;
            break;
        default:
            bounds = null;
    }
    if (!bounds) {
        throw new TypeError(`Metric scale bounds must be configured for type: ${metricType}`);
    }
    const normalized: ScaleBounds = {};
    const min = bounds.min;
    const max = bounds.max;
    if (isFiniteNumber(min)) {
        normalized.min = Number(min);
    }
    if (isFiniteNumber(max)) {
        normalized.max = Number(max);
    }
    return Object.keys(normalized).length ? normalized : null;
};

const formatMetricsMetricValue = (host: MetricsPageStateHost, metricType: string, value: number): string => {
    if (!isFiniteNumber(value)) {
        return i18n.t('common.notAvailableShort');
    }
    const formatter = host.metricsServices.metricsFormatter;
    const roundedValue = Math.round(value);
    const compact = Math.abs(value) >= CHART_FULL_VALUE_LIMIT ? formatCompactNumber(value) : null;
    switch (metricType) {
        case 'requests':
            return compact ?? formatter.number(roundedValue);
        case 'latency':
            return compact === null ? formatter.ms(value) : i18n.t('common.time.units.millisecond.short', { count: compact });
        case 'tokens':
            return compact ?? formatter.number(value);
        case 'throughput':
            return i18n.t('metrics.units.tokensPerSecond', { value: compact ?? formatter.number(value) });
        case 'queue':
            return `${compact ?? formatter.number(roundedValue)} ${i18n.t('metrics.units.jobs')}`;
        default:
            return formatInvariantNumber(value, { maximumFractionDigits: 2 });
    }
};

const extractMetricsValue = (host: MetricsPageStateHost, metrics: MetricsData, metricType: string): number | null => {
    if (metricType === 'requests') {
        return calculateMetricsTotalRequests(host, metrics);
    }
    if (metricType === 'latency') {
        return calculateMetricsAverageLatency(host, metrics);
    }
    if (metricType === 'tokens') {
        return metrics.billing?.totalTokensGenerated ?? null;
    }
    if (metricType === 'queue') {
        return metrics.director?.gauges?.queueSize ?? null;
    }
    if (metricType === 'throughput') {
        return resolveMetricsCurrentTokenRateOrNull(metrics);
    }
    return null;
};

const calculateMetricsTotalRequests = (_host: MetricsPageStateHost, metrics: MetricsData): number | null => {
    const requests = metrics.director?.requests;
    if (!requests) {
        return null;
    }
    const total = requests.total;
    return total != null ? total : null;
};

const calculateMetricsAverageLatency = (_host: MetricsPageStateHost, metrics: MetricsData): number | null => {
    const latencyMs = metrics.director?.gauges?.requestLatencyMs;
    return latencyMs != null && latencyMs > 0 ? latencyMs : null;
};

const extractMetricsTimestamp = (_host: MetricsPageStateHost, _metrics: MetricsData): number => {
    return serverEpochMs();
};

export { calculateMetricsAverageLatency, calculateMetricsTotalRequests, extractMetricsTimestamp, extractMetricsValue, formatMetricsMetricValue, getEffectiveMetricsCandlestickIntervalMs, getMetricsHistoryAggregation, getMetricsHistoryKey, getMetricsHistoryOhlcAggregation, getMetricsHistoryPointBudgetConfig, getMetricsMetricDisplayName, getMetricsMetricScaleBounds, getMetricsMetricTransform, isMetricsCandlestickActive, recalculateMetricsHistoryPointBudget, resolveMetricsValueIntervalMs, updateMetricsChartConfiguration };
