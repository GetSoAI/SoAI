/* SoAI - Shared OHLC history trimming helpers [frontend/assets/ts/features/charts/ohlc/trimming.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

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

export { filterCandlestickBucketsForSeries };
