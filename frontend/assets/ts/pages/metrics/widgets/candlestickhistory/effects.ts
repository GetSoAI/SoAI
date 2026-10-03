/* SoAI - Metrics page candlestick history effects [frontend/assets/ts/pages/metrics/widgets/candlestickhistory/effects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { MetricsHistoryPayload } from '@core/realtime/metricsHistoryContracts.ts';
import { readRoundedIntegerMinimumValue, readRoundedPositiveIntegerOrNullValue } from '@core/types/numberCoercionReaders.ts';
import { isArray } from '@core/typeGuards.ts';
import { filterCandlestickBucketsForSeries, resolveHistoryChartStorageCapacity, type HistoryChartOhlcModule } from '@features/charts/public.ts';
import { METRICS_HISTORY_API_POINT_LIMIT } from '@features/metrics/public.ts';
import { trimCandlestickSeries } from '@pages/metrics/mappers/metricsHistoryMapping.ts';
import type { CandlestickDataPoint, CandlestickMetadata } from '@pages/metrics/types.ts';
import { parseBackendOhlcResponse } from '@pages/metrics/widgets/candlestickhistory/mappers.ts';
import type { CandlestickHistoryContext } from '@pages/metrics/widgets/candlestickhistory/types.ts';

const applyCandlestickMetadata = (context: CandlestickHistoryContext, chartOhlc: HistoryChartOhlcModule, metadata: CandlestickMetadata): void => {
    if (!metadata || !chartOhlc) {
        return;
    }
    const monitoringInterval = readRoundedPositiveIntegerOrNullValue(metadata.loggingIntervalMs);
    if (monitoringInterval) {
        context.limits.monitoringIntervalMs = monitoringInterval;
    }
    const maxPoints = readRoundedPositiveIntegerOrNullValue(metadata.maxPoints);
    if (maxPoints) {
        const bounded = Math.min(context.limits.chartHardLimit, METRICS_HISTORY_API_POINT_LIMIT, maxPoints);
        context.limits.historyApiPointCap = bounded;
        context.limits.maxHistoryPoints = resolveHistoryChartStorageCapacity(bounded, context.limits.maxRetentionMinutes, context.limits.monitoringIntervalMs, context.limits.chartHardLimit);
        context.chart.mainChart?.settings.update({
            maxDataPoints: context.limits.maxHistoryPoints
        });
    }
    const limit = context.limits.pointBudget;
    const effectivePoints = readRoundedPositiveIntegerOrNullValue(metadata.effectivePoints);
    context.limits.currentHistoryPointBudget = effectivePoints ? Math.min(limit, effectivePoints) : limit;
};

const trimCandlestickData = (context: CandlestickHistoryContext, force = false): boolean => {
    const { modified, candles, buckets } = trimCandlestickSeries({
        candles: context.state.candlestickData,
        buckets: context.state.candlestickBuckets,
        capacity: context.limits.maxHistoryPoints,
        historyTrimRatio: context.limits.historyTrimRatio,
        force
    });
    if (modified) {
        context.state.candlestickData = candles;
        context.state.candlestickBuckets = buckets;
    }
    return modified;
};

const applyCandlestickHistory = (context: CandlestickHistoryContext, chartOhlc: HistoryChartOhlcModule, response: MetricsHistoryPayload): boolean => {
    if (!chartOhlc) {
        throw new TypeError('metrics candlestick history requires ohlc utilities');
    }
    const result = parseBackendOhlcResponse(chartOhlc, response, context.query.getMetricTransform());
    if (result.intervalMs <= 0) {
        throw new TypeError('metrics candlestick history intervalMs must be a positive number');
    }
    if (!isArray(context.state.baseCandleIntervals)) {
        throw new TypeError('baseCandleIntervals must be an array');
    }
    context.state.candlestickData = result.candles.slice(-context.limits.maxHistoryPoints);
    context.state.candlestickBuckets = filterCandlestickBucketsForSeries(context.state.candlestickData, result.candlestickBuckets);
    context.state.candlestickMetadata = result.metadata;
    applyCandlestickMetadata(context, chartOhlc, context.state.candlestickMetadata);

    const intervalMinutes = readRoundedIntegerMinimumValue(result.intervalMs / 60000, 1);
    context.state.lastResolvedCandlestickIntervalMs = result.intervalMs;
    if (!context.state.baseCandleIntervals.includes(intervalMinutes)) {
        context.state.baseCandleIntervals = [...new Set([...context.state.baseCandleIntervals, intervalMinutes])].sort((firstValue, secondValue) => firstValue - secondValue);
    }
    if (intervalMinutes === context.state.candlestickIntervalMinutes) {
        return false;
    }
    context.state.candlestickIntervalMinutes = intervalMinutes;
    return true;
};

const prependCandlestickHistory = (context: CandlestickHistoryContext, chartOhlc: HistoryChartOhlcModule, response: MetricsHistoryPayload): { prepended: CandlestickDataPoint[]; capped: boolean } => {
    const result = parseBackendOhlcResponse(chartOhlc, response, context.query.getMetricTransform());
    if (result.intervalMs !== context.state.lastResolvedCandlestickIntervalMs) {
        throw new TypeError('Metrics older history interval differs from the displayed series');
    }
    const earliestTimestamp = context.state.candlestickData[0]?.timestamp;
    if (earliestTimestamp === undefined) {
        throw new TypeError('Metrics older history requires an existing series');
    }
    const older = result.candles.filter((candle) => candle.timestamp < earliestTimestamp);
    const room = Math.max(0, context.limits.maxHistoryPoints - context.state.candlestickData.length);
    const prepended = older.slice(Math.max(0, older.length - room));
    const capped = prepended.length < older.length;
    if (!prepended.length) return { prepended, capped };
    const buckets = new Map(context.state.candlestickBuckets);
    for (const candle of prepended) {
        const bucket = result.candlestickBuckets.get(candle.timestamp);
        if (!bucket) throw new TypeError('Metrics older history candle is missing its bucket');
        buckets.set(candle.timestamp, bucket);
    }
    context.state.candlestickData = [...prepended, ...context.state.candlestickData];
    context.state.candlestickBuckets = buckets;
    return { prepended, capped };
};

export { applyCandlestickHistory, applyCandlestickMetadata, prependCandlestickHistory, trimCandlestickData };
