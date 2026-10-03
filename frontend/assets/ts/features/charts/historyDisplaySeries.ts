/* SoAI - Charts feature history display series [frontend/assets/ts/features/charts/historyDisplaySeries.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonObject } from '@core/types/jsonValues.ts';
import type { ChartPointInput } from '@features/charts/data/chartPointTypes.ts';
import type { HistoryChartRuntimeContract } from '@features/charts/historyChartContracts.ts';

interface HistoryDisplaySourcePoint {
    timestamp: number;
    value?: number | null | undefined;
    open?: number | null | undefined;
    high?: number | null | undefined;
    low?: number | null | undefined;
    close?: number | null | undefined;
}

interface HistoryDisplaySeriesOptions {
    candlestick: boolean;
    intervalMs: number;
    capacity: number;
}

type HistoryDisplayRuntime = Pick<HistoryChartRuntimeContract, 'getDataTransforms' | 'getOhlc'>;

const DISPLAY_FIELDS: readonly Exclude<keyof HistoryDisplaySourcePoint, 'timestamp'>[] = ['value', 'open', 'high', 'low', 'close'];

const toJsonHistoryPoint = (point: HistoryDisplaySourcePoint): JsonObject => {
    const record: JsonObject = { timestamp: point.timestamp };
    for (const field of DISPLAY_FIELDS) {
        const value = point[field];
        if (typeof value === 'number' && Number.isFinite(value)) record[field] = value;
    }
    return record;
};

const buildHistoryDisplaySeries = (runtime: HistoryDisplayRuntime, source: readonly HistoryDisplaySourcePoint[], { candlestick, intervalMs, capacity }: HistoryDisplaySeriesOptions): ChartPointInput[] => {
    if (!(intervalMs > 0) || !(capacity >= 1)) throw new TypeError('History display series requires a positive interval and capacity');
    const points = source.map(toJsonHistoryPoint);
    if (candlestick) return runtime.getOhlc().buildCandlestickSeries(points, { maxPoints: capacity, timeRangeMs: Number.POSITIVE_INFINITY, intervalMs: Math.max(1, Math.round(intervalMs)) });
    return runtime.getDataTransforms().toLineSeries(points, capacity, { assumeSorted: true, fillGaps: false, intervalMs: Math.max(1, Math.round(intervalMs)), densityMode: 'preserve', targetPoints: capacity });
};

export { buildHistoryDisplaySeries };
export type { HistoryDisplayRuntime, HistoryDisplaySeriesOptions, HistoryDisplaySourcePoint };
