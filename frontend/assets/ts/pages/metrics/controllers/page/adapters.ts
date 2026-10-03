/* SoAI - Metrics page adapters [frontend/assets/ts/pages/metrics/controllers/page/adapters.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { SystemMetricsHistoryRequest } from '@core/api/contracts/systemMetricsRequestContracts.ts';
import type { MetricsHistoryPayload } from '@core/realtime/metricsHistoryContracts.ts';
import type { HistoryPageWindow, HistoryResolutionWindow } from '@features/charts/public.ts';
import { getMetricsCatalogEntry } from '@pages/metrics/controllers/page/capabilities.ts';
import type { MetricsPageAdaptersHost } from '@pages/metrics/controllers/page/contracts.ts';
import { trimMetricsHistoryPoints } from '@pages/metrics/controllers/page/metricsUpdateProcessing.ts';
import { getEffectiveMetricsCandlestickIntervalMs, getMetricsHistoryAggregation, getMetricsHistoryKey, getMetricsHistoryOhlcAggregation, getMetricsMetricTransform } from '@pages/metrics/controllers/page/state.ts';
import { applyValueHistory, resolveValueHistoryRequest, type ValueHistoryContext } from '@pages/metrics/state/valueHistory.ts';
import type { CandlestickDataPoint, ValueHistoryResult } from '@pages/metrics/types.ts';
import { applyCandlestickHistory, prependCandlestickHistory, trimCandlestickData } from '@pages/metrics/widgets/candlestickhistory/effects.ts';
import { resolveCandlestickHistoryRequest } from '@pages/metrics/widgets/candlestickhistory/service.ts';
import type { CandlestickHistoryContext } from '@pages/metrics/widgets/candlestickhistory/types.ts';

const buildValueHistoryContext = (host: MetricsPageAdaptersHost): ValueHistoryContext => ({
    chartRuntime: host.state.chartRuntime,
    getMetricHistoryKey: () => getMetricsHistoryKey(host),
    getMetricHistoryAggregation: () => getMetricsHistoryAggregation(host),
    getCatalogEntry: (metricKey: string) => getMetricsCatalogEntry(host, metricKey),
    trimMetricsHistory: (force?: boolean) => trimMetricsHistoryPoints(host, force),
    timeRange: host.state.timeRange,
    pointBudget: host.operations.pointBudget(),
    monitoringIntervalMs: host.state.monitoringIntervalMs,
    historyIntervalMs: host.state.historyIntervalMs,
    supportedHistoryIntervalsMs: host.state.supportedHistoryIntervalsMs,
    maxHistoryPoints: host.state.maxHistoryPoints,
    metricsHistory: host.state.metricsHistory
});

const buildCandlestickContext = (host: MetricsPageAdaptersHost): CandlestickHistoryContext => ({
    query: {
        getMetricHistoryKey: () => getMetricsHistoryKey(host),
        getMetricHistoryOhlcAggregation: () => getMetricsHistoryOhlcAggregation(host),
        getCatalogEntry: (metricKey: string) => getMetricsCatalogEntry(host, metricKey),
        getMetricTransform: () => getMetricsMetricTransform(host, host.state.currentMetricType),
        getEffectiveCandlestickIntervalMs: () => getEffectiveMetricsCandlestickIntervalMs(host)
    },
    limits: {
        supportsOhlc: host.state.supportsOhlc,
        timeRange: host.state.timeRange,
        availableTimeRanges: host.state.availableTimeRanges,
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
    host.state.historyIntervalMs = context.historyIntervalMs;
};

const syncCandlestickContext = (host: MetricsPageAdaptersHost, context: CandlestickHistoryContext): void => {
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

const withValueHistoryContext = <T>(host: MetricsPageAdaptersHost, task: (context: ValueHistoryContext) => T): T => {
    const context = buildValueHistoryContext(host);
    const result = task(context);
    syncValueContext(host, context);
    return result;
};

const withCandlestickContext = <T>(host: MetricsPageAdaptersHost, task: (context: CandlestickHistoryContext) => T): T => {
    const context = buildCandlestickContext(host);
    const result = task(context);
    syncCandlestickContext(host, context);
    return result;
};

const resolveMetricsValueHistoryRequest = (host: MetricsPageAdaptersHost, page: HistoryPageWindow | HistoryResolutionWindow | null): SystemMetricsHistoryRequest | null => withValueHistoryContext(host, (context) => resolveValueHistoryRequest(context, page));

const applyMetricsValueHistory = (host: MetricsPageAdaptersHost, payload: MetricsHistoryPayload, mode: 'refresh' | 'prepend'): ValueHistoryResult => withValueHistoryContext(host, (context) => applyValueHistory(context, payload, { mode }));

const resolveMetricsCandlestickHistoryRequest = (host: MetricsPageAdaptersHost, page: HistoryPageWindow | null): SystemMetricsHistoryRequest | null => withCandlestickContext(host, (context) => resolveCandlestickHistoryRequest(context, page));

const applyMetricsCandlestickHistory = (host: MetricsPageAdaptersHost, payload: MetricsHistoryPayload): boolean => withCandlestickContext(host, (context) => applyCandlestickHistory(context, host.state.chartRuntime.getOhlc(), payload));

const prependMetricsCandlestickHistory = (host: MetricsPageAdaptersHost, payload: MetricsHistoryPayload): { prepended: CandlestickDataPoint[]; capped: boolean } => withCandlestickContext(host, (context) => prependCandlestickHistory(context, host.state.chartRuntime.getOhlc(), payload));

const trimMetricsCandlestickData = (host: MetricsPageAdaptersHost, force = false): boolean => withCandlestickContext(host, (context) => trimCandlestickData(context, force));

const openMetricsExportPreview = async (host: MetricsPageAdaptersHost): Promise<void> =>
    host.metricsServices.exportPreviewModal.open({
        snapshotResource: 'system.metrics.export',
        payload: {},
        scope: 'metrics',
        boundaryName: 'metrics:openExportPreviewModal',
        downloadBoundaryName: 'metrics:downloadExportPreview'
    });

export { applyMetricsCandlestickHistory, applyMetricsValueHistory, openMetricsExportPreview, prependMetricsCandlestickHistory, resolveMetricsCandlestickHistoryRequest, resolveMetricsValueHistoryRequest, trimMetricsCandlestickData };
