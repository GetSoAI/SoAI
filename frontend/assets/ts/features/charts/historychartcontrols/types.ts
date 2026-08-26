/* SoAI - Charts feature history chart controls contracts [frontend/assets/ts/features/charts/historychartcontrols/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { CandlestickSelection, ChartDataTransformsApi, TimeRangeSelection } from '@features/charts/controlsTypes.ts';
import type { HistoryChartRuntimeContract } from '@features/charts/historyChartContracts.ts';

interface HistoryChartControlsManagerConfig {
    chartRuntime?: HistoryChartRuntimeContract;
}

interface TimeRangeOptions {
    retentionMinutes?: number | undefined;
    baseOptions?: number[] | undefined;
    selectedMinutes?: number | undefined;
    minimum?: number | undefined;
}

interface CandlestickSelectionOptions {
    timeRangeMinutes?: number | undefined;
    baseIntervals?: number[] | undefined;
    supportedIntervalsMs?: number[] | undefined;
    selectedIntervalMinutes?: number | undefined;
    pointBudget?: number | undefined;
    monitoringIntervalMs?: number | undefined;
}

interface SyncTimeRangeControlsOptions {
    retentionMinutes?: number | undefined;
    baseOptions?: number[] | undefined;
    selectedMinutes?: number | undefined;
    onSelection?: ((selection: TimeRangeSelection) => void) | undefined;
}

interface SyncCandlestickControlsOptions {
    timeRangeMinutes?: number | undefined;
    baseIntervals?: number[] | undefined;
    supportedIntervalsMs?: number[] | undefined;
    selectedIntervalMinutes?: number | undefined;
    pointBudget?: number | undefined;
    monitoringIntervalMs?: number | undefined;
    onSelection?: ((selection: CandlestickSelection) => void) | undefined;
}

interface ResolveCandlestickIntervalMsOptions {
    metadataIntervalMs?: number | undefined;
    lastResolvedIntervalMs?: number | undefined;
    requestedIntervalMinutes?: number | undefined;
    supportedHistoryIntervalsMs?: number[] | undefined;
    monitoringIntervalMs?: number | undefined;
}

interface ResolveTimeRangeSelectionOptions extends TimeRangeOptions {
    chartRuntime: HistoryChartRuntimeContract;
}

interface ResolveCandlestickSelectionOptions extends CandlestickSelectionOptions {
    chartRuntime: HistoryChartRuntimeContract;
}

interface ResolveCandlestickIntervalMsResolverOptions extends ResolveCandlestickIntervalMsOptions {
    chartRuntime: HistoryChartRuntimeContract;
}

export type { CandlestickSelectionOptions, ChartDataTransformsApi, HistoryChartControlsManagerConfig, HistoryChartRuntimeContract, ResolveCandlestickIntervalMsOptions, ResolveCandlestickIntervalMsResolverOptions, ResolveCandlestickSelectionOptions, ResolveTimeRangeSelectionOptions, SyncCandlestickControlsOptions, SyncTimeRangeControlsOptions, TimeRangeOptions };
