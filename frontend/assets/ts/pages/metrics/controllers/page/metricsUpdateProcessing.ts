/* SoAI - Metrics page update processing [frontend/assets/ts/pages/metrics/controllers/page/metricsUpdateProcessing.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { readRuntimeFiniteNumberOrFallbackValue } from '@core/types/numberCoercionReaders.ts';
import { isArray, isFiniteNumber, isObject } from '@core/typeGuards.ts';
import { formatCompactNumber } from '@core/primitives/compactNumber.ts';
import { updateAdaptiveNumber } from '@core/ui/adaptiveNumber.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';
import { markChartViewportFitted, resolveChartViewportReset, type ChartPointInput } from '@features/charts/public.ts';
import { KPI_CONFIG, refreshMetricsAdvancedModalIfOpen, resolveMetricsTotalTokens } from '@features/metrics/public.ts';
import type { MetricsPageActionsHost } from '@pages/metrics/controllers/page/contracts.ts';
import { extractMetricsTimestamp, extractMetricsValue, getEffectiveMetricsCandlestickIntervalMs, getMetricsHistoryAggregation, getMetricsHistoryKey, getMetricsMetricScaleBounds, isMetricsCandlestickActive } from '@pages/metrics/controllers/page/state.ts';
import { trimMetricsHistory } from '@pages/metrics/mappers/metricsHistoryMapping.ts';
import type { CandlestickDataPoint, MetricsData, MetricsHistoryPoint, RealtimeCandlestickUpdate } from '@pages/metrics/types.ts';
import { updateDistributionChart, updateSystemStats } from '@pages/metrics/widgets/effects.ts';
import { updateModelTable, updatePluginHealth } from '@pages/metrics/widgets/service.ts';

interface MetricsChartRenderOptions {
    resetView?: boolean;
    prepended?: MetricsHistoryPoint[] | null;
}

const toJsonValuePoint = (point: MetricsHistoryPoint): JsonObject => ({
    timestamp: point.timestamp,
    value: point.value
});

const toCandlestickJsonPoint = (point: CandlestickDataPoint): JsonObject => ({
    timestamp: point.timestamp,
    open: point.open,
    high: point.high,
    low: point.low,
    close: point.close,
    value: point.value
});

const resetMetricsValueHistory = (host: MetricsPageActionsHost, { clear = false }: { clear?: boolean } = {}): void => {
    host.state.valueHistoryRequestToken = null;
    host.state.valueHistoryRequestState.clear();
    host.state.lastRealtimeMetricValues.clear();
    host.state.metricsHistoryExhausted = false;
    if (clear) {
        host.state.metricsHistory = [];
    }
};

const resetMetricsData = (host: MetricsPageActionsHost, fullReset = false): void => {
    host.state.candlestickData = [];
    host.state.candlestickBuckets.clear();
    host.state.candlestickMetadata = null;
    host.state.lastCandlestickRequest = null;
    host.state.candlestickHistoryExhausted = false;
    resetMetricsValueHistory(host, { clear: fullReset });
    if (fullReset) {
        host.state.metricsHistory = [];
    }
};

const trimMetricsHistoryPoints = (host: MetricsPageActionsHost, force = false): boolean => {
    const beforeLength = host.state.metricsHistory.length;
    host.state.metricsHistory = trimMetricsHistory({
        points: host.state.metricsHistory,
        maxHistoryPoints: host.state.maxHistoryPoints,
        historyTrimRatio: host.state.historyTrimRatio,
        force
    });
    return host.state.metricsHistory.length !== beforeLength;
};

const appendMetricsHistoryPoint = (host: MetricsPageActionsHost, timestamp: number, value: number): void => {
    if (!isFiniteNumber(timestamp) || !isFiniteNumber(value)) {
        return;
    }
    const intervalMs = host.operations.normalizeMetricsInt(host.state.monitoringIntervalMs, 1);
    const bucketTimestamp = Math.floor(timestamp / intervalMs) * intervalMs;
    const lastPoint = host.state.metricsHistory[host.state.metricsHistory.length - 1];
    if (lastPoint && lastPoint.timestamp === bucketTimestamp) {
        lastPoint.value = getMetricsHistoryAggregation(host, host.state.currentMetricType) === 'delta' ? lastPoint.value + value : value;
        return;
    }
    const dataModule = host.state.chartRuntime.getCachedModules()?.data ?? null;
    if (lastPoint && dataModule) {
        const fillers = dataModule.buildLineGapFillers(toJsonValuePoint(lastPoint), bucketTimestamp, intervalMs, {
            maxFill: Math.min(host.operations.pointBudget(), 20000)
        });
        if (fillers.length) {
            host.state.metricsHistory.push(
                ...fillers.map((point) => ({
                    timestamp: point.timestamp,
                    value: point.value
                }))
            );
        }
    }
    host.state.metricsHistory.push({ timestamp: bucketTimestamp, value });
    trimMetricsHistoryPoints(host);
};

const canApplyRealtimeMetricsHistory = (host: MetricsPageActionsHost): boolean => {
    if (!host.state.metricsHistoryEnabled) {
        return true;
    }
    if (isMetricsCandlestickActive(host)) {
        return host.state.candlestickData.length > 0 || host.state.candlestickBuckets.size > 0;
    }
    return host.state.metricsHistory.length > 0;
};

const updateMetricsKpiCards = (host: MetricsPageActionsHost): void => {
    const metrics = host.state.currentMetrics;
    for (const entry of KPI_CONFIG) {
        const value = metrics ? entry.value(host.metricsServices.kpiHost, metrics) : null;
        host.owners.pageElements.setValue(entry.id, value, { allowNull: true });
    }
    const totalTokensElement = host.operations.getCachedUI('totalTokens');
    if (metrics && totalTokensElement) {
        const totalTokens = resolveMetricsTotalTokens(metrics);
        updateAdaptiveNumber({ pageDom: host.owners.pageDom }, totalTokensElement, host.metricsServices.metricsFormatter.number(totalTokens), formatCompactNumber(totalTokens), 'ui-adaptive-number metrics-adaptive-number');
    }
};

const updateMetricsMainChart = (host: MetricsPageActionsHost, options: MetricsChartRenderOptions = {}): void => {
    const { resetView = false, prepended = null } = options;
    const chart = host.state.mainChart;
    if (!chart) {
        return;
    }
    const shouldResetView = resolveChartViewportReset(host.state, resetView);
    chart.settings.update({ scaleBounds: getMetricsMetricScaleBounds(host.state.currentMetricType) });
    const candlestickMode = isMetricsCandlestickActive(host);
    chart.settings.setChartType(candlestickMode ? 'candlestick' : host.state.currentChartType);
    if (isArray(prepended) && prepended.length && !shouldResetView && !candlestickMode) {
        const normalized: ChartPointInput[] = [];
        for (const point of prepended) {
            const timestamp = readRuntimeFiniteNumberOrFallbackValue(point.timestamp, Number.NaN);
            const value = readRuntimeFiniteNumberOrFallbackValue(point.value, Number.NaN);
            if (!Number.isFinite(timestamp) || !Number.isFinite(value)) {
                continue;
            }
            normalized.push({ timestamp, value });
        }
        if (normalized.length) {
            chart.data.prepend(normalized);
        }
        host.state.pendingChartSync = false;
        return;
    }
    if (candlestickMode) {
        const intervalMs = getEffectiveMetricsCandlestickIntervalMs(host);
        const series = host.state.chartRuntime.getOhlc().buildCandlestickSeries(host.state.candlestickData.map(toCandlestickJsonPoint), {
            maxPoints: host.operations.pointBudget(),
            timeRangeMs: host.state.timeRange * 60000,
            intervalMs
        });
        chart.data.replace(series, { preserveView: !shouldResetView, assumeSorted: true });
    } else {
        if (host.state.metricsHistory.length === 0) {
            chart.data.replace([], { preserveView: !shouldResetView, assumeSorted: true });
            host.state.pendingChartSync = false;
            return;
        }
        const latestTimestamp = host.state.metricsHistory[host.state.metricsHistory.length - 1]?.timestamp;
        if (!isFiniteNumber(latestTimestamp)) {
            throw new TypeError('metricsHistory must include finite timestamps');
        }
        const cutoff = latestTimestamp - host.state.timeRange * 60000;
        let source = host.state.metricsHistory.filter((point) => point.timestamp >= cutoff);
        if (!source.length && host.state.metricsHistory.length) {
            source = host.state.metricsHistory.slice(-Math.min(host.operations.pointBudget(), host.state.metricsHistory.length));
        }
        const series = host.state.chartRuntime.getDataTransforms().toLineSeries(source.map(toJsonValuePoint), host.operations.pointBudget(), {
            assumeSorted: true,
            fillGaps: true,
            intervalMs: host.operations.normalizeMetricsInt(host.state.monitoringIntervalMs, 1),
            rangeMs: Math.max(60000, Math.round(host.state.timeRange * 60000)),
            densityMode: host.state.currentChartType === 'bar' ? 'average' : 'shape',
            targetPoints: host.operations.pointBudget()
        });
        chart.data.replace(series, { preserveView: !shouldResetView, assumeSorted: true });
    }
    if (shouldResetView) {
        chart.view.fitTimeRange(host.state.timeRange, { align: 'tail' });
        markChartViewportFitted(host.state);
    } else {
        chart.view.alignToLatest();
    }
    host.state.pendingChartSync = false;
};

const updateMetricsDisplays = (host: MetricsPageActionsHost, { skipChart = false }: { skipChart?: boolean } = {}): void => {
    if (!host.state.currentMetrics) {
        host.metricsServices.telemetryPresenter?.updateCard();
        return;
    }
    updateMetricsKpiCards(host);
    if (!skipChart) {
        updateMetricsMainChart(host);
    }
    updatePluginHealth(host);
    updateDistributionChart(host);
    updateModelTable(host);
    updateSystemStats(host);
    host.metricsServices.telemetryPresenter?.updateCard();
    refreshMetricsAdvancedModalIfOpen();
};

const updateRealtimeCandlestick = (host: MetricsPageActionsHost, timestamp: number, value: number): RealtimeCandlestickUpdate => {
    const effectiveIntervalMs = getEffectiveMetricsCandlestickIntervalMs(host);
    const result = host.state.chartRuntime.getOhlc().updateRealtimeCandlestick(host.state.candlestickBuckets, host.state.candlestickData, timestamp, value, effectiveIntervalMs);
    const intervalMs = Math.max(1, Math.round(Number(effectiveIntervalMs)));
    const bucketTimestamp = Math.floor(timestamp / intervalMs) * intervalMs;
    const point = host.state.candlestickBuckets.get(bucketTimestamp) ?? null;
    return { updated: result.updated, appended: result.appended, point };
};

const resolveRealtimeChartValue = (host: MetricsPageActionsHost, metrics: MetricsData, metricType: string): number | null => {
    const rawValue = extractMetricsValue(host, metrics, metricType);
    if (!isFiniteNumber(rawValue)) {
        return null;
    }
    if (getMetricsHistoryAggregation(host, metricType) !== 'delta') {
        return rawValue;
    }
    const metricKey = getMetricsHistoryKey(host, metricType);
    if (!metricKey) {
        throw new Error(`Missing realtime metric key for ${metricType}`);
    }
    const previousValue = host.state.lastRealtimeMetricValues.get(metricKey);
    host.state.lastRealtimeMetricValues.set(metricKey, rawValue);
    if (!isFiniteNumber(previousValue)) {
        return null;
    }
    if (rawValue < previousValue) {
        return rawValue;
    }
    return rawValue - previousValue;
};

const processMetricsUpdate = (host: MetricsPageActionsHost, data: MetricsData): void => {
    if (!isObject(data)) {
        return;
    }
    host.state.currentMetrics = data;
    const timestamp = extractMetricsTimestamp(host, data);
    const chartValue = resolveRealtimeChartValue(host, data, host.state.currentMetricType);
    if (!isFiniteNumber(chartValue)) {
        updateMetricsDisplays(host);
        return;
    }
    if (!canApplyRealtimeMetricsHistory(host)) {
        updateMetricsDisplays(host, { skipChart: true });
        return;
    }
    appendMetricsHistoryPoint(host, timestamp, chartValue);
    const chart = host.state.mainChart;
    const isAnimating = chart?.view.status.isAnimating === true;
    const isDragging = chart?.view.status.isDragging === true;
    if (isMetricsCandlestickActive(host) && (host.state.candlestickBuckets.size > 0 || host.state.candlestickData.length > 0)) {
        const realtimeUpdate = updateRealtimeCandlestick(host, timestamp, chartValue);
        if (!isAnimating && !isDragging) {
            if (host.operations.trimCandlestickData(realtimeUpdate.appended)) {
                updateMetricsMainChart(host, { resetView: true });
            } else if (realtimeUpdate.point) {
                if (realtimeUpdate.appended) {
                    chart?.data.appendPoint(realtimeUpdate.point);
                } else if (realtimeUpdate.updated) {
                    chart?.data.updateCurrentBar(realtimeUpdate.point);
                }
            }
        } else {
            host.state.pendingChartSync = true;
        }
        updateMetricsDisplays(host, { skipChart: true });
        return;
    }
    updateMetricsDisplays(host);
};

export { appendMetricsHistoryPoint, processMetricsUpdate, resetMetricsData, resetMetricsValueHistory, trimMetricsHistoryPoints, updateMetricsMainChart };
export type { MetricsChartRenderOptions };
