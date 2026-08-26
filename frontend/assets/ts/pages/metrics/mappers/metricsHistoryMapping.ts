/* SoAI - Metrics page history mapping [frontend/assets/ts/pages/metrics/mappers/metricsHistoryMapping.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { readRoundedIntegerAtLeastValue, readRoundedPositiveIntegerOrFallbackValue, readRoundedPositiveIntegerOrNullValue } from '@core/types/numberCoercionReaders.ts';
import { isFiniteNumber } from '@core/typeGuards.ts';
import { minutesToMs } from '@core/time/durations.ts';
import { serverEpochMs } from '@core/time/clock.ts';
import { filterCandlestickBucketsForSeries, trimCandlestickSeriesToTimeRange } from '@features/charts/public.ts';
import { METRICS_HISTORY_API_POINT_LIMIT } from '@features/metrics/public.ts';
import type { CandlestickDataPoint, MetricsHistoryPoint } from '@pages/metrics/types.ts';

export type HistoryWindow = {
    startTsMs: number;
    endTsMs: number;
    rangeMs: number;
};

const normalizeSupportedIntervals = (supportedIntervalsMs: readonly number[] | null | undefined): number[] => {
    if (!supportedIntervalsMs?.length) {
        return [];
    }
    const intervals = supportedIntervalsMs.map((value) => readRoundedPositiveIntegerOrNullValue(value)).filter((value): value is number => value !== null);
    return Array.from(new Set(intervals)).sort((firstValue, secondValue) => firstValue - secondValue);
};

const resolveSupportedInterval = (minimumIntervalMs: number, requestedIntervalMs: number, supportedIntervalsMs: readonly number[] | null | undefined): number => {
    const intervals = normalizeSupportedIntervals(supportedIntervalsMs);
    if (!intervals.length) {
        throw new Error('Metrics history requires supported intervals from backend capabilities');
    }
    const required = Math.max(requestedIntervalMs, minimumIntervalMs);
    const interval = intervals.find((intervalMs) => intervalMs >= required);
    if (!interval) {
        throw new Error(`Metrics history has no supported interval for ${required}ms`);
    }
    return interval;
};

export const resolveHistoryIntervalMs = ({ startTsMs, endTsMs, requestedIntervalMs, pointBudget, maxBuckets = METRICS_HISTORY_API_POINT_LIMIT, supportedIntervalsMs = null }: { startTsMs: number; endTsMs: number; requestedIntervalMs: number; pointBudget: number; maxBuckets?: number; supportedIntervalsMs?: readonly number[] | null }): number => {
    const requested = readRoundedPositiveIntegerOrFallbackValue(requestedIntervalMs, 1);
    const rawBudget = readRoundedPositiveIntegerOrFallbackValue(pointBudget, maxBuckets);
    const budget = Number.isFinite(rawBudget) ? Math.max(1, Math.min(rawBudget, maxBuckets)) : maxBuckets;
    const start = Math.floor(Number(startTsMs));
    const end = Math.floor(Number(endTsMs));
    if (!Number.isFinite(start) || !Number.isFinite(end) || end <= start) {
        return resolveSupportedInterval(requested, requested, supportedIntervalsMs);
    }
    const spanMs = Math.max(1, end - start);
    const minimumSafeInterval = Math.max(1, Math.ceil(spanMs / budget));
    return resolveSupportedInterval(minimumSafeInterval, requested, supportedIntervalsMs);
};

export const buildHistoryWindow = ({ beforeTimestampMs = null, intervalMs = null, expand = 1, timeRangeMinutes, maxRetentionMinutes }: { beforeTimestampMs?: number | null; intervalMs?: number | null; expand?: number; timeRangeMinutes: number; maxRetentionMinutes: number | null }): HistoryWindow | null => {
    const nowMs = Math.floor(serverEpochMs());
    const beforeProvided = isFiniteNumber(beforeTimestampMs);
    const baseReferenceMs = beforeProvided ? Math.floor(Number(beforeTimestampMs)) : nowMs;
    const interval = isFiniteNumber(intervalMs) && Number(intervalMs) > 0 ? Math.round(Number(intervalMs)) : null;
    const normalizedRangeMinutes = Number(timeRangeMinutes);
    if (!Number.isFinite(normalizedRangeMinutes) || normalizedRangeMinutes <= 0) {
        throw new TypeError('timeRangeMinutes must be a positive number');
    }
    const normalizedRetentionMinutes = Number(maxRetentionMinutes);
    const retentionMins = Number.isFinite(normalizedRetentionMinutes) && normalizedRetentionMinutes > 0 ? Math.min(normalizedRangeMinutes, normalizedRetentionMinutes) : normalizedRangeMinutes;
    const expansion = Number(expand);
    if (!Number.isFinite(expansion) || expansion <= 0) {
        throw new TypeError('expand must be a positive number');
    }
    const rangeMs = Math.max(minutesToMs(1), Math.round(minutesToMs(retentionMins) * (expansion > 1 ? expansion : 1)));
    const intervalOffset = beforeProvided && interval ? interval : 0;
    const endTsMs = Math.max(0, baseReferenceMs - intervalOffset);
    const startTsMs = Math.max(0, endTsMs - rangeMs);
    if (startTsMs >= endTsMs) {
        const adjustedEnd = Math.max(0, baseReferenceMs);
        const adjustedStart = Math.max(0, adjustedEnd - rangeMs);
        return adjustedStart < adjustedEnd ? { startTsMs: adjustedStart, endTsMs: adjustedEnd, rangeMs } : null;
    }
    return { startTsMs, endTsMs, rangeMs };
};

export const computeCandlestickPointBudget = ({ rangeMs, intervalMs, pointBudget }: { rangeMs: number; intervalMs: number; pointBudget: number }): number => {
    const interval = readRoundedIntegerAtLeastValue(intervalMs, 'interval_ms', 1);
    const range = readRoundedIntegerAtLeastValue(rangeMs, 'rangeMs', 1);
    const budget = readRoundedIntegerAtLeastValue(pointBudget, 'pointBudget', 1);
    const desired = Math.ceil(Math.max(1, Math.ceil(range / interval)) * 4);
    return Math.max(1, Math.min(budget, desired));
};

export const trimCandlestickSeries = ({
    candles,
    buckets,
    pointBudget,
    historyTrimRatio,
    timeRangeMinutes,
    intervalMs,
    force = false
}: {
    candles: CandlestickDataPoint[];
    buckets: Map<number, CandlestickDataPoint & { count: number }>;
    pointBudget: number;
    historyTrimRatio: number;
    timeRangeMinutes: number;
    intervalMs: number;
    force?: boolean;
}): {
    modified: boolean;
    candles: CandlestickDataPoint[];
    buckets: Map<number, CandlestickDataPoint & { count: number }>;
} => {
    let modified = false;
    const threshold = force ? pointBudget : Math.floor(pointBudget * historyTrimRatio);
    let currentCandles = candles;
    let currentBuckets = buckets;
    if (currentCandles.length > threshold) {
        currentCandles = currentCandles.slice(currentCandles.length - pointBudget);
        modified = true;
    }
    if (currentCandles.length === 0) {
        return { modified, candles: currentCandles, buckets: currentBuckets };
    }
    const trimmed = trimCandlestickSeriesToTimeRange({
        candles: currentCandles,
        pointBudget,
        timeRangeMs: minutesToMs(timeRangeMinutes),
        intervalMs: intervalMs,
        errorContext: 'candlestick series'
    });
    if (trimmed.modified) {
        currentCandles = trimmed.candles;
        modified = true;
        currentBuckets = filterCandlestickBucketsForSeries(currentCandles, currentBuckets);
    }
    return { modified, candles: currentCandles, buckets: currentBuckets };
};

export const trimMetricsHistory = ({ points, maxHistoryPoints, historyTrimRatio, force = false }: { points: MetricsHistoryPoint[]; maxHistoryPoints: number; historyTrimRatio: number; force?: boolean }): MetricsHistoryPoint[] => {
    const limit = maxHistoryPoints || 20000;
    const threshold = force ? limit : Math.floor(limit * historyTrimRatio);
    return points.length > threshold ? points.slice(points.length - limit) : points;
};
