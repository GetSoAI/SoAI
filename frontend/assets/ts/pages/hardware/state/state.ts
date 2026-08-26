/* SoAI - Hardware page state [frontend/assets/ts/pages/hardware/state/state.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonObject } from '@core/types/jsonValues.ts';
import { HISTORY_CHART_DEFAULT_CAP, HISTORY_CHART_MIN_POINTS, type CandlestickPoint } from '@features/charts/public.ts';
import type { ChartInstance } from '@pages/hardware/contracts/contracts.ts';
import { STR_AVG, STR_CPU, STR_GPU, STR_USAGE } from '@pages/hardware/contracts/hardwarePageSupport.ts';
import type { HardwareCapabilities, HardwarePageSnapshot, HistoryDataPoint, HistoryMetadata, MetricsData } from '@pages/hardware/types.ts';

type HardwarePageState = {
    lastSnapshot: HardwarePageSnapshot | null;
    currentMetrics: MetricsData | null;
    hardwareCapabilities: HardwareCapabilities | null;
    webuiPermissions: { actions: string[]; isAdmin: boolean } | null;
    soaibenchRuns: JsonObject | null;

    historyData: HistoryDataPoint[];
    historyMetadata: HistoryMetadata | null;
    candlestickData: CandlestickPoint[];
    candlestickMetadata: HistoryMetadata | null;
    candlestickBuckets: Map<number, CandlestickPoint & { count: number }>;

    chartHardLimit: number;
    historyTrimRatio: number;
    monitoringIntervalMs: number;
    currentHistoryPointBudget: number;
    historyApiPointCap: number;
    maxHistoryPoints: number;
    maxRetentionMinutes: number | null;

    availableTimeRanges: number[];
    baseTimeRangeOptions: number[];
    baseCandleIntervals: number[];

    selectedDevice: string;
    selectedMetric: string;
    timeRange: number;
    chartType: string;
    candlestickIntervalMinutes: number;
    lastResolvedCandlestickIntervalMs: number | undefined;
    supportedHistoryIntervalsMs: number[] | undefined;
    supportedHistoryAggregations: string[];
    supportedHistoryComponents: string[];

    mainChart: ChartInstance | null;
    initialChartViewportFitted: boolean;
    lineHistoryExhausted: boolean;
    candlestickHistoryExhausted: boolean;
};

const createHardwarePageState = (): HardwarePageState => ({
    lastSnapshot: null,
    currentMetrics: null,
    hardwareCapabilities: null,
    webuiPermissions: null,
    soaibenchRuns: null,
    historyData: [],
    historyMetadata: null,
    candlestickData: [],
    candlestickMetadata: null,
    candlestickBuckets: new Map<number, CandlestickPoint & { count: number }>(),
    chartHardLimit: 50000,
    historyTrimRatio: 1.1,
    monitoringIntervalMs: 2000,
    currentHistoryPointBudget: 0,
    historyApiPointCap: HISTORY_CHART_DEFAULT_CAP,
    maxHistoryPoints: HISTORY_CHART_MIN_POINTS,
    maxRetentionMinutes: null,
    availableTimeRanges: [],
    baseTimeRangeOptions: [],
    baseCandleIntervals: [],
    selectedDevice: STR_CPU,
    selectedMetric: STR_USAGE,
    timeRange: 120,
    chartType: 'area',
    candlestickIntervalMinutes: 1,
    lastResolvedCandlestickIntervalMs: undefined,
    supportedHistoryIntervalsMs: undefined,
    supportedHistoryAggregations: [STR_AVG],
    supportedHistoryComponents: [STR_CPU, STR_GPU],
    mainChart: null,
    initialChartViewportFitted: false,
    lineHistoryExhausted: false,
    candlestickHistoryExhausted: false
});

export { createHardwarePageState };
export type { HardwarePageState };
