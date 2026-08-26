/* SoAI - Metrics feature configuration [frontend/assets/ts/features/metrics/Config.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { formatPercent } from '@core/primitives/percent.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { isFiniteNumber, isObject } from '@core/typeGuards.ts';
import { DEFAULT_CHART_TYPE_SEQUENCE, DEFAULT_PRIMARY_BOTTOM_AXIS_PADDING, resolveChartPadding, type ChartPadding } from '@core/charts/constants.ts';
import { resolveMetricsCurrentTokenRateOrNull } from '@features/metrics/liveTokenRates.ts';
import type { Metrics } from '@features/metrics/metricsSnapshot.ts';

interface MetricHistoryKeys {
    requests: string;
    latency: string;
    tokens: string;
    queue: string;
}

interface MetricHistoryAggregations {
    requests: string;
    latency: string;
    tokens: string;
    queue: string;
}

interface MetricHistoryOhlcAggregations {
    requests: string;
    latency: string;
    tokens: string;
    queue: string;
}

interface MetricValueTransforms {
    latency: (value: number) => number;
}

interface ScaleBound {
    min: number;
    max?: number;
}

interface MetricScaleBounds {
    requests: ScaleBound;
    latency: ScaleBound;
    tokens: ScaleBound;
    queue: ScaleBound;
}

interface MetricsFormatter {
    number(value: JsonValue | null | undefined, fallback?: string): string;
    ms(value: JsonValue | null | undefined, fallback?: string): string;
    secondsFromMs(value: JsonValue | null | undefined, fallback?: string): string;
}

interface MetricsKpiHost {
    metricsFormatter: MetricsFormatter;
    calculateTotalRequests(metrics: Metrics): number;
    calculateAverageLatency(metrics: Metrics): number;
}

interface KPIConfigItem {
    id: string;
    getLabel: () => string;
    value: (host: MetricsKpiHost, metrics: Metrics) => string;
}

interface SystemStatsConfigItem {
    id: string;
    getLabel: () => string;
    value: (metrics: Metrics) => number;
    unit?: 'number' | 'percent';
}

interface RequestOutcomeCounts {
    completed: number;
    failed: number;
    totalFinished: number;
}

const METRIC_HISTORY_KEYS: Readonly<MetricHistoryKeys> = Object.freeze({
    requests: 'director.requests.total',
    latency: 'director.gauges.request_latency_ms',
    tokens: 'billing.total_tokens_generated',
    queue: 'director.gauges.queue_size'
});

const METRIC_HISTORY_AGGREGATIONS: Readonly<MetricHistoryAggregations> = Object.freeze({
    requests: 'max',
    latency: 'avg',
    tokens: 'max',
    queue: 'avg'
});

const METRIC_HISTORY_OHLC_AGGREGATIONS: Readonly<MetricHistoryOhlcAggregations> = Object.freeze({
    requests: 'ohlc',
    latency: 'ohlc',
    tokens: 'ohlc',
    queue: 'ohlc'
});

const METRIC_VALUE_TRANSFORMS: Readonly<MetricValueTransforms> = Object.freeze({
    latency: (value: number): number => value
});

const METRIC_SCALE_BOUNDS: Readonly<MetricScaleBounds> = Object.freeze({
    requests: { min: 0 },
    latency: { min: 0 },
    tokens: { min: 0 },
    queue: { min: 0 }
});

const CHART_TYPE_SEQUENCE = DEFAULT_CHART_TYPE_SEQUENCE;

const PRIMARY_CHART_PADDING: Readonly<ChartPadding> = Object.freeze(resolveChartPadding(undefined));
const PRIMARY_BOTTOM_AXIS_PADDING = DEFAULT_PRIMARY_BOTTOM_AXIS_PADDING;

const METRICS_HISTORY_API_POINT_LIMIT = 50000;

const resolveMetricsTotalTokens = (metrics: Metrics): number => {
    const liveTokens = metrics.billing?.totalTokensGenerated;
    if (isFiniteNumber(liveTokens)) return liveTokens;
    const tokens = metrics.genesis?.tokensTotal;
    return isFiniteNumber(tokens) ? tokens : 0;
};

const resolveMetricsActiveInferences = (metrics: Metrics): number => {
    const active = metrics.director?.gauges?.pluginConcurrencyActive;
    if (!isObject(active)) {
        return 0;
    }
    let total = 0;
    for (const value of Object.values(active)) {
        if (isFiniteNumber(value)) {
            total += value;
        }
    }
    return total;
};

const resolveRequestOutcomeCounts = (metrics: Metrics): RequestOutcomeCounts => {
    const completedValue = metrics.director?.requests?.completed;
    const failedValue = metrics.director?.requests?.failed;
    const completed = isFiniteNumber(completedValue) && completedValue >= 0 ? completedValue : 0;
    const failed = isFiniteNumber(failedValue) && failedValue >= 0 ? failedValue : 0;
    const totalFinished = completed + failed;
    return { completed, failed, totalFinished };
};

const resolveRequestFailureRate = (metrics: Metrics): number => {
    const { failed, totalFinished } = resolveRequestOutcomeCounts(metrics);
    return totalFinished > 0 ? (failed / totalFinished) * 100 : 0;
};

const resolveRequestSuccessRate = (metrics: Metrics): number | null => {
    const { completed, totalFinished } = resolveRequestOutcomeCounts(metrics);
    return totalFinished > 0 ? (completed / totalFinished) * 100 : null;
};

const KPI_CONFIG: Readonly<KPIConfigItem[]> = Object.freeze([
    {
        id: 'totalRequests',
        getLabel: (): string => i18n.t('metrics.stats.totalRequests'),
        value: (host: MetricsKpiHost, metrics: Metrics): string => {
            const total = host.calculateTotalRequests(metrics) ?? 0;
            return host.metricsFormatter.number(total);
        }
    },
    {
        id: 'totalTokens',
        getLabel: (): string => i18n.t('metrics.stats.tokensGenerated'),
        value: (host: MetricsKpiHost, metrics: Metrics): string => {
            return host.metricsFormatter.number(resolveMetricsTotalTokens(metrics));
        }
    },
    {
        id: 'avgLatency',
        getLabel: (): string => i18n.t('metrics.stats.avgLatency'),
        value: (host: MetricsKpiHost, metrics: Metrics): string => {
            const latency = host.calculateAverageLatency(metrics);
            if (!isFiniteNumber(latency)) return i18n.t('common.notAvailableShort');
            return host.metricsFormatter.secondsFromMs(latency);
        }
    },
    {
        id: 'requestSuccessRate',
        getLabel: (): string => i18n.t('metrics.stats.requestSuccessRate'),
        value: (_host: MetricsKpiHost, metrics: Metrics): string => {
            const successRate = resolveRequestSuccessRate(metrics);
            return successRate === null ? i18n.t('common.notAvailableShort') : formatPercent(successRate);
        }
    },
    {
        id: 'liveThroughput',
        getLabel: (): string => i18n.t('metrics.stats.liveThroughput'),
        value: (host: MetricsKpiHost, metrics: Metrics): string => {
            const currentRate = resolveMetricsCurrentTokenRateOrNull(metrics);
            if (currentRate === null) return i18n.t('common.notAvailableShort');
            return i18n.t('metrics.units.tokensPerSecond', { value: host.metricsFormatter.number(currentRate) });
        }
    },
    {
        id: 'modelLoads',
        getLabel: (): string => i18n.t('metrics.stats.modelLoads'),
        value: (host: MetricsKpiHost, metrics: Metrics): string => {
            const loads = metrics.director?.modelLoads?.successful ?? 0;
            return host.metricsFormatter.number(loads);
        }
    },
    {
        id: 'deduplicated',
        getLabel: (): string => i18n.t('metrics.stats.deduplicated'),
        value: (host: MetricsKpiHost, metrics: Metrics): string => {
            const dedup = metrics.director?.requests?.deduplicated ?? 0;
            return host.metricsFormatter.number(dedup);
        }
    }
]);

const SYSTEM_STATS_CONFIG: Readonly<SystemStatsConfigItem[]> = Object.freeze([
    { id: 'queueDepth', getLabel: (): string => i18n.t('metrics.cards.systemPerformance.stats.queueDepth'), value: (metrics: Metrics): number => metrics.director?.gauges?.queueSize ?? 0 },
    {
        id: 'activePlugins',
        getLabel: (): string => i18n.t('metrics.cards.systemPerformance.stats.activePlugins'),
        value: (metrics: Metrics): number => {
            const pluginHealth = metrics.director?.gauges?.pluginHealth;
            return pluginHealth && isObject(pluginHealth) ? Object.keys(pluginHealth).length : 0;
        }
    },
    { id: 'dbQueueDepth', getLabel: (): string => i18n.t('metrics.cards.systemPerformance.stats.dbQueueDepth'), value: (metrics: Metrics): number => metrics.database?.gauges?.writeQueueDepth ?? 0 },
    { id: 'pendingLoads', getLabel: (): string => i18n.t('metrics.cards.systemPerformance.stats.pendingLoads'), value: (metrics: Metrics): number => metrics.director?.gauges?.pendingLoads ?? 0 },
    { id: 'failedRequests', getLabel: (): string => i18n.t('metrics.cards.systemPerformance.stats.failedRequests'), value: (metrics: Metrics): number => metrics.director?.requests?.failed ?? 0 },
    { id: 'requestFailureRate', getLabel: (): string => i18n.t('metrics.cards.systemPerformance.stats.requestFailureRate'), value: resolveRequestFailureRate, unit: 'percent' },
    { id: 'discoveryRuns', getLabel: (): string => i18n.t('metrics.cards.systemPerformance.stats.discoveryRuns'), value: (metrics: Metrics): number => metrics.modelManager?.discoveriesRun ?? 0 },
    { id: 'eventsDropped', getLabel: (): string => i18n.t('metrics.cards.systemPerformance.stats.eventsDropped'), value: (metrics: Metrics): number => metrics.eventBus?.eventsDropped ?? 0 },
    { id: 'modelsUpdated', getLabel: (): string => i18n.t('metrics.cards.systemPerformance.stats.modelsUpdated'), value: (metrics: Metrics): number => metrics.modelManager?.modelsUpdated ?? 0 },
    { id: 'eventBusQueueDepth', getLabel: (): string => i18n.t('metrics.cards.systemPerformance.stats.eventBusQueueDepth'), value: (metrics: Metrics): number => metrics.eventBus?.gauges?.queueDepth ?? 0 },
    { id: 'streamingDroppedEvents', getLabel: (): string => i18n.t('metrics.cards.systemPerformance.stats.streamingDroppedEvents'), value: (metrics: Metrics): number => metrics.streaming?.backpressure?.droppedEvents ?? 0 },
    { id: 'streamingDeliveryTimeouts', getLabel: (): string => i18n.t('metrics.cards.systemPerformance.stats.streamingDeliveryTimeouts'), value: (metrics: Metrics): number => metrics.streaming?.delivery?.timeoutCount ?? 0 },
    { id: 'failedModelLoads', getLabel: (): string => i18n.t('metrics.cards.systemPerformance.stats.failedModelLoads'), value: (metrics: Metrics): number => metrics.director?.modelLoads?.failed ?? 0 }
]);

interface MetricsConfigModule {
    METRIC_HISTORY_KEYS: Readonly<MetricHistoryKeys>;
    METRIC_HISTORY_AGGREGATIONS: Readonly<MetricHistoryAggregations>;
    METRIC_HISTORY_OHLC_AGGREGATIONS: Readonly<MetricHistoryOhlcAggregations>;
    METRIC_VALUE_TRANSFORMS: Readonly<MetricValueTransforms>;
    METRIC_SCALE_BOUNDS: Readonly<MetricScaleBounds>;
    CHART_TYPE_SEQUENCE: readonly string[];
    PRIMARY_CHART_PADDING: Readonly<ChartPadding>;
    PRIMARY_BOTTOM_AXIS_PADDING: number;
    METRICS_HISTORY_API_POINT_LIMIT: number;
    KPI_CONFIG: Readonly<KPIConfigItem[]>;
    SYSTEM_STATS_CONFIG: Readonly<SystemStatsConfigItem[]>;
}

const metricsConfig: Readonly<MetricsConfigModule> = Object.freeze({
    METRIC_HISTORY_KEYS,
    METRIC_HISTORY_AGGREGATIONS,
    METRIC_HISTORY_OHLC_AGGREGATIONS,
    METRIC_VALUE_TRANSFORMS,
    METRIC_SCALE_BOUNDS,
    CHART_TYPE_SEQUENCE,
    PRIMARY_CHART_PADDING,
    PRIMARY_BOTTOM_AXIS_PADDING,
    METRICS_HISTORY_API_POINT_LIMIT,
    KPI_CONFIG,
    SYSTEM_STATS_CONFIG
});

export { metricsConfig, METRIC_HISTORY_KEYS, METRIC_HISTORY_AGGREGATIONS, METRIC_HISTORY_OHLC_AGGREGATIONS, METRIC_VALUE_TRANSFORMS, METRIC_SCALE_BOUNDS, CHART_TYPE_SEQUENCE, PRIMARY_CHART_PADDING, PRIMARY_BOTTOM_AXIS_PADDING, METRICS_HISTORY_API_POINT_LIMIT, KPI_CONFIG, SYSTEM_STATS_CONFIG, resolveMetricsTotalTokens, resolveMetricsActiveInferences };
export type { MetricHistoryKeys, MetricHistoryAggregations, MetricHistoryOhlcAggregations, MetricValueTransforms, ScaleBound, MetricScaleBounds, MetricsFormatter, MetricsKpiHost, KPIConfigItem, SystemStatsConfigItem, MetricsConfigModule };
