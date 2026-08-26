/* SoAI - Chart series collection storage mutations [frontend/assets/ts/features/charts/session/chartSeriesMutations.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isArray, isString } from '@core/typeGuards.ts';
import { TIMESTAMP_EPSILON } from '@features/charts/component/chartComponentStatics.ts';
import type { DatasetInput, DatasetValue } from '@features/charts/chartTypes.ts';
import type { ChartPointCandidate, NormalizedDataPoint } from '@features/charts/data/chartPointTypes.ts';
import { insertSeriesPoint, isMonotonicByTimestamp, setSeriesPoint, updateCurrentSeriesBar } from '@features/charts/session/chartSeriesActions.ts';
import type { ChartSeriesStorageRuntime, SeriesInsertResult, SeriesPrependResult, SeriesReplaceResult } from '@features/charts/session/chartSeriesRuntime.ts';

const appendSeriesPoint = (runtime: ChartSeriesStorageRuntime, input: ChartPointCandidate): SeriesInsertResult => {
    const point = runtime.data.normalize(input);
    const previousLength = runtime.series.dataLength;
    if (!point) return { changed: false, previousLength, nextLength: previousLength, removedFromHead: 0 };
    const previousTimestamp = runtime.series.timestamps[previousLength - 1];
    if (previousLength > 0 && previousTimestamp !== undefined && Math.abs(point.timestamp - previousTimestamp) <= TIMESTAMP_EPSILON) return updateCurrentSeriesBar(runtime, input);
    if (point.mode === 'ohlc' && !runtime.data.hasOhlc()) runtime.data.upgradeToOhlc();
    const slot = runtime.data.findTimestamp(point.timestamp);
    if (!slot.exact) return insertSeriesPoint(runtime, slot.index, point);
    setSeriesPoint(runtime, slot.index, point);
    return { changed: true, previousLength, nextLength: runtime.series.dataLength, removedFromHead: 0 };
};

const replaceSeries = (runtime: ChartSeriesStorageRuntime, points: ReadonlyArray<ChartPointCandidate> | null, options: { assumeSorted?: boolean } = {}): SeriesReplaceResult => {
    const previousLength = runtime.series.dataLength;
    if (!isArray(points)) return { previousLength, nextLength: previousLength, startIndex: 0, empty: previousLength === 0 };
    const normalized: NormalizedDataPoint[] = [];
    for (const input of points) {
        const point = runtime.data.normalize(input);
        if (point) normalized.push(point);
    }
    if (options.assumeSorted !== true || !isMonotonicByTimestamp(normalized)) normalized.sort((left, right) => left.timestamp - right.timestamp);
    if (normalized.length === 0) {
        runtime.series.dataLength = 0;
        runtime.data.discardHeikin();
        runtime.series.sourceSeriesMode = 'value';
        return { previousLength, nextLength: 0, startIndex: 0, empty: true };
    }
    const containsOhlc = normalized.some((point) => point.mode === 'ohlc');
    if (containsOhlc) runtime.data.upgradeToOhlc();
    else runtime.data.downgradeToValue();
    const nextLength = Math.min(normalized.length, runtime.maxDataPoints);
    const startIndex = normalized.length - nextLength;
    const ohlc = containsOhlc ? runtime.data.ensureOhlc() : null;
    let includesHeikin = false;
    const retainedPoints = normalized.slice(startIndex);
    for (const [index, point] of retainedPoints.entries()) {
        if (point.sourceMode === 'heikin-ashi') includesHeikin = true;
        runtime.series.timestamps[index] = point.timestamp;
        runtime.series.values[index] = point.value;
        if (!ohlc) continue;
        ohlc.open[index] = point.open;
        ohlc.high[index] = point.high;
        ohlc.low[index] = point.low;
        ohlc.close[index] = point.close;
    }
    runtime.series.sourceSeriesMode = containsOhlc ? (includesHeikin ? 'heikin-ashi' : 'ohlc') : 'value';
    runtime.series.dataLength = nextLength;
    if (runtime.data.hasOhlc()) runtime.data.invalidateHeikin(0);
    else runtime.data.discardHeikin();
    return { previousLength, nextLength, startIndex, empty: false };
};

const prependSeries = (runtime: ChartSeriesStorageRuntime, inputs: ReadonlyArray<ChartPointCandidate> | null): SeriesPrependResult => {
    if (!isArray(inputs) || inputs.length === 0) return { changed: false, addedToHead: 0 };
    const normalized = inputs
        .map((input) => runtime.data.normalize(input))
        .filter((point): point is NormalizedDataPoint => point !== null)
        .sort((left, right) => left.timestamp - right.timestamp);
    if (normalized.length === 0) return { changed: false, addedToHead: 0 };
    if (runtime.series.dataLength === 0) {
        const result = replaceSeries(runtime, inputs);
        return { changed: result.nextLength > 0, addedToHead: 0 };
    }
    const firstTimestamp = runtime.series.timestamps[0];
    if (firstTimestamp === undefined) throw new Error('Non-empty chart series is missing its first timestamp.');
    const filtered = normalized.filter((point) => point.timestamp < firstTimestamp - 1e-3);
    const addedToHead = Math.min(filtered.length, runtime.maxDataPoints - runtime.series.dataLength);
    if (addedToHead <= 0) return { changed: false, addedToHead: 0 };
    const startIndex = filtered.length - addedToHead;
    runtime.series.timestamps.copyWithin(addedToHead, 0, runtime.series.dataLength);
    runtime.series.values.copyWithin(addedToHead, 0, runtime.series.dataLength);
    if (runtime.data.hasOhlc() || filtered.some((point) => point.mode === 'ohlc')) {
        if (!runtime.data.hasOhlc()) runtime.data.upgradeToOhlc();
        const ohlc = runtime.data.ensureOhlc();
        for (const values of Object.values(ohlc)) values.copyWithin(addedToHead, 0, runtime.series.dataLength);
    }
    const prependedPoints = filtered.slice(startIndex);
    for (const [index, point] of prependedPoints.entries()) {
        setSeriesPoint(runtime, index, point);
    }
    runtime.series.dataLength += addedToHead;
    runtime.data.invalidateHeikin(0);
    return { changed: true, addedToHead };
};

const normalizeDatasetValues = (candidate: DatasetValue): Float64Array | number[] | undefined => {
    if (candidate instanceof Float64Array) return candidate;
    if (!isArray(candidate)) return undefined;
    const values: number[] = [];
    for (const value of candidate) {
        if (typeof value !== 'number') return undefined;
        values.push(value);
    }
    return values;
};

const addSeriesDataset = (runtime: ChartSeriesStorageRuntime, definition: DatasetInput): void => {
    const candidateName = definition['name'];
    const name = isString(candidateName) && candidateName.trim() ? candidateName : `Dataset ${runtime.series.datasets.length + 1}`;
    const candidateValues = definition['values'];
    const values = normalizeDatasetValues(candidateValues);
    runtime.series.datasets.push({ ...definition, name, values });
};

const clearSeriesDatasets = (runtime: ChartSeriesStorageRuntime): void => {
    runtime.series.datasets = [];
};

export { addSeriesDataset, appendSeriesPoint, clearSeriesDatasets, prependSeries, replaceSeries };
