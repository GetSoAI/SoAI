/* SoAI - Hardware page render effects [frontend/assets/ts/pages/hardware/controllers/render/effects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { throwIfAborted } from '@core/errors/abort.ts';
import { isArray } from '@core/typeGuards.ts';
import { serverEpochMs } from '@core/time/clock.ts';
import { HistoryChartRuntime, markChartViewportFitted, resetChartViewportState, resolveChartViewportReset, type CandlestickPoint, type ChartValuePointInput } from '@features/charts/public.ts';
import { applyHardwareCandlestickIntervalMetadata, resolveHardwareStateCandlestickIntervalMs } from '@pages/hardware/state/history/hardwareCandlestickIntervalManager.ts';
import { buildHardwareCandlestickSeries, buildHardwareValueSeries } from '@pages/hardware/state/history/hardwareSeriesBuilders.ts';
import type { HardwarePageState } from '@pages/hardware/state/state.ts';
import type { ChartColorContext, HistoryDataPoint } from '@pages/hardware/types.ts';

type HardwareChartContext = {
    state: HardwarePageState;
    chartRuntime: HistoryChartRuntime;
    requireHTMLElement: (id: string) => HTMLElement;
    beginChartPresentationLoad: () => number;
    completeChartPresentationLoad: (sequence: number) => void;
    resetChartPresentation: () => void;
    destroyChartPresentation: () => void;
    getMetricScaleBounds: () => { min?: number | undefined; max?: number | undefined } | null;
    buildChartColorContext: () => ChartColorContext;
    getMetricLabel: () => string;
    formatMetricValue: (value: number) => string;
    isCandlestickActive: () => boolean;
    resetHistoryState: (options: { clearLine?: boolean; clearCandle?: boolean }) => void;
    trimHistoryData: (force?: boolean) => boolean;
};

type HardwareChartLoadToken = number;

const beginMainChartLoad = (context: HardwareChartContext): HardwareChartLoadToken => {
    const loadToken = context.beginChartPresentationLoad();
    context.resetHistoryState({ clearLine: true, clearCandle: true });
    context.state.historyMetadata = null;
    context.state.candlestickMetadata = null;
    context.state.lastResolvedCandlestickIntervalMs = undefined;
    return loadToken;
};

const completeMainChartLoad = (context: HardwareChartContext, loadToken: HardwareChartLoadToken): void => {
    context.completeChartPresentationLoad(loadToken);
};

const getPointBudget = (context: HardwareChartContext): number => {
    return context.chartRuntime.resolvePointBudget({
        chart: context.state.mainChart ?? undefined,
        maxHistoryPoints: context.state.maxHistoryPoints,
        historyApiPointCap: context.state.historyApiPointCap
    });
};

const initializeMainChart = async (context: HardwareChartContext, options: { signal?: AbortSignal | undefined; onRequestHistoricalData: (timestamp: number) => void | Promise<void> }): Promise<void> => {
    throwIfAborted(options.signal);
    const host = context.requireHTMLElement('hardwareHistoryChart');
    context.resetChartPresentation();
    host.textContent = '';
    const chart = await context.chartRuntime.initializeChart({
        container: host,
        chartType: context.state.chartType,
        options: {
            scaleBounds: context.getMetricScaleBounds(),
            maxDataPoints: context.state.maxHistoryPoints,
            chartColorContext: context.buildChartColorContext()
        },
        onRequestHistoricalData: (timestamp: number): void | Promise<void> => options.onRequestHistoricalData(timestamp),
        signal: options.signal
    });
    if (!chart) {
        throw new Error('Chart initialization returned no chart instance');
    }
    if (options.signal?.aborted) {
        await chart.lifecycle.destroy();
        throwIfAborted(options.signal);
    }
    context.state.mainChart = chart;
    resetChartViewportState(context.state);
    chart.settings.setMetricName(context.getMetricLabel());
    chart.settings.setValueFormatter((value: number) => context.formatMetricValue(value));
};

const updateMainChart = (context: HardwareChartContext, { resetView = false }: { resetView?: boolean } = {}): void => {
    const chart = context.state.mainChart;
    if (!chart) return;
    const shouldResetView = resolveChartViewportReset(context.state, resetView);
    const candlestickActive = context.isCandlestickActive();
    chart.settings.setChartType(candlestickActive ? 'candlestick' : context.state.chartType);
    chart.settings.update({
        scaleBounds: context.getMetricScaleBounds(),
        chartColorContext: context.buildChartColorContext()
    });
    const source = candlestickActive ? context.state.candlestickData : context.state.historyData;
    if (!isArray(source)) throw new TypeError('sourceData must be an array');
    const rangeMs = Math.max(60000, Math.round(context.state.timeRange * 60000));
    const last = source[source.length - 1];
    const reference = last ? last.timestamp : serverEpochMs();
    if (candlestickActive) {
        const intervalMs = resolveHardwareStateCandlestickIntervalMs(context.state);
        applyHardwareCandlestickIntervalMetadata(context.state, intervalMs);
        const cutoff = reference - rangeMs - intervalMs;
        const filtered = source.filter((point: HistoryDataPoint) => point?.timestamp >= cutoff);
        const series = buildCandlestickSeries(context, filtered);
        const anchorTail = chart.view.status.isAtTail;
        chart.data.replace(series, { preserveView: !shouldResetView || !anchorTail, assumeSorted: true });
    } else {
        const cutoff = reference - rangeMs;
        const filtered = source.filter((point: HistoryDataPoint) => point?.timestamp >= cutoff);
        const series = buildValueSeries(context, filtered);
        chart.data.replace(series, { preserveView: !shouldResetView, assumeSorted: true });
    }
    if (shouldResetView) {
        chart.view.fitTimeRange(context.state.timeRange, { align: 'tail' });
        markChartViewportFitted(context.state);
    } else if (chart.view.status.isAtTail) chart.view.alignToLatest();
    chart.settings.setMetricName(context.getMetricLabel());
    chart.settings.setValueFormatter((value: number) => context.formatMetricValue(value));
};

const applyChartDataLimits = (context: HardwareChartContext): void => {
    context.trimHistoryData(true);
    context.state.mainChart?.settings.update({ maxDataPoints: context.state.maxHistoryPoints });
};

const destroyChart = async (context: HardwareChartContext): Promise<void> => {
    context.destroyChartPresentation();
    if (context.state.mainChart) {
        await context.state.mainChart.lifecycle.destroy();
        context.state.mainChart = null;
    }
};

const buildValueSeries = (context: HardwareChartContext, data: HistoryDataPoint[], max: number | undefined = context.state.mainChart?.settings.snapshot.maxDataPoints): ChartValuePointInput[] => {
    return buildHardwareValueSeries(
        {
            maxHistoryPoints: context.state.maxHistoryPoints,
            monitoringIntervalMs: context.state.monitoringIntervalMs,
            timeRange: context.state.timeRange,
            chartType: context.state.chartType,
            chartDataTransforms: context.chartRuntime.getDataTransforms(),
            chartOhlc: context.chartRuntime.getOhlc()
        },
        data,
        max
    );
};

const buildCandlestickSeries = (context: HardwareChartContext, data: HistoryDataPoint[], max: number | undefined = context.state.mainChart?.settings.snapshot.maxDataPoints): CandlestickPoint[] => {
    return buildHardwareCandlestickSeries(
        {
            candlestickMetadata: context.state.candlestickMetadata,
            lastResolvedCandlestickIntervalMs: context.state.lastResolvedCandlestickIntervalMs,
            monitoringIntervalMs: context.state.monitoringIntervalMs,
            chartOhlc: context.chartRuntime.getOhlc()
        },
        data,
        max
    );
};

export { applyChartDataLimits, beginMainChartLoad, completeMainChartLoad, destroyChart, getPointBudget, initializeMainChart, updateMainChart };
export type { HardwareChartContext, HardwareChartLoadToken };
