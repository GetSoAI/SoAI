/* SoAI - Charts feature data transforms actions [frontend/assets/ts/features/charts/datatransforms/actions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import { isArray, isFunction, isObject } from '@core/typeGuards.ts';
import { readRuntimeFiniteNumberOrFallbackValue } from '@core/types/numberCoercionReaders.ts';
import { reduceSeriesDensity } from '@features/charts/datatransforms/density.ts';
import type { BuildValueSeriesOptions, DataPoint } from '@features/charts/datatransforms/types.ts';

const sanitizePoints = (data: ReadonlyArray<JsonValue | DataPoint | null | undefined> | null | undefined, { assumeSorted = false }: { assumeSorted?: boolean } = {}): DataPoint[] => {
    if (!isArray(data) || data.length === 0) {
        return [];
    }

    const mapped: DataPoint[] = [];
    data.forEach((point: JsonValue | DataPoint | null | undefined): void => {
        if (!isObject(point)) {
            return;
        }
        const timestamp = readRuntimeFiniteNumberOrFallbackValue(point['timestamp'], null);
        if (timestamp === null || timestamp === undefined || !Number.isFinite(timestamp)) {
            return;
        }
        const closeValue = 'close' in point ? point['close'] : null;
        const baseValue = readRuntimeFiniteNumberOrFallbackValue(point['value'], readRuntimeFiniteNumberOrFallbackValue(closeValue, null));
        if (baseValue === null || baseValue === undefined || !Number.isFinite(baseValue)) {
            return;
        }
        const mappedPoint: DataPoint = { timestamp, value: baseValue };
        if (typeof point['mode'] === 'string') mappedPoint.mode = point['mode'];
        if (typeof point['sourceMode'] === 'string') mappedPoint.sourceMode = point['sourceMode'];
        mapped.push(mappedPoint);
    });

    if (!assumeSorted) {
        mapped.sort((firstValue: DataPoint, secondValue: DataPoint): number => firstValue.timestamp - secondValue.timestamp);
    }
    return mapped;
};

const estimateIntervalMs = (points: DataPoint[]): number | null => {
    if (!isArray(points) || points.length <= 1) {
        return null;
    }

    const deltas: number[] = [];
    for (let index = 1; index < points.length; index += 1) {
        const current = points[index];
        const previous = points[index - 1];
        if (!current || !previous) {
            continue;
        }
        const delta = current['timestamp'] - previous['timestamp'];
        if (Number.isFinite(delta) && delta > 0) {
            deltas.push(delta);
        }
    }

    if (!deltas.length) {
        return null;
    }
    deltas.sort((firstValue: number, secondValue: number): number => firstValue - secondValue);
    const median = deltas[Math.floor(deltas.length / 2)];
    if (median === undefined) {
        return null;
    }
    return Math.max(1, Math.round(median));
};

const downsampleSeries = (points: DataPoint[], limit: number): DataPoint[] => {
    return reduceSeriesDensity(points, limit);
};

const buildValueSeriesFromPairs = (timestamps: JsonValue | null | undefined, values: JsonValue | null | undefined, { valueTransform = null }: BuildValueSeriesOptions = {}): DataPoint[] => {
    const timestampList = isArray(timestamps) ? timestamps : [];
    const valueList = isArray(values) ? values : [];
    const length = Math.min(timestampList.length, valueList.length);
    const mapped: DataPoint[] = [];

    for (let index = 0; index < length; index += 1) {
        const timestamp = readRuntimeFiniteNumberOrFallbackValue(timestampList[index], null);
        const raw = readRuntimeFiniteNumberOrFallbackValue(valueList[index], null);
        if (timestamp === null || raw === null || !Number.isFinite(timestamp) || !Number.isFinite(raw)) {
            continue;
        }
        const value = isFunction(valueTransform) && valueTransform !== null ? valueTransform(raw) : raw;
        if (!Number.isFinite(value)) {
            continue;
        }
        mapped.push({ timestamp: Math.round(timestamp), value });
    }

    return sanitizePoints(mapped, { assumeSorted: true });
};

export { buildValueSeriesFromPairs, downsampleSeries, estimateIntervalMs, sanitizePoints };
