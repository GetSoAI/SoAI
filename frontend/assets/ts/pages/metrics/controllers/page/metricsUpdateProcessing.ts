/* SoAI - Metrics page update processing [frontend/assets/ts/pages/metrics/controllers/page/metricsUpdateProcessing.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isFiniteNumber, isObject } from '@core/typeGuards.ts';
import { formatCompactNumber } from '@core/primitives/compactNumber.ts';
import { updateAdaptiveNumber } from '@core/ui/adaptiveNumber.ts';
import { appendHistoryValue, buildHistoryDisplaySeries, markChartViewportFitted, resolveChartViewportReset, type ChartPointInput } from '@features/charts/public.ts';
import { KPI_CONFIG, refreshMetricsAdvancedModalIfOpen, resolveMetricsTotalTokens } from '@features/metrics/public.ts';
import type { MetricsPageActionsHost } from '@pages/metrics/controllers/page/contracts.ts';
import { extractMetricsTimestamp, extractMetricsValue, getEffectiveMetricsCandlestickIntervalMs, getMetricsHistoryAggregation, getMetricsHistoryKey, getMetricsMetricScaleBounds, isMetricsCandlestickActive, resolveMetricsValueIntervalMs } from '@pages/metrics/controllers/page/state.ts';
import { trimMetricsHistory } from '@pages/metrics/mappers/metricsHistoryMapping.ts';
import type { CandlestickDataPoint, MetricsData, MetricsHistoryPoint, RealtimeCandlestickUpdate } from '@pages/metrics/types.ts';
import { updateDistributionChart, updateSystemStats } from '@pages/metrics/widgets/effects.ts';
import { updateApiKeyUsageTable } from '@pages/metrics/widgets/apiKeyUsageTableWidget.ts';
import { updateModelTable, updatePluginHealth } from '@pages/metrics/widgets/service.ts';

const resetMetricsValueHistory = (host: MetricsPageActionsHost, { clear = false }: { clear?: boolean } = {}): void => {
    host.state.lastRealtimeMetricValues.clear();
    if (clear) {
        host.state.metricsHistory = [];
        host.state.historyIntervalMs = null;
    }
};

const resetMetricsData = (host: MetricsPageActionsHost, fullReset = false): void => {
    host.state.candlestickData = [];
    host.state.candlestickBuckets.clear();
    host.state.candlestickMetadata = null;
    host.state.lastResolvedCandlestickIntervalMs = null;
    resetMetricsValueHistory(host, { clear: fullReset });
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

const appendMetricsHistoryPoint = (host: MetricsPageActionsHost, timestamp: number, value: number): 'ignored' | 'updated' | 'appended' | 'trimmed' => {
    if (!isFiniteNumber(timestamp) || !isFiniteNumber(value)) {
        return 'ignored';
    }
    const result = appendHistoryValue(host.state.metricsHistory, timestamp, value, resolveMetricsValueIntervalMs(host), getMetricsHistoryAggregation(host, host.state.currentMetricType));
    return result === 'appended' && trimMetricsHistoryPoints(host) ? 'trimmed' : result;
};

const canApplyRealtimeMetricsHistory = (host: MetricsPageActionsHost): boolean => {
    if (!host.state.metricsHistoryEnabled) {
        return true;
    }
    return host.history.isInitialized();
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

const buildMetricsDisplaySeries = (host: MetricsPageActionsHost, source: readonly (MetricsHistoryPoint | CandlestickDataPoint)[], candlestick: boolean): ChartPointInput[] => {
    if (source.length === 0) return [];
    const intervalMs = candlestick ? getEffectiveMetricsCandlestickIntervalMs(host) : host.operations.normalizeMetricsInt(resolveMetricsValueIntervalMs(host), 1);
    return buildHistoryDisplaySeries(host.state.chartRuntime, source, { candlestick, intervalMs, capacity: host.state.maxHistoryPoints });
};

const updateMetricsMainChart = (host: MetricsPageActionsHost, { resetView = false, morph = false }: { resetView?: boolean; morph?: boolean } = {}): void => {
    const chart = host.state.mainChart;
    if (!chart) {
        return;
    }
    const shouldResetView = resolveChartViewportReset(host.state, resetView);
    const candlestick = isMetricsCandlestickActive(host);
    chart.settings.update({ scaleBounds: getMetricsMetricScaleBounds(host.state.currentMetricType), expectedSampleIntervalMs: candlestick ? getEffectiveMetricsCandlestickIntervalMs(host) : resolveMetricsValueIntervalMs(host) });
    chart.settings.setChartType(host.state.currentChartType);
    chart.data.replace(buildMetricsDisplaySeries(host, candlestick ? host.state.candlestickData : host.state.metricsHistory, candlestick), { preserveView: !shouldResetView, assumeSorted: true, morph });
    if (shouldResetView) {
        chart.view.fitTimeRange(host.state.timeRange);
        markChartViewportFitted(host.state);
    }
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

const applyRealtimeMetricsChartValue = (host: MetricsPageActionsHost, timestamp: number, chartValue: number, { renderChart = true }: { renderChart?: boolean } = {}): void => {
    if (host.state.metricsHistoryEnabled && !host.history.acceptRealtimeTimestamp(timestamp)) {
        return;
    }
    const chart = host.state.mainChart;
    if (isMetricsCandlestickActive(host)) {
        const realtimeUpdate = updateRealtimeCandlestick(host, timestamp, chartValue);
        if (host.operations.trimCandlestickData(realtimeUpdate.appended)) {
            if (!renderChart) {
                return;
            }
            updateMetricsMainChart(host);
        } else if (renderChart && realtimeUpdate.point) {
            if (realtimeUpdate.appended) {
                chart?.data.appendPoint(realtimeUpdate.point);
            } else if (realtimeUpdate.updated) {
                chart?.data.updateCurrentBar(realtimeUpdate.point);
            }
        }
        return;
    }
    const update = appendMetricsHistoryPoint(host, timestamp, chartValue);
    if (update === 'trimmed' && renderChart) updateMetricsMainChart(host);
    else if (renderChart && (update === 'appended' || update === 'updated')) {
        const latest = host.state.metricsHistory[host.state.metricsHistory.length - 1];
        if (!latest) throw new Error('Metrics realtime update did not retain its sample');
        if (update === 'appended') chart?.data.appendPoint(latest);
        else chart?.data.updateCurrentBar(latest);
    }
};

const refreshMetricsPresentation = (host: MetricsPageActionsHost): void => {
    if (canApplyRealtimeMetricsHistory(host)) {
        updateMetricsMainChart(host);
    }
    updateMetricsDisplays(host, { skipChart: true });
    updateApiKeyUsageTable(host);
    if (!host.state.currentMetrics) {
        updateDistributionChart(host);
    }
};

const processMetricsUpdate = (host: MetricsPageActionsHost, data: MetricsData, { renderDisplays = true }: { renderDisplays?: boolean } = {}): void => {
    if (!isObject(data)) {
        return;
    }
    host.state.currentMetrics = data;
    const renderNow = host.presentation.requestRefresh();
    const timestamp = extractMetricsTimestamp(host, data);
    const chartValue = resolveRealtimeChartValue(host, data, host.state.currentMetricType);
    if (!isFiniteNumber(chartValue)) {
        if (renderNow && renderDisplays) {
            updateMetricsDisplays(host);
        }
        return;
    }
    host.history.captureRealtimeSample(timestamp, chartValue);
    if (!canApplyRealtimeMetricsHistory(host)) {
        if (renderNow && renderDisplays) {
            updateMetricsDisplays(host, { skipChart: true });
        }
        return;
    }
    applyRealtimeMetricsChartValue(host, timestamp, chartValue, { renderChart: renderNow });
    if (renderNow && renderDisplays) {
        updateMetricsDisplays(host, { skipChart: true });
    }
};

export { appendMetricsHistoryPoint, applyRealtimeMetricsChartValue, buildMetricsDisplaySeries, processMetricsUpdate, refreshMetricsPresentation, resetMetricsData, resetMetricsValueHistory, trimMetricsHistoryPoints, updateMetricsDisplays, updateMetricsMainChart };
