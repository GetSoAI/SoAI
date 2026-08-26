/* SoAI - Charts feature data transforms effects [frontend/assets/ts/features/charts/datatransforms/effects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { clampNumber } from '@core/primitives/clampNumber.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { isArray, isObject } from '@core/typeGuards.ts';
import { readRuntimeFiniteNumberOrFallbackValue } from '@core/types/numberCoercionReaders.ts';
import { estimateIntervalMs, sanitizePoints } from '@features/charts/datatransforms/actions.ts';
import { reduceSeriesDensity } from '@features/charts/datatransforms/density.ts';
import type { BuildLineGapFillersOptions, DataPoint, OhlcPoint, ToHeikinAshiOptions, ToLineSeriesOptions } from '@features/charts/datatransforms/types.ts';

const buildLineGapFillers = (previousPoint: DataPoint | JsonValue | null | undefined, nextTimestamp: JsonValue | null | undefined, intervalMs: JsonValue | null | undefined, options: BuildLineGapFillersOptions = {}): DataPoint[] => {
    const previousTimestamp = readRuntimeFiniteNumberOrFallbackValue(isObject(previousPoint) ? previousPoint['timestamp'] : null, null);
    const previousValue = readRuntimeFiniteNumberOrFallbackValue(isObject(previousPoint) ? previousPoint['value'] : null, null);
    const targetTimestamp = readRuntimeFiniteNumberOrFallbackValue(nextTimestamp, null);
    const interval = readRuntimeFiniteNumberOrFallbackValue(intervalMs, null);

    if (previousTimestamp === null || previousValue === null || targetTimestamp === null || interval === null || !Number.isFinite(previousTimestamp) || !Number.isFinite(previousValue) || !Number.isFinite(targetTimestamp) || !Number.isFinite(interval) || targetTimestamp <= previousTimestamp) {
        return [];
    }

    const intervalRounded = Math.max(1, Math.round(interval));
    const tolerance = intervalRounded * 1.5;
    if (targetTimestamp - previousTimestamp <= tolerance) {
        return [];
    }

    const rawCount = Math.floor((targetTimestamp - previousTimestamp) / intervalRounded) - 1;
    if (rawCount <= 0) {
        return [];
    }

    const capSource = Number.isFinite(options.maxFill) ? Number(options.maxFill) : Number.isFinite(options.limit) ? Number(options.limit) : 20000;
    const maxCount = clampNumber(Math.floor(capSource), 0, 20000);
    const count = Math.min(rawCount, maxCount);
    if (count <= 0) {
        return [];
    }

    const template: DataPoint = { timestamp: previousTimestamp, value: previousValue };
    const fillers: DataPoint[] = [];
    let timestamp = previousTimestamp;

    for (let index = 0; index < count; index += 1) {
        timestamp += intervalRounded;
        if (timestamp >= targetTimestamp) {
            break;
        }
        fillers.push({ ...template, timestamp, value: previousValue });
    }
    return fillers;
};

const fillGapsInSeries = (points: DataPoint[], intervalMs: JsonValue | null | undefined, limit: JsonValue | null | undefined, rangeMs: JsonValue | null | undefined): DataPoint[] => {
    const intervalNumeric = readRuntimeFiniteNumberOrFallbackValue(intervalMs, null);
    if (intervalNumeric === null) {
        return points;
    }

    const interval = Math.max(1, Math.round(intervalNumeric));
    const limitNumeric = readRuntimeFiniteNumberOrFallbackValue(limit, null);
    const cappedLimit = limitNumeric !== null && limitNumeric > 0 ? Math.floor(limitNumeric) : null;
    const maxFill = cappedLimit ? Math.max(16, Math.min(cappedLimit * 2, 20000)) : 20000;

    const latestTimestamp = points[points.length - 1]?.['timestamp'] ?? null;
    const latestTimestampNumeric = readRuntimeFiniteNumberOrFallbackValue(latestTimestamp, null);
    const rangeNumeric = readRuntimeFiniteNumberOrFallbackValue(rangeMs, null);
    const rangeCutoff = rangeNumeric !== null && rangeNumeric > 0 && latestTimestampNumeric !== null ? latestTimestampNumeric - rangeNumeric : null;

    const result: DataPoint[] = [];
    for (let index = 0; index < points.length; index += 1) {
        const current = points[index];
        if (current && (rangeCutoff === null || current['timestamp'] >= rangeCutoff)) {
            result.push(current);
        }

        const next = points[index + 1];
        if (!next) {
            continue;
        }

        const fillers = buildLineGapFillers(current, next['timestamp'], interval, { maxFill });
        if (!fillers.length) {
            continue;
        }

        if (rangeCutoff !== null) {
            for (const filler of fillers) {
                if (filler['timestamp'] >= rangeCutoff) {
                    result.push(filler);
                }
            }
        } else {
            result.push(...fillers);
        }
    }

    if (rangeCutoff !== null) {
        return result.filter((point: DataPoint): boolean => point['timestamp'] >= rangeCutoff);
    }
    return result;
};

const toLineSeries = (data: JsonValue | null | undefined, maxPoints: JsonValue | null | undefined, options: ToLineSeriesOptions = {}): DataPoint[] => {
    const { assumeSorted = false, fillGaps = true, intervalMs: intervalOption = null, rangeMs = null, densityMode = 'shape', targetPoints = null } = options;
    const points = sanitizePoints(isArray(data) ? data : [], { assumeSorted });
    if (!points.length) {
        return [];
    }

    const maxPointsNumeric = readRuntimeFiniteNumberOrFallbackValue(maxPoints, null);
    const limit = maxPointsNumeric !== null && maxPointsNumeric > 0 ? Math.floor(maxPointsNumeric) : points.length;
    const targetPointsNumeric = readRuntimeFiniteNumberOrFallbackValue(targetPoints, null);
    const displayLimit = targetPointsNumeric !== null && targetPointsNumeric > 0 ? Math.min(limit, Math.floor(targetPointsNumeric)) : limit;
    let working = points;

    const lastPoint = points[points.length - 1];
    const rangeNumeric = readRuntimeFiniteNumberOrFallbackValue(rangeMs, null);
    if (rangeNumeric !== null && rangeNumeric > 0 && points.length > 1 && lastPoint) {
        const cutoff = lastPoint['timestamp'] - rangeNumeric;
        const filtered = points.filter((point: DataPoint): boolean => point['timestamp'] >= cutoff);
        if (filtered.length > 0) {
            working = filtered;
        }
    }

    if (!fillGaps || working.length <= 1) {
        return working.length <= displayLimit ? working : reduceSeriesDensity(working, displayLimit, densityMode);
    }

    let intervalMs: number | null = readRuntimeFiniteNumberOrFallbackValue(intervalOption, null);
    if (intervalMs === null || intervalMs === undefined || !Number.isFinite(intervalMs) || intervalMs <= 0) {
        intervalMs = estimateIntervalMs(working);
    }
    if (intervalMs === null || intervalMs === undefined || !Number.isFinite(intervalMs) || intervalMs <= 0) {
        return working.length <= displayLimit ? working : reduceSeriesDensity(working, displayLimit, densityMode);
    }

    const filled = fillGapsInSeries(working, intervalMs, limit, rangeMs);
    return filled.length <= displayLimit ? filled : reduceSeriesDensity(filled, displayLimit, densityMode);
};

const toHeikinAshiSeries = (data: JsonValue | null | undefined, { assumeSorted = false }: ToHeikinAshiOptions = {}): OhlcPoint[] => {
    if (!isArray(data) || !data.length) {
        return [];
    }

    const prepared = assumeSorted
        ? data.slice()
        : data.slice().sort((left: JsonValue | null | undefined, right: JsonValue | null | undefined): number => {
              const leftTimestamp = readRuntimeFiniteNumberOrFallbackValue(isObject(left) ? left['timestamp'] : null, 0);
              const rightTimestamp = readRuntimeFiniteNumberOrFallbackValue(isObject(right) ? right['timestamp'] : null, 0);
              return leftTimestamp - rightTimestamp;
          });

    const series: OhlcPoint[] = [];
    let previousOpen = Number.NaN;
    let previousClose = Number.NaN;

    for (const item of prepared) {
        if (!isObject(item)) {
            continue;
        }

        const timestamp = readRuntimeFiniteNumberOrFallbackValue(item['timestamp'], null);
        const open = readRuntimeFiniteNumberOrFallbackValue(item['open'], null);
        const high = readRuntimeFiniteNumberOrFallbackValue(item['high'], null);
        const low = readRuntimeFiniteNumberOrFallbackValue(item['low'], null);
        const closeValue = item['close'] ?? item['value'];
        const close = readRuntimeFiniteNumberOrFallbackValue(closeValue, null);

        if (timestamp === null || open === null || high === null || low === null || close === null) {
            continue;
        }
        if (![timestamp, open, high, low, close].every(Number.isFinite)) {
            continue;
        }

        const heikinClose = (open + high + low + close) / 4;
        const heikinOpen = Number.isFinite(previousOpen) && Number.isFinite(previousClose) ? (previousOpen + previousClose) / 2 : (open + close) / 2;
        const heikinHigh = Math.max(high, heikinOpen, heikinClose);
        const heikinLow = Math.min(low, heikinOpen, heikinClose);

        const point: OhlcPoint = {
            timestamp,
            open: heikinOpen,
            high: heikinHigh,
            low: heikinLow,
            close: heikinClose,
            value: heikinClose,
            mode: 'ohlc',
            sourceMode: 'heikin-ashi'
        };
        series.push(point);
        previousOpen = heikinOpen;
        previousClose = heikinClose;
    }

    return series;
};

export { buildLineGapFillers, toHeikinAshiSeries, toLineSeries };
