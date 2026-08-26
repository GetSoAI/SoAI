/* SoAI - Metrics page widgets candlestick history mapping [frontend/assets/ts/pages/metrics/widgets/candlestickhistory/mappers.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { MetricsHistoryPayload } from '@core/realtime/metricsHistoryContracts.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { readRuntimeFiniteNumberOrFallbackValue } from '@core/types/numberCoercionReaders.ts';
import { isFiniteNumber, isObject } from '@core/typeGuards.ts';
import type { HistoryChartOhlcModule } from '@features/charts/public.ts';
import type { CandlestickMetadata } from '@pages/metrics/types.ts';
import { isOhlcParserHost } from '@pages/metrics/widgets/candlestickhistory/guards.ts';
import type { CandlestickResult } from '@pages/metrics/widgets/candlestickhistory/types.ts';

const parseCandlestickMetadata = <T>(value: T | JsonValue | null | undefined, intervalMs: number): CandlestickMetadata => {
    if (!isObject(value)) {
        throw new TypeError('candlestick metadata must be an object');
    }
    return {
        intervalMs: intervalMs,
        loggingIntervalMs: 'loggingIntervalMs' in value ? readRuntimeFiniteNumberOrFallbackValue(value['loggingIntervalMs'], undefined) : undefined,
        maxPoints: 'maxPoints' in value ? readRuntimeFiniteNumberOrFallbackValue(value['maxPoints'], undefined) : undefined,
        effectivePoints: 'effectivePoints' in value ? readRuntimeFiniteNumberOrFallbackValue(value['effectivePoints'], undefined) : undefined,
        requestedPoints: 'requestedPoints' in value ? readRuntimeFiniteNumberOrFallbackValue(value['requestedPoints'], undefined) : undefined,
        points: 'points' in value ? readRuntimeFiniteNumberOrFallbackValue(value['points'], undefined) : undefined
    };
};

const parseBackendOhlcResponse = (chartOhlc: HistoryChartOhlcModule, response: MetricsHistoryPayload, transform: (value: number) => number): CandlestickResult => {
    if (!isOhlcParserHost(chartOhlc)) {
        throw new TypeError('ohlc parser host is unavailable');
    }
    const result = chartOhlc.parseBackendOhlcResponse(response, { transform, requireAggregation: false });
    if (!isObject(result)) {
        throw new TypeError('ohlc parser returned invalid response');
    }
    const intervalMs = readRuntimeFiniteNumberOrFallbackValue(result.intervalMs, Number.NaN);
    if (!isFiniteNumber(intervalMs) || intervalMs <= 0) {
        throw new TypeError('ohlc parser intervalMs must be a positive number');
    }
    return {
        candles: result.candles,
        candlestickBuckets: result.candlestickBuckets,
        metadata: parseCandlestickMetadata(result.metadata, intervalMs),
        intervalMs
    };
};

export { parseBackendOhlcResponse };
