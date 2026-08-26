/* SoAI - Chart series indexed storage mutations [frontend/assets/ts/features/charts/session/chartSeriesActions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { clampNumber } from '@core/primitives/clampNumber.ts';
import { isArray } from '@core/typeGuards.ts';
import { isFin } from '@features/charts/component/chartComponentStatics.ts';
import type { ChartPointCandidate, NormalizedDataPoint } from '@features/charts/data/chartPointTypes.ts';
import type { ChartSeriesStorageRuntime, SeriesInsertResult } from '@features/charts/session/chartSeriesRuntime.ts';

const isMonotonicByTimestamp = (points: ReadonlyArray<{ timestamp: number } | null | undefined>): boolean => {
    for (let index = 1; index < points.length; index += 1) {
        const previous = points[index - 1];
        const current = points[index];
        if (previous && current && previous.timestamp > current.timestamp) return false;
    }
    return true;
};

const setSeriesPoint = (runtime: ChartSeriesStorageRuntime, index: number, point: NormalizedDataPoint): void => {
    const series = runtime.series;
    series.timestamps[index] = point.timestamp;
    series.values[index] = point.value;
    if (point.sourceMode === 'heikin-ashi') series.sourceSeriesMode = 'heikin-ashi';
    else if (point.mode === 'ohlc' && series.sourceSeriesMode === 'value') series.sourceSeriesMode = 'ohlc';
    if (runtime.data.hasOhlc()) {
        const ohlc = runtime.data.ensureOhlc();
        ohlc.open[index] = point.open;
        ohlc.high[index] = point.high;
        ohlc.low[index] = point.low;
        ohlc.close[index] = point.close;
        runtime.data.invalidateHeikin(index);
        return;
    }
    if (runtime.chartType === 'heikin-ashi') runtime.data.invalidateHeikin(index);
};

const shiftDatasetsForInsert = (runtime: ChartSeriesStorageRuntime, index: number, currentLength: number): void => {
    const targetLength = Math.min(runtime.maxDataPoints, currentLength + 1);
    const insertAt = clampNumber(index, 0, targetLength - 1);
    for (const dataset of runtime.series.datasets) {
        const values = dataset.values;
        const valuesLength = Number(values?.length);
        if (!isFin(valuesLength) || valuesLength === 0) continue;
        if (values instanceof Float64Array) {
            const next = new Float64Array(targetLength);
            next.fill(Number.NaN);
            const beforeCount = Math.min(valuesLength, insertAt);
            if (beforeCount > 0) next.set(values.subarray(0, beforeCount));
            const afterCount = Math.min(valuesLength - insertAt, targetLength - insertAt - 1);
            if (afterCount > 0) next.set(values.subarray(insertAt, insertAt + afterCount), insertAt + 1);
            dataset.values = next;
        } else if (isArray(values)) {
            dataset.values = [...values.slice(0, insertAt), Number.NaN, ...values.slice(insertAt, targetLength - 1)].slice(0, targetLength);
        }
    }
};

const shiftDatasetsForRollingWindow = (runtime: ChartSeriesStorageRuntime): void => {
    for (const dataset of runtime.series.datasets) {
        const values = dataset.values;
        if ((!isArray(values) && !(values instanceof Float64Array)) || !isFin(values.length) || values.length <= 0) continue;
        values.copyWithin(0, 1);
        values[values.length - 1] = Number.NaN;
    }
};

const insertSeriesPoint = (runtime: ChartSeriesStorageRuntime, index: number, point: NormalizedDataPoint): SeriesInsertResult => {
    const series = runtime.series;
    const previousLength = series.dataLength;
    let insertAt = index;
    let removedFromHead = 0;
    if (series.dataLength >= runtime.maxDataPoints) {
        series.timestamps.copyWithin(0, 1, series.dataLength);
        series.values.copyWithin(0, 1, series.dataLength);
        if (runtime.data.hasOhlc() && series.ohlc) {
            for (const values of Object.values(series.ohlc)) values.copyWithin(0, 1, series.dataLength);
        }
        shiftDatasetsForRollingWindow(runtime);
        series.dataLength = Math.max(0, series.dataLength - 1);
        runtime.data.invalidateHeikin(0);
        insertAt = Math.max(0, insertAt - 1);
        removedFromHead = 1;
    }
    const currentLength = series.dataLength;
    if (insertAt < currentLength) {
        series.timestamps.copyWithin(insertAt + 1, insertAt, currentLength);
        series.values.copyWithin(insertAt + 1, insertAt, currentLength);
        if (runtime.data.hasOhlc() && series.ohlc) {
            for (const values of Object.values(series.ohlc)) values.copyWithin(insertAt + 1, insertAt, currentLength);
        }
    }
    shiftDatasetsForInsert(runtime, insertAt, currentLength);
    setSeriesPoint(runtime, insertAt, point);
    series.dataLength = Math.min(runtime.maxDataPoints, currentLength + 1);
    return { changed: true, previousLength, nextLength: series.dataLength, removedFromHead };
};

const updateCurrentSeriesBar = (runtime: ChartSeriesStorageRuntime, input: ChartPointCandidate): SeriesInsertResult => {
    const point = runtime.data.normalize(input);
    const previousLength = runtime.series.dataLength;
    if (!point) return { changed: false, previousLength, nextLength: previousLength, removedFromHead: 0 };
    if (previousLength === 0) runtime.series.dataLength = 1;
    if (point.mode === 'ohlc' && !runtime.data.hasOhlc()) runtime.data.upgradeToOhlc();
    setSeriesPoint(runtime, runtime.series.dataLength - 1, point);
    return { changed: true, previousLength, nextLength: runtime.series.dataLength, removedFromHead: 0 };
};

const trimSeriesDatasets = (runtime: Pick<ChartSeriesStorageRuntime, 'series'>, startIndex: number, targetLength: number): void => {
    const normalizedStart = Math.max(0, Math.floor(startIndex) || 0);
    const normalizedLength = Math.max(0, Math.floor(targetLength) || 0);
    for (const dataset of runtime.series.datasets) {
        const values = dataset.values;
        if (!values || !isFin(values.length) || values.length <= 0) continue;
        const sliceStart = Math.min(normalizedStart, values.length);
        const sliceEnd = Math.min(values.length, sliceStart + normalizedLength);
        if (isArray(values)) dataset.values = values.slice(sliceStart, sliceEnd);
        else if (values instanceof Float64Array) dataset.values = new Float64Array(values.subarray(sliceStart, sliceEnd));
    }
};

export { insertSeriesPoint, isMonotonicByTimestamp, setSeriesPoint, shiftDatasetsForInsert, shiftDatasetsForRollingWindow, trimSeriesDatasets, updateCurrentSeriesBar };
