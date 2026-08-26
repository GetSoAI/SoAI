/* SoAI - Chart OHLC interaction actions [frontend/assets/ts/features/charts/ohlc/actions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { clampNumber } from '@core/primitives/clampNumber.ts';
import { isArray, isFiniteNumber } from '@core/typeGuards.ts';
import { readRuntimeFiniteNumberOrFallbackValue } from '@core/types/numberCoercionReaders.ts';
import { OHLC } from '@features/charts/ohlc/constants.ts';
import { resolveNumeric } from '@features/charts/ohlc/guards.ts';
import type { BuildMissingOptions, CandlestickPoint, EnsureContinuousOptions, UpdateResult } from '@features/charts/ohlc/types.ts';

const buildMissingCandles = (lastCandle: CandlestickPoint, targetTimestamp: number, intervalMs: number, options: BuildMissingOptions = {}): CandlestickPoint[] => {
    if (!lastCandle) {
        return [];
    }

    const lastTimestamp = readRuntimeFiniteNumberOrFallbackValue(lastCandle['timestamp'], null);
    const target = readRuntimeFiniteNumberOrFallbackValue(targetTimestamp, null);
    const resolvedInterval = readRuntimeFiniteNumberOrFallbackValue(intervalMs, null);
    const interval = resolvedInterval === null ? null : Math.max(1, Math.round(resolvedInterval));
    const base = resolveNumeric(lastCandle['close'], lastCandle['value'], lastCandle['open']);

    if (lastTimestamp === null || target === null || interval === null || base === null || target <= lastTimestamp) {
        return [];
    }
    if (target - lastTimestamp <= interval * 1.5) {
        return [];
    }

    const rawCount = Math.floor((target - lastTimestamp) / interval) - 1;
    if (rawCount <= 0) {
        return [];
    }

    const maxFillValue = options.maxFill !== undefined ? readRuntimeFiniteNumberOrFallbackValue(options.maxFill, null) : null;
    const limitValue = options.limit !== undefined ? readRuntimeFiniteNumberOrFallbackValue(options.limit, null) : null;
    const cap = maxFillValue ?? limitValue ?? 20000;
    const count = Math.min(rawCount, clampNumber(Math.floor(cap), 0, 20000));
    if (count <= 0) {
        return [];
    }

    const sourceMode = lastCandle['sourceMode'] === 'heikin-ashi' ? 'heikin-ashi' : OHLC;
    const result: CandlestickPoint[] = [];
    let timestamp = lastTimestamp;

    for (let index = 0; index < count; index += 1) {
        timestamp += interval;
        if (timestamp >= target) {
            break;
        }
        result.push({
            timestamp,
            open: base,
            high: base,
            low: base,
            close: base,
            value: base,
            mode: OHLC,
            sourceMode
        });
    }
    return result;
};

const ensureContinuousCandles = (series: CandlestickPoint[], intervalMs: number, options: EnsureContinuousOptions = {}): CandlestickPoint[] => {
    if (!isArray(series) || !series.length) {
        return [];
    }

    const intervalValue = readRuntimeFiniteNumberOrFallbackValue(intervalMs, null);
    if (intervalValue === null || intervalValue <= 0) {
        throw new TypeError('intervalMs must be a positive number');
    }
    const normalizedIntervalMs = Math.max(1, Math.round(intervalValue));

    const maxFillValue = options.maxFill !== undefined ? readRuntimeFiniteNumberOrFallbackValue(options.maxFill, null) : null;
    const limitValue = options.limit !== undefined ? readRuntimeFiniteNumberOrFallbackValue(options.limit, null) : null;
    const cap = maxFillValue ?? limitValue ?? series.length * 2;
    const maxFill = clampNumber(Math.floor(cap), 0, 20000);

    const output: CandlestickPoint[] = [];
    let previous: CandlestickPoint | null = null;

    for (const candle of series) {
        if (!candle) {
            continue;
        }
        const currentTimestamp = candle.timestamp;
        if (!isFiniteNumber(currentTimestamp)) {
            continue;
        }
        if (previous) {
            const fillers = buildMissingCandles(previous, currentTimestamp, normalizedIntervalMs, { maxFill });
            if (fillers.length) {
                output.push(...fillers);
            }
        }
        output.push(candle);
        previous = candle;
    }

    return output;
};

const updateRealtimeCandlestick = (buckets: Map<number, CandlestickPoint & { count: number }>, data: CandlestickPoint[], timestamp: number, value: number, intervalMs: number): UpdateResult => {
    if (!isFiniteNumber(timestamp) || !isFiniteNumber(value)) {
        return { updated: false, appended: false };
    }

    const intervalValue = readRuntimeFiniteNumberOrFallbackValue(intervalMs, null);
    if (intervalValue === null || intervalValue <= 0) {
        throw new TypeError('intervalMs must be a positive number');
    }
    const normalizedIntervalMs = Math.max(1, Math.round(intervalValue));
    const bucketTimestamp = Math.floor(timestamp / normalizedIntervalMs) * normalizedIntervalMs;

    const last = data.length ? data[data.length - 1] : null;
    if (last && last['timestamp'] && bucketTimestamp > last['timestamp']) {
        const cap = Math.min(20000, Math.max((data.length || 1) * 2, 120));
        const fillers = buildMissingCandles(last, bucketTimestamp, normalizedIntervalMs, { maxFill: cap });
        for (const filler of fillers) {
            buckets.set(filler['timestamp'], { ...filler, count: 0 });
            data.push(filler);
        }
    }

    const bucket = buckets.get(bucketTimestamp);
    if (bucket) {
        bucket['high'] = Math.max(bucket['high'], value);
        bucket['low'] = Math.min(bucket['low'], value);
        bucket['close'] = value;
        bucket['value'] = value;
        bucket['count'] = (bucket['count'] || 0) + 1;

        const index = data.findIndex((candle: CandlestickPoint): boolean => candle['timestamp'] === bucketTimestamp);
        if (index !== -1 && data[index]) {
            const item = data[index];
            if (item) {
                Object.assign(item, {
                    high: bucket['high'],
                    low: bucket['low'],
                    close: bucket['close'],
                    value: bucket['value'],
                    sourceMode: OHLC
                });
            }
        }
        return { updated: true, appended: false };
    }

    const candle: CandlestickPoint = {
        timestamp: bucketTimestamp,
        open: value,
        high: value,
        low: value,
        close: value,
        value,
        mode: OHLC,
        sourceMode: OHLC
    };

    buckets.set(bucketTimestamp, { ...candle, count: 1 });

    const lastItem = data.length ? data[data.length - 1] : null;
    const lastTimestamp = lastItem ? lastItem['timestamp'] : null;
    if (lastTimestamp === null || bucketTimestamp >= lastTimestamp) {
        data.push(candle);
    } else {
        let index = data.findIndex((entry: CandlestickPoint): boolean => entry['timestamp'] > bucketTimestamp);
        if (index === -1) {
            index = data.length;
        }
        data.splice(index, 0, candle);
    }

    return { updated: true, appended: true };
};

export { buildMissingCandles, ensureContinuousCandles, updateRealtimeCandlestick };
