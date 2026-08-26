/* SoAI - Hardware page data effects [frontend/assets/ts/pages/hardware/controllers/data/effects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { decodeHardwareHistory } from '@core/api/contracts/hardwareContracts.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { isArray, isFiniteNumber } from '@core/typeGuards.ts';
import { clampHistoryChartPointCount, computeHistoryChartPointBudget, filterCandlestickBucketsForSeries, isCandlestickModeActive, resolveCandlestickIntervalMs, resolveHistoryChartPointLimit, trimCandlestickSeriesToTimeRange, type HistoryChartControlsManager, type HistoryChartPointBudgetConfig } from '@features/charts/public.ts';
import type { ChartOhlcContract } from '@pages/hardware/contracts/contracts.ts';
import { STR_AVG, STR_OHLC } from '@pages/hardware/contracts/hardwarePageSupport.ts';
import { getHistoryMetricKey } from '@pages/hardware/mappers/mappers.ts';
import { applyHardwareCandlestickIntervalMetadata, resolveHardwareStateCandlestickIntervalMs } from '@pages/hardware/state/history/hardwareCandlestickIntervalManager.ts';
import { buildHardwareHistoryRequestParameters } from '@pages/hardware/state/history/hardwareHistoryRequestParams.ts';
import { buildHistorySeriesFromPayload } from '@pages/hardware/state/history/hardwareHistorySeries.ts';
import type { HardwarePageState } from '@pages/hardware/state/state.ts';
import type { DeviceSelection, HistoryRequestParameters, HistorySeriesResult } from '@pages/hardware/types.ts';

type HardwareHistoryContext = {
    state: HardwarePageState;
    chartOhlc: ChartOhlcContract;
    historyControlsManager: HistoryChartControlsManager;
    getSelectedHistoryTarget: () => DeviceSelection;
    resolveSupportedHistoryComponent: (component: JsonValue) => string;
};

const isCandlestickActive = (state: HardwarePageState): boolean => {
    return isCandlestickModeActive({ chartType: state.chartType, chart: state.mainChart ?? undefined });
};

const getEffectiveCandlestickIntervalMs = (context: HardwareHistoryContext): number => {
    const resolved = resolveCandlestickIntervalMs({
        controlsManager: context.historyControlsManager,
        metadataIntervalMs: context.state.candlestickMetadata?.intervalMs,
        lastResolvedIntervalMs: context.state.lastResolvedCandlestickIntervalMs,
        requestedIntervalMinutes: context.state.candlestickIntervalMinutes,
        supportedHistoryIntervalsMs: context.state.supportedHistoryIntervalsMs,
        monitoringIntervalMs: context.state.monitoringIntervalMs
    });
    context.state.lastResolvedCandlestickIntervalMs = resolved;
    return resolved;
};

const getActiveAggregation = (state: HardwarePageState): string => {
    const preferred = isCandlestickActive(state) ? STR_OHLC : STR_AVG;
    if (!isArray(state.supportedHistoryAggregations)) {
        throw new TypeError('supportedHistoryAggregations must be an array');
    }
    if (!state.supportedHistoryAggregations.includes(preferred)) {
        throw new TypeError(`Unsupported aggregation: ${preferred}`);
    }
    return preferred;
};

const buildHardwareHistorySeries = (context: HardwareHistoryContext, payload: JsonValue): HistorySeriesResult | null => {
    const selectedTarget = context.getSelectedHistoryTarget();
    const metricKey = getHistoryMetricKey(context.state.selectedMetric, selectedTarget.type);
    const result = buildHistorySeriesFromPayload({
        payload: decodeHardwareHistory(payload),
        aggregation: getActiveAggregation(context.state),
        metricKey,
        monitoringIntervalMs: context.state.monitoringIntervalMs,
        chartOhlc: context.chartOhlc
    });
    if (!result) return null;
    if (result.type === STR_OHLC) {
        context.state.candlestickBuckets = result.candlestickBuckets;
    }
    return result;
};

const updateRealtimeCandlestick = (context: HardwareHistoryContext, timestampValue: JsonValue, valueInput: JsonValue): { appended: boolean } | null => {
    const timestamp = Number(timestampValue);
    const value = Number(valueInput);
    if (!isFiniteNumber(timestamp) || !isFiniteNumber(value)) return null;
    const intervalMs = getEffectiveCandlestickIntervalMs(context);
    return context.chartOhlc.updateRealtimeCandlestick(context.state.candlestickBuckets, context.state.candlestickData, timestamp, value, intervalMs);
};

const resolveHistoryPointLimit = (state: HardwarePageState): number => {
    return resolveHistoryChartPointLimit(getHistoryPointBudgetConfig(state));
};

const clampHistoryPoints = (state: HardwarePageState, value: number, min: number = 300): number => {
    return clampHistoryChartPointCount(getHistoryPointBudgetConfig(state), value, min);
};

const trimHistoryData = (state: HardwarePageState, force = false): boolean => {
    const { modified, data } = trimArrayByLength(state.historyData, state.maxHistoryPoints, force, state.historyTrimRatio);
    if (modified) state.historyData = data;
    return modified;
};

const resetHistoryState = (state: HardwarePageState, { clearLine = false, clearCandle = false }: { clearLine?: boolean; clearCandle?: boolean } = {}): void => {
    state.lineHistoryExhausted = false;
    state.candlestickHistoryExhausted = false;
    if (clearLine) state.historyData = [];
    if (clearCandle) {
        state.candlestickData = [];
        state.candlestickBuckets.clear();
    }
};

const trimCandlestickData = (state: HardwarePageState, force = false): boolean => {
    const { modified: lengthModified, data } = trimArrayByLength(state.candlestickData, state.maxHistoryPoints, force, state.historyTrimRatio);
    state.candlestickData = data;
    if (state.candlestickData.length === 0) {
        state.candlestickBuckets.clear();
        return lengthModified;
    }
    const intervalMs = resolveHardwareStateCandlestickIntervalMs(state);
    applyHardwareCandlestickIntervalMetadata(state, intervalMs);
    const trimmed = trimCandlestickSeriesToTimeRange({
        candles: state.candlestickData,
        pointBudget: state.maxHistoryPoints,
        timeRangeMs: Math.max(60000, Math.round(state.timeRange * 60000)),
        intervalMs: intervalMs,
        errorContext: 'candlestickData'
    });
    if (trimmed.modified) {
        state.candlestickData = trimmed.candles;
    }
    state.candlestickBuckets = filterCandlestickBucketsForSeries(state.candlestickData, state.candlestickBuckets);
    return lengthModified || trimmed.modified;
};

const buildHistoryRequestParameters = (context: HardwareHistoryContext): HistoryRequestParameters => {
    const pointBudgetConfig = getHistoryPointBudgetConfig(context.state);
    const { parameters, pointBudget } = buildHardwareHistoryRequestParameters({
        getSelectedHistoryTarget: () => context.getSelectedHistoryTarget(),
        resolveSupportedHistoryComponent: (component: JsonValue): string => context.resolveSupportedHistoryComponent(component),
        getActiveAggregation: () => getActiveAggregation(context.state),
        computeHistoryPoints: (rangeMs: number): number => computeHistoryChartPointBudget(pointBudgetConfig, rangeMs),
        getEffectiveCandlestickIntervalMs: (): number => getEffectiveCandlestickIntervalMs(context),
        clampHistoryPoints: (points: number, min?: number): number => clampHistoryChartPointCount(pointBudgetConfig, points, min),
        timeRange: context.state.timeRange,
        maxRetentionMinutes: context.state.maxRetentionMinutes
    });
    context.state.currentHistoryPointBudget = pointBudget;
    return parameters;
};

const getHistoryPointBudgetConfig = (state: HardwarePageState): HistoryChartPointBudgetConfig => {
    return {
        monitoringIntervalMs: state.monitoringIntervalMs,
        chartHardLimit: state.chartHardLimit,
        historyApiPointCap: state.historyApiPointCap,
        maxHistoryPoints: state.maxHistoryPoints,
        maxRetentionMinutes: state.maxRetentionMinutes,
        candlestickActive: isCandlestickActive(state),
        candlestickIntervalMinutes: state.candlestickIntervalMinutes
    };
};

const trimArrayByLength = <T>(data: ReadonlyArray<T>, limit: number, force: boolean, historyTrimRatio: number): { modified: boolean; data: T[] } => {
    const effectiveLimit = Math.max(1, Math.floor(limit ?? 0));
    if (effectiveLimit <= 0) return { modified: false, data: [...data] };
    const ratio = isFiniteNumber(historyTrimRatio) ? historyTrimRatio : 1.05;
    const threshold = force ? effectiveLimit : Math.floor(effectiveLimit * ratio);
    return data.length > threshold ? { modified: true, data: data.slice(-effectiveLimit) } : { modified: false, data: [...data] };
};

export { buildHardwareHistorySeries, buildHistoryRequestParameters, clampHistoryPoints, getActiveAggregation, getEffectiveCandlestickIntervalMs, isCandlestickActive, resetHistoryState, resolveHistoryPointLimit, trimCandlestickData, trimHistoryData, updateRealtimeCandlestick };
export type { HardwareHistoryContext };
