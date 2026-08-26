/* SoAI - Metrics page candlestick history effects [frontend/assets/ts/pages/metrics/widgets/candlestickhistory/effects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { decodeMetricsHistoryPayload } from '@core/realtime/metricsHistoryContracts.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { readRoundedIntegerMinimumValue, readRoundedPositiveIntegerOrNullValue } from '@core/types/numberCoercionReaders.ts';
import { isArray, isObject } from '@core/typeGuards.ts';
import { HISTORY_CHART_MIN_POINTS, type HistoryChartOhlcModule } from '@features/charts/public.ts';
import { METRICS_HISTORY_API_POINT_LIMIT } from '@features/metrics/public.ts';
import { trimCandlestickSeries } from '@pages/metrics/mappers/metricsHistoryMapping.ts';
import type { CandlestickMetadata } from '@pages/metrics/types.ts';
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
        context.limits.maxHistoryPoints = Math.min(context.limits.chartHardLimit, Math.max(HISTORY_CHART_MIN_POINTS, bounded));
        context.chart.mainChart?.settings.update({
            maxDataPoints: Math.min(context.limits.maxHistoryPoints, context.limits.historyApiPointCap)
        });
    }
    const limit = context.limits.pointBudget;
    const effectivePoints = readRoundedPositiveIntegerOrNullValue(metadata.effectivePoints);
    context.limits.currentHistoryPointBudget = effectivePoints ? Math.min(limit, effectivePoints) : limit;
};

const trimCandlestickData = (context: CandlestickHistoryContext, force = false): boolean => {
    const intervalMs = context.query.getEffectiveCandlestickIntervalMs();
    const { modified, candles, buckets } = trimCandlestickSeries({
        candles: context.state.candlestickData,
        buckets: context.state.candlestickBuckets,
        pointBudget: context.limits.pointBudget,
        historyTrimRatio: context.limits.historyTrimRatio,
        timeRangeMinutes: context.limits.timeRange,
        intervalMs,
        force
    });
    if (modified) {
        context.state.candlestickData = candles;
        context.state.candlestickBuckets = buckets;
    }
    return modified;
};

const applyCandlestickHistory = (context: CandlestickHistoryContext, chartOhlc: HistoryChartOhlcModule, response: JsonValue, { resetView = false }: { resetView?: boolean } = {}): void => {
    if (!isObject(response)) {
        throw new TypeError('metrics candlestick history response must be an object');
    }
    if (!chartOhlc) {
        throw new TypeError('metrics candlestick history requires ohlc utilities');
    }
    context.state.candlestickHistoryExhausted = false;
    const result = parseBackendOhlcResponse(chartOhlc, decodeMetricsHistoryPayload(response), context.query.getMetricTransform());
    if (result.intervalMs <= 0) {
        throw new TypeError('metrics candlestick history intervalMs must be a positive number');
    }
    context.state.candlestickData = result.candles.slice(0, context.limits.chartHardLimit);
    context.state.candlestickBuckets = result.candlestickBuckets;
    context.state.candlestickMetadata = result.metadata;
    applyCandlestickMetadata(context, chartOhlc, context.state.candlestickMetadata);

    const intervalMinutes = readRoundedIntegerMinimumValue(result.intervalMs / 60000, 1);
    context.state.lastResolvedCandlestickIntervalMs = result.intervalMs;
    if (!isArray(context.state.baseCandleIntervals)) {
        throw new TypeError('baseCandleIntervals must be an array');
    }
    if (!context.state.baseCandleIntervals.includes(intervalMinutes)) {
        context.state.baseCandleIntervals = [...new Set([...context.state.baseCandleIntervals, intervalMinutes])].sort((firstValue, secondValue) => firstValue - secondValue);
    }
    if (intervalMinutes !== context.state.candlestickIntervalMinutes) {
        context.state.candlestickIntervalMinutes = intervalMinutes;
        terminateHandledPromise(context.query.syncChartControls({ range: false, candles: true }));
    }
    const trimmed = trimCandlestickData(context, true);
    if (context.query.isCandlestickActive()) {
        context.query.updateMainChart({ resetView: resetView || trimmed });
    }
};

export { applyCandlestickHistory, applyCandlestickMetadata, trimCandlestickData };
