/* SoAI - Hardware page render effects [frontend/assets/ts/pages/hardware/controllers/render/effects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { throwIfAborted } from '@core/errors/abort.ts';
import { buildHistoryDisplaySeries, HistoryChartRuntime, markChartViewportFitted, resetChartViewportState, resolveChartViewportReset, type ChartPointInput, type HistoryPager } from '@features/charts/public.ts';
import { resolveHardwareHistoryIntervalMs } from '@pages/hardware/controllers/data/effects.ts';
import { applyHardwareCandlestickIntervalMetadata } from '@pages/hardware/state/history/hardwareCandlestickIntervalManager.ts';
import type { HardwarePageState } from '@pages/hardware/state/state.ts';
import type { ChartColorContext, HistoryDataPoint } from '@pages/hardware/types.ts';

type HardwareChartContext = {
    state: HardwarePageState;
    chartRuntime: HistoryChartRuntime;
    requireHTMLElement: (id: string) => HTMLElement;
    beginChartPresentationLoad: () => number;
    currentChartPresentationLoad: () => number;
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

const beginMainChartLoad = (context: HardwareChartContext, { presentation }: { presentation: boolean }): HardwareChartLoadToken => {
    const loadToken = presentation ? context.beginChartPresentationLoad() : context.currentChartPresentationLoad();
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

const initializeMainChart = async (context: HardwareChartContext, options: { signal?: AbortSignal | undefined; history: HistoryPager; onTimeRangeChange: (visibleStartTs: number, visibleEndTs: number) => void }): Promise<void> => {
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
            chartColorContext: context.buildChartColorContext(),
            history: options.history,
            onTimeRangeChange: (visibleStartTs: number, visibleEndTs: number): void => options.onTimeRangeChange(visibleStartTs, visibleEndTs)
        },
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

const buildHardwareDisplaySeries = (context: Pick<HardwareChartContext, 'state' | 'chartRuntime'>, source: readonly HistoryDataPoint[], candlestick: boolean): ChartPointInput[] => {
    if (source.length === 0) return [];
    return buildHistoryDisplaySeries(context.chartRuntime, source, { candlestick, intervalMs: resolveHardwareHistoryIntervalMs(context.state, candlestick), capacity: context.state.maxHistoryPoints });
};

const updateMainChart = (context: HardwareChartContext, { resetView = false, morph = false }: { resetView?: boolean; morph?: boolean } = {}): void => {
    const chart = context.state.mainChart;
    if (!chart) return;
    const shouldResetView = resolveChartViewportReset(context.state, resetView);
    const candlestick = context.isCandlestickActive();
    const intervalMs = resolveHardwareHistoryIntervalMs(context.state, candlestick);
    if (candlestick) applyHardwareCandlestickIntervalMetadata(context.state, intervalMs);
    chart.settings.update({
        scaleBounds: context.getMetricScaleBounds(),
        chartColorContext: context.buildChartColorContext(),
        expectedSampleIntervalMs: intervalMs
    });
    chart.settings.setChartType(context.state.chartType);
    chart.data.replace(buildHardwareDisplaySeries(context, candlestick ? context.state.candlestickData : context.state.historyData, candlestick), { preserveView: !shouldResetView, assumeSorted: true, morph });
    if (shouldResetView) {
        chart.view.fitTimeRange(context.state.timeRange);
        markChartViewportFitted(context.state);
    }
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

export { applyChartDataLimits, beginMainChartLoad, buildHardwareDisplaySeries, completeMainChartLoad, destroyChart, getPointBudget, initializeMainChart, updateMainChart };
export type { HardwareChartContext, HardwareChartLoadToken };
