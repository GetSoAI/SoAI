/* SoAI - Metrics page adapters [frontend/assets/ts/pages/metrics/controllers/page/adapters.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import { isFiniteNumber } from '@core/typeGuards.ts';
import { getMetricsCatalogEntry } from '@pages/metrics/controllers/page/capabilities.ts';
import type { MetricsPageAdaptersHost } from '@pages/metrics/controllers/page/contracts.ts';
import { trimMetricsHistoryPoints, updateMetricsMainChart } from '@pages/metrics/controllers/page/metricsUpdateProcessing.ts';
import { getEffectiveMetricsCandlestickIntervalMs, getMetricsHistoryAggregation, getMetricsHistoryKey, getMetricsHistoryOhlcAggregation, getMetricsMetricTransform, isMetricsCandlestickActive } from '@pages/metrics/controllers/page/state.ts';
import { applyValueHistory, fetchValueHistory, integrateValueHistoryPoints, parseValueHistoryResponse, type ValueHistoryContext } from '@pages/metrics/state/valueHistory.ts';
import type { CandlestickMetadata, HistoryResponse, MetricsHistoryPoint, ParsedHistoryResponse, ValueHistoryResult } from '@pages/metrics/types.ts';
import { applyCandlestickHistory, applyCandlestickMetadata, fetchCandlestickHistory, trimCandlestickData, type CandlestickHistoryContext } from '@pages/metrics/widgets/candlestickhistory/service.ts';

const buildValueHistoryContext = (host: MetricsPageAdaptersHost): ValueHistoryContext => ({
    chartRuntime: host.state.chartRuntime,
    getMetricHistoryKey: () => getMetricsHistoryKey(host),
    getMetricHistoryAggregation: () => getMetricsHistoryAggregation(host),
    getCatalogEntry: (metricKey: string) => getMetricsCatalogEntry(host, metricKey),
    isCandlestickActive: () => isMetricsCandlestickActive(host),
    updateMainChart: (options) => updateMetricsMainChart(host, options),
    trimMetricsHistory: (force?: boolean) => trimMetricsHistoryPoints(host, force),
    getRequestToken: () => host.state.valueHistoryRequestToken,
    setRequestToken: (token: number | null) => {
        host.state.valueHistoryRequestToken = token;
    },
    timeRange: host.state.timeRange,
    pointBudget: host.operations.pointBudget(),
    monitoringIntervalMs: host.state.monitoringIntervalMs,
    supportedHistoryIntervalsMs: host.state.supportedHistoryIntervalsMs,
    maxHistoryPoints: host.state.maxHistoryPoints,
    metricsHistory: host.state.metricsHistory,
    metricsHistoryExhausted: host.state.metricsHistoryExhausted,
    valueHistoryRequestState: host.state.valueHistoryRequestState
});

const buildCandlestickContext = (host: MetricsPageAdaptersHost): CandlestickHistoryContext => ({
    query: {
        runWithBoundary: <T>(name: string, functionValue: () => Promise<T>) => host.owners.pageLifecycle.run(name, functionValue),
        getMetricHistoryKey: () => getMetricsHistoryKey(host),
        getMetricHistoryOhlcAggregation: () => getMetricsHistoryOhlcAggregation(host),
        getCatalogEntry: (metricKey: string) => getMetricsCatalogEntry(host, metricKey),
        getMetricTransform: () => getMetricsMetricTransform(host, host.state.currentMetricType),
        getEffectiveCandlestickIntervalMs: () => getEffectiveMetricsCandlestickIntervalMs(host),
        syncChartControls: (options: { range?: boolean; candles?: boolean }) => host.operations.syncChartControls(options),
        isCandlestickActive: () => isMetricsCandlestickActive(host),
        updateMainChart: (options: { resetView?: boolean }) => updateMetricsMainChart(host, options),
        getRequestSignature: () => host.state.lastCandlestickRequest,
        setRequestSignature: (signature: string | null) => {
            host.state.lastCandlestickRequest = signature;
        },
        isRequestActive: () => host.state.isFetchingCandles,
        setRequestActive: (active: boolean) => {
            host.state.isFetchingCandles = active;
        }
    },
    limits: {
        supportsOhlc: host.state.supportsOhlc,
        timeRange: host.state.timeRange,
        maxRetentionMinutes: host.state.maxRetentionMinutes,
        supportedHistoryIntervalsMs: host.state.supportedHistoryIntervalsMs,
        pointBudget: host.operations.pointBudget(),
        historyTrimRatio: host.state.historyTrimRatio,
        chartHardLimit: host.state.chartHardLimit,
        monitoringIntervalMs: host.state.monitoringIntervalMs,
        historyApiPointCap: host.state.historyApiPointCap,
        maxHistoryPoints: host.state.maxHistoryPoints,
        currentHistoryPointBudget: host.state.currentHistoryPointBudget
    },
    state: {
        candlestickHistoryExhausted: host.state.candlestickHistoryExhausted,
        candlestickIntervalMinutes: host.state.candlestickIntervalMinutes,
        lastResolvedCandlestickIntervalMs: host.state.lastResolvedCandlestickIntervalMs,
        baseCandleIntervals: host.state.baseCandleIntervals,
        candlestickData: host.state.candlestickData,
        candlestickBuckets: host.state.candlestickBuckets,
        candlestickMetadata: host.state.candlestickMetadata
    },
    chart: { mainChart: host.state.mainChart }
});

const syncValueContext = (host: MetricsPageAdaptersHost, context: ValueHistoryContext): void => {
    host.state.metricsHistory = context.metricsHistory;
    host.state.metricsHistoryExhausted = context.metricsHistoryExhausted;
};

const syncCandlestickContext = (host: MetricsPageAdaptersHost, context: CandlestickHistoryContext): void => {
    host.state.candlestickHistoryExhausted = context.state.candlestickHistoryExhausted;
    host.state.candlestickIntervalMinutes = context.state.candlestickIntervalMinutes;
    host.state.lastResolvedCandlestickIntervalMs = context.state.lastResolvedCandlestickIntervalMs;
    host.state.baseCandleIntervals = context.state.baseCandleIntervals;
    host.state.candlestickData = context.state.candlestickData;
    host.state.candlestickBuckets = context.state.candlestickBuckets;
    host.state.candlestickMetadata = context.state.candlestickMetadata;
    host.state.monitoringIntervalMs = context.limits.monitoringIntervalMs;
    host.state.historyApiPointCap = context.limits.historyApiPointCap;
    host.state.maxHistoryPoints = context.limits.maxHistoryPoints;
    host.state.currentHistoryPointBudget = context.limits.currentHistoryPointBudget;
};

const fetchMetricsValueHistory = async (host: MetricsPageAdaptersHost, options: { resetView?: boolean; beforeTimestamp?: number | null } = {}): Promise<void> => {
    const hasCachedChartData = Boolean(host.state.chartRuntime.getCachedModules()?.data);
    const context = buildValueHistoryContext(host);
    const changed = await fetchValueHistory(context, options, hasCachedChartData);
    if (changed) {
        syncValueContext(host, context);
    }
};

const parseMetricsValueHistoryResponse = (host: MetricsPageAdaptersHost, response: HistoryResponse): ParsedHistoryResponse => parseValueHistoryResponse(buildValueHistoryContext(host), response);

const integrateMetricsValueHistoryPoints = (host: MetricsPageAdaptersHost, points: MetricsHistoryPoint[], options: { mode?: string } = {}): ValueHistoryResult => {
    const context = buildValueHistoryContext(host);
    const result = integrateValueHistoryPoints(context, points, options);
    syncValueContext(host, context);
    return result;
};

const applyMetricsValueHistory = (host: MetricsPageAdaptersHost, response: HistoryResponse, options: { mode?: string } = {}): ValueHistoryResult & { intervalMs: number | null } => {
    const context = buildValueHistoryContext(host);
    const result = applyValueHistory(context, response, options);
    syncValueContext(host, context);
    return result;
};

const fetchMetricsCandlestickHistory = async (host: MetricsPageAdaptersHost, options: { resetView?: boolean; beforeTimestampMs?: number | null } = {}): Promise<void> => {
    const context = buildCandlestickContext(host);
    const changed = await fetchCandlestickHistory(context, host.state.chartRuntime.getOhlc(), options);
    if (changed) {
        syncCandlestickContext(host, context);
    }
};

const applyMetricsCandlestickHistory = (host: MetricsPageAdaptersHost, response: HistoryResponse, options: { resetView?: boolean } = {}): void => {
    const context = buildCandlestickContext(host);
    applyCandlestickHistory(context, host.state.chartRuntime.getOhlc(), response, options);
    syncCandlestickContext(host, context);
};

const applyMetricsCandlestickMetadata = (host: MetricsPageAdaptersHost, metadata: CandlestickMetadata): void => {
    const context = buildCandlestickContext(host);
    applyCandlestickMetadata(context, host.state.chartRuntime.getOhlc(), metadata);
    syncCandlestickContext(host, context);
};

const trimMetricsCandlestickData = (host: MetricsPageAdaptersHost, force = false): boolean => {
    const context = buildCandlestickContext(host);
    const modified = trimCandlestickData(context, force);
    syncCandlestickContext(host, context);
    return modified;
};

const handleMetricsChartHistoricalRequest = async (host: MetricsPageAdaptersHost, timestamp: JsonValue): Promise<void> => {
    if (!isFiniteNumber(timestamp)) {
        return;
    }
    if (!host.state.metricsHistoryEnabled) {
        return;
    }
    if (isMetricsCandlestickActive(host)) {
        await fetchMetricsCandlestickHistory(host, { beforeTimestampMs: timestamp });
        return;
    }
    await fetchMetricsValueHistory(host, { beforeTimestamp: timestamp });
};

const openMetricsExportPreview = async (host: MetricsPageAdaptersHost): Promise<void> =>
    host.metricsServices.exportPreviewModal.open({
        snapshotResource: 'system.metrics.export',
        payload: {},
        scope: 'metrics',
        boundaryName: 'metrics:openExportPreviewModal',
        downloadBoundaryName: 'metrics:downloadExportPreview'
    });

export { applyMetricsCandlestickHistory, applyMetricsCandlestickMetadata, applyMetricsValueHistory, fetchMetricsCandlestickHistory, fetchMetricsValueHistory, handleMetricsChartHistoricalRequest, integrateMetricsValueHistoryPoints, openMetricsExportPreview, parseMetricsValueHistoryResponse, trimMetricsCandlestickData };
