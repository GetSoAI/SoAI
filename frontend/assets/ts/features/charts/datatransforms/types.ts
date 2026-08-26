/* SoAI - Charts feature data transforms contracts [frontend/assets/ts/features/charts/datatransforms/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ChartOhlcPointInput, ChartValuePointInput } from '@features/charts/data/chartPointTypes.ts';

type DataPoint = ChartValuePointInput;
type OhlcPoint = ChartOhlcPointInput;
type DensityMode = 'shape' | 'average';

interface BuildLineGapFillersOptions {
    maxFill?: number;
    limit?: number;
}

interface TimeRangeSelectionOptions {
    retentionMinutes?: number;
    baseOptions?: readonly number[];
    selectedMinutes?: number | null;
    minimum?: number;
}

interface CandlestickIntervalSelectionOptions {
    timeRangeMinutes?: number;
    baseIntervals?: readonly number[];
    supportedIntervalsMs?: number[] | null;
    selectedIntervalMinutes?: number | null;
    pointBudget?: number | null;
    tolerance?: number;
    minimum?: number;
    monitoringIntervalMs?: number | null;
}

interface ToLineSeriesOptions {
    assumeSorted?: boolean;
    fillGaps?: boolean;
    intervalMs?: number | null;
    rangeMs?: number | null;
    densityMode?: DensityMode | undefined;
    targetPoints?: number | null | undefined;
}

interface ToHeikinAshiOptions {
    assumeSorted?: boolean;
}

interface BuildValueSeriesOptions {
    valueTransform?: ((value: number) => number) | null;
}

export type { BuildLineGapFillersOptions, BuildValueSeriesOptions, CandlestickIntervalSelectionOptions, DataPoint, DensityMode, OhlcPoint, TimeRangeSelectionOptions, ToHeikinAshiOptions, ToLineSeriesOptions };
