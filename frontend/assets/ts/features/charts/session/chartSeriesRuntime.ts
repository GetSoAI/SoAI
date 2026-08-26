/* SoAI - Chart series storage algorithm contracts [frontend/assets/ts/features/charts/session/chartSeriesRuntime.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { OhlcData } from '@features/charts/component/chartComponentTypes.ts';
import type { ChartPointCandidate, NormalizedDataPoint } from '@features/charts/data/chartPointTypes.ts';
import type { ChartSeriesState } from '@features/charts/session/chartState.ts';

interface ChartSeriesStorageOperations {
    normalize(point: ChartPointCandidate): NormalizedDataPoint | null;
    findTimestamp(timestamp: number): { exact: boolean; index: number };
    hasOhlc(): boolean;
    ensureOhlc(): OhlcData;
    invalidateHeikin(index: number): void;
    discardHeikin(): void;
    upgradeToOhlc(): void;
    downgradeToValue(): void;
}

interface ChartSeriesStorageRuntime {
    series: ChartSeriesState;
    maxDataPoints: number;
    chartType: string;
    data: ChartSeriesStorageOperations;
}

interface SeriesInsertResult {
    changed: boolean;
    previousLength: number;
    nextLength: number;
    removedFromHead: number;
}

interface SeriesReplaceResult {
    previousLength: number;
    nextLength: number;
    startIndex: number;
    empty: boolean;
}

interface SeriesPrependResult {
    changed: boolean;
    addedToHead: number;
}

interface SeriesResizeResult {
    previousLength: number;
    nextLength: number;
    removedFromHead: number;
}

export type { ChartSeriesStorageOperations, ChartSeriesStorageRuntime, SeriesInsertResult, SeriesPrependResult, SeriesReplaceResult, SeriesResizeResult };
