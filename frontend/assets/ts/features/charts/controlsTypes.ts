/* SoAI - Shared types for history chart control selection and transform APIs [frontend/assets/ts/features/charts/controlsTypes.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

interface ChartDataTransformsApi {
    buildTimeRangeSelection(options: TimeRangeSelectionOptions): TimeRangeSelection;
    buildCandlestickIntervalSelection(options: CandlestickIntervalSelectionOptions): CandlestickSelection;
    formatTimeRangeMinutes(value: number): string;
    resolveSupportedIntervalMs(requested: number, supported: number[], baseline: number): number;
    constants: {
        DEFAULT_TIME_RANGES: number[];
        DEFAULT_CANDLE_INTERVALS: number[];
    };
}

interface TimeRangeSelectionOptions {
    retentionMinutes?: number | undefined;
    baseOptions?: number[] | undefined;
    selectedMinutes?: number | undefined;
    minimum?: number | undefined;
}

interface CandlestickIntervalSelectionOptions {
    timeRangeMinutes?: number | undefined;
    baseIntervals?: number[] | undefined;
    supportedIntervalsMs?: number[] | undefined;
    selectedIntervalMinutes?: number | undefined;
    pointBudget?: number | undefined;
    tolerance?: number | undefined;
    monitoringIntervalMs?: number | undefined;
    minimum?: number | undefined;
}

interface BaseSelection {
    selected: number;
    options: number[];
}

type TimeRangeSelection = BaseSelection;

interface CandlestickSelection extends BaseSelection {
    intervalMs: number;
}

export type { CandlestickIntervalSelectionOptions, CandlestickSelection, ChartDataTransformsApi, TimeRangeSelection, TimeRangeSelectionOptions };
export type { BaseSelection };
