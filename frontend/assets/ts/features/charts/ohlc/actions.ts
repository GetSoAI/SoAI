/* SoAI - Chart OHLC interaction actions [frontend/assets/ts/features/charts/ohlc/actions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isFiniteNumber } from '@core/typeGuards.ts';
import { readRuntimeFiniteNumberOrFallbackValue } from '@core/types/numberCoercionReaders.ts';
import { OHLC } from '@features/charts/ohlc/constants.ts';
import type { CandlestickPoint, UpdateResult } from '@features/charts/ohlc/types.ts';

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

    const last = data[data.length - 1];
    if (last && bucketTimestamp < last.timestamp) return { updated: false, appended: false };

    const bucket = buckets.get(bucketTimestamp);
    if (Boolean(bucket) !== Boolean(last && last.timestamp === bucketTimestamp)) {
        throw new TypeError('Realtime candlestick bucket and series are inconsistent');
    }
    if (bucket) {
        bucket['high'] = Math.max(bucket['high'], value);
        bucket['low'] = Math.min(bucket['low'], value);
        bucket['close'] = value;
        bucket['value'] = value;
        bucket['count'] = (bucket['count'] || 0) + 1;

        if (!last) throw new TypeError('Realtime candlestick requires a last series entry');
        Object.assign(last, {
            high: bucket['high'],
            low: bucket['low'],
            close: bucket['close'],
            value: bucket['value'],
            sourceMode: OHLC
        });
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

    data.push(candle);

    return { updated: true, appended: true };
};

export { updateRealtimeCandlestick };
