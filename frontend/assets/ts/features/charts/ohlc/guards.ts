/* SoAI - Chart OHLC payload validation [frontend/assets/ts/features/charts/ohlc/guards.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import { isArray, isFiniteNumber, isNullOrUndefined, isObject, isString } from '@core/typeGuards.ts';
import { EPOCH_MS_DETECTION_FLOOR } from '@core/time/epochMs.ts';
import { readRuntimeFiniteNumberOrFallbackValue } from '@core/types/numberCoercionReaders.ts';
import { OHLC } from '@features/charts/ohlc/constants.ts';
import type { CandlestickPoint, NormalizedOhlc } from '@features/charts/ohlc/types.ts';

const resolveNumeric = (...values: (JsonValue | null | undefined)[]): number | null => {
    for (const value of values) {
        if (value == null) {
            continue;
        }
        const numeric = readRuntimeFiniteNumberOrFallbackValue(value, null);
        if (numeric !== null) {
            return numeric;
        }
    }
    return null;
};

const toTimestampMs = (value: JsonValue | null | undefined): number | null => {
    const numeric = readRuntimeFiniteNumberOrFallbackValue(value, null);
    if (numeric === null) {
        return null;
    }
    const rounded = Math.round(numeric);
    if (!Number.isFinite(rounded) || rounded < 0) {
        return null;
    }
    if (0 < rounded && rounded < EPOCH_MS_DETECTION_FLOOR) {
        return null;
    }
    return rounded;
};

const normalizeOhlcRecord = (record: JsonValue | null | undefined, transform: (value: number) => number = (value: number): number => value): NormalizedOhlc | null => {
    if (!isObject(record)) {
        return null;
    }

    const normalizeField = (value: JsonValue | null | undefined): number | null => {
        const numeric = readRuntimeFiniteNumberOrFallbackValue(value, null);
        return numeric === null ? null : transform(numeric);
    };

    const open = normalizeField(record['open'] ?? record['value'] ?? record['avg'] ?? record['close']);
    const close = normalizeField(record['close'] ?? record['value'] ?? record['avg'] ?? record['open']);
    const high = normalizeField(record['high'] ?? record['max'] ?? close ?? open);
    const low = normalizeField(record['low'] ?? record['min'] ?? close ?? open);

    if (open === null && close === null) {
        return null;
    }

    return {
        open: open ?? close ?? 0,
        high: high ?? open ?? close ?? 0,
        low: low ?? open ?? close ?? 0,
        close: close ?? open ?? 0,
        count: Number(record['count']) || 0
    };
};

type OhlcInputSeries = ReadonlyArray<JsonValue | CandlestickPoint | null | undefined>;

const isPreNormalizedOhlcSeries = (series: OhlcInputSeries | null | undefined): series is CandlestickPoint[] => {
    if (!isArray(series) || !series.length) {
        return false;
    }

    const length = Math.min(series.length, 6);
    for (let index = 0; index < length; index += 1) {
        const entry = series[index];
        if (!entry || !isObject(entry)) {
            return false;
        }

        if (entry['mode'] !== OHLC) {
            return false;
        }
        if ([entry['timestamp'], entry['open'], entry['high'], entry['low'], entry['close']].every(isFiniteNumber) === false) {
            return false;
        }
        const value = entry['value'];
        if (!isNullOrUndefined(value) && !isFiniteNumber(value)) {
            return false;
        }
    }
    return true;
};

const isSortedByTimestamp = (series: OhlcInputSeries | null | undefined): boolean => {
    if (!isArray(series) || series.length <= 1) {
        return true;
    }

    const first = series[0];
    if (!first || !isObject(first)) {
        return false;
    }

    const firstTimestamp = readRuntimeFiniteNumberOrFallbackValue(first['timestamp'], null);
    if (firstTimestamp === null) {
        return false;
    }

    let previousTimestamp = firstTimestamp;
    for (let index = 1; index < series.length; index += 1) {
        const item = series[index];
        if (!item || !isObject(item)) {
            return false;
        }
        const timestamp = readRuntimeFiniteNumberOrFallbackValue(item['timestamp'], null);
        if (timestamp === null || timestamp < previousTimestamp) {
            return false;
        }
        previousTimestamp = timestamp;
    }
    return true;
};

const lowerBoundTimestamp = (series: CandlestickPoint[], timestamp: number): number => {
    let low = 0;
    let high = series.length;
    while (low < high) {
        const middle = (low + high) >>> 1;
        const item = series[middle];
        const value = item ? +item['timestamp'] : Number.NaN;
        if (!isFiniteNumber(value) || value < timestamp) {
            low = middle + 1;
        } else {
            high = middle;
        }
    }
    return low;
};

const normalizeCandlestickInput = (data: OhlcInputSeries | null | undefined): CandlestickPoint[] => {
    if (!isArray(data) || !data.length) {
        return [];
    }

    const normalized: CandlestickPoint[] = [];
    for (const candle of data) {
        if (!candle || !isObject(candle)) {
            continue;
        }

        const timestamp = toTimestampMs(candle['timestamp']);
        const open = readRuntimeFiniteNumberOrFallbackValue(candle['open'], null);
        const high = readRuntimeFiniteNumberOrFallbackValue(candle['high'], null);
        const low = readRuntimeFiniteNumberOrFallbackValue(candle['low'], null);
        const close = readRuntimeFiniteNumberOrFallbackValue(candle['close'], null);

        if (timestamp === null || open === null || high === null || low === null || close === null) {
            continue;
        }

        const candleValue = candle['value'];
        const rawValue = isNullOrUndefined(candleValue) ? close : candleValue;
        const value = readRuntimeFiniteNumberOrFallbackValue(rawValue, close);
        const sourceModeValue = candle['sourceMode'];
        const sourceMode = isString(sourceModeValue) ? String(sourceModeValue).trim().toLowerCase() : null;

        normalized.push({
            timestamp,
            open,
            high,
            low,
            close,
            value,
            mode: OHLC,
            sourceMode: sourceMode === 'heikin-ashi' ? sourceMode : OHLC
        });
    }

    if (normalized.length > 1) {
        normalized.sort((left: CandlestickPoint, right: CandlestickPoint): number => left.timestamp - right.timestamp);
    }
    return normalized;
};

export { isPreNormalizedOhlcSeries, isSortedByTimestamp, lowerBoundTimestamp, normalizeCandlestickInput, normalizeOhlcRecord, resolveNumeric, toTimestampMs };
