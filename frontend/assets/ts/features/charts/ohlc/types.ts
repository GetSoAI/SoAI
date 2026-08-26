/* SoAI - Chart OHLC public contracts [frontend/assets/ts/features/charts/ohlc/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ChartOhlcPointInput } from '@features/charts/data/chartPointTypes.ts';

interface NormalizedOhlc {
    open: number;
    high: number;
    low: number;
    close: number;
    count: number;
}

type CandlestickPoint = ChartOhlcPointInput & {
    value: number;
    mode: 'ohlc';
    sourceMode: 'ohlc' | 'heikin-ashi';
};

interface ParseOptions {
    transform?: (value: number) => number;
    intervalMs?: number;
    metricKey?: string;
    requireAggregation?: boolean;
}

interface BuildCandlestickOptions {
    maxPoints?: number;
    timeRangeMs?: number;
    intervalMs?: number | null;
}

interface ParsedOhlcMetadata {
    intervalMs: number;
    aggregation?: string;
    monitoringIntervalMs?: number;
    loggingIntervalMs?: number;
    maxPoints?: number;
    effectivePoints?: number;
    requestedPoints?: number;
    points?: number;
    component?: string;
    deviceId?: string | null;
    identifier?: string | null;
    bucketGapCount?: number;
}

interface ParsedOhlcResult {
    candles: CandlestickPoint[];
    metadata: ParsedOhlcMetadata;
    intervalMs: number;
    candlestickBuckets: Map<number, CandlestickPoint & { count: number }>;
}

interface UpdateResult {
    updated: boolean;
    appended: boolean;
}

interface BuildMissingOptions {
    maxFill?: number;
    limit?: number;
}

interface EnsureContinuousOptions {
    maxFill?: number;
    limit?: number;
}

export type { BuildCandlestickOptions, BuildMissingOptions, CandlestickPoint, EnsureContinuousOptions, NormalizedOhlc, ParseOptions, ParsedOhlcMetadata, ParsedOhlcResult, UpdateResult };
