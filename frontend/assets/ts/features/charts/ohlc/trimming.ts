/* SoAI - Shared OHLC history trimming helpers [frontend/assets/ts/features/charts/ohlc/trimming.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isFiniteNumber } from '@core/typeGuards.ts';

interface TimestampedCandlestick {
    timestamp: number;
}

const filterCandlestickBucketsForSeries = <TPoint extends TimestampedCandlestick, TBucket>(candles: readonly TPoint[], buckets: ReadonlyMap<number, TBucket>): Map<number, TBucket> => {
    const allowedTimestamps = new Set(candles.map((point) => point.timestamp));
    const filteredBuckets = new Map<number, TBucket>();
    for (const [timestamp, bucket] of buckets) {
        if (allowedTimestamps.has(timestamp)) {
            filteredBuckets.set(timestamp, bucket);
        }
    }
    return filteredBuckets;
};

const trimCandlestickSeriesToTimeRange = <TPoint extends TimestampedCandlestick>(inputArguments: { candles: readonly TPoint[]; pointBudget: number; timeRangeMs: number; intervalMs: number; errorContext: string }): { candles: TPoint[]; modified: boolean } => {
    if (inputArguments.candles.length === 0) {
        return { candles: [], modified: false };
    }
    const latestTimestamp = inputArguments.candles[inputArguments.candles.length - 1]?.timestamp;
    if (!isFiniteNumber(latestTimestamp)) {
        throw new TypeError(`${inputArguments.errorContext} must include finite timestamps`);
    }
    const toleranceMs = inputArguments.intervalMs > 0 ? Math.max(250, Math.round(inputArguments.intervalMs * 0.75)) : 0;
    const cutoff = latestTimestamp - inputArguments.timeRangeMs - toleranceMs;
    const filtered = inputArguments.candles.filter((point) => point.timestamp >= cutoff);
    const retainedCount = Math.min(inputArguments.pointBudget, inputArguments.candles.length);
    const trimmed = filtered.length > 0 ? filtered : inputArguments.candles.slice(-retainedCount);
    return { candles: trimmed, modified: trimmed.length !== inputArguments.candles.length };
};

export { filterCandlestickBucketsForSeries, trimCandlestickSeriesToTimeRange };
