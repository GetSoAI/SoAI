/* SoAI - Metrics page value history effects [frontend/assets/ts/pages/metrics/controllers/page/metricsValueHistoryEffects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { MetricsPageEffectsHost } from '@pages/metrics/controllers/page/contracts.ts';
import { trimMetricsHistoryPoints, updateMetricsMainChart } from '@pages/metrics/controllers/page/metricsUpdateProcessing.ts';
import { getMetricsHistoryAggregation, getMetricsHistoryKey, isMetricsCandlestickActive } from '@pages/metrics/controllers/page/state.ts';
import { fetchValueHistory, type ValueHistoryContext } from '@pages/metrics/state/valueHistory.ts';

const syncMetricsValueHistoryContext = (host: MetricsPageEffectsHost, context: ValueHistoryContext): void => {
    host.state.metricsHistory = context.metricsHistory;
    host.state.metricsHistoryExhausted = context.metricsHistoryExhausted;
    host.state.monitoringIntervalMs = context.monitoringIntervalMs;
};

const buildMetricsValueHistoryContext = (host: MetricsPageEffectsHost): ValueHistoryContext => ({
    chartRuntime: host.state.chartRuntime,
    getMetricHistoryKey: () => getMetricsHistoryKey(host),
    getMetricHistoryAggregation: () => getMetricsHistoryAggregation(host),
    getCatalogEntry: (metricKey: string) => host.state.metricsCatalog?.[metricKey] ?? null,
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

const fetchMetricsValueHistory = async (host: MetricsPageEffectsHost, options: { resetView?: boolean; beforeTimestamp?: number | null } = {}): Promise<void> => {
    const hasChartDataTransforms = Boolean(host.state.chartRuntime.getCachedModules()?.data);
    const context = buildMetricsValueHistoryContext(host);
    context.updateMainChart = (chartOptions) => {
        syncMetricsValueHistoryContext(host, context);
        updateMetricsMainChart(host, chartOptions);
    };
    const changed = await fetchValueHistory(context, options, hasChartDataTransforms);
    if (changed) {
        syncMetricsValueHistoryContext(host, context);
    }
};

export { fetchMetricsValueHistory };
