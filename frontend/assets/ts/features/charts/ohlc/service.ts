/* SoAI - Chart OHLC processing service [frontend/assets/ts/features/charts/ohlc/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { formatPercentFromFraction } from '@core/primitives/percent.ts';
import type { HardwareHistoryResponse } from '@core/api/contracts/hardwareContracts.ts';
import type { MetricsHistoryPayload } from '@core/realtime/metricsHistoryContracts.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { isArray, isFiniteNumber, isObject } from '@core/typeGuards.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { readRuntimeFiniteNumberOrFallbackValue } from '@core/types/numberCoercionReaders.ts';
import { OHLC, logDebug, logError } from '@features/charts/ohlc/constants.ts';
import { ensureContinuousCandles } from '@features/charts/ohlc/actions.ts';
import { isPreNormalizedOhlcSeries, isSortedByTimestamp, lowerBoundTimestamp, normalizeCandlestickInput, normalizeOhlcRecord, toTimestampMs } from '@features/charts/ohlc/guards.ts';
import type { BuildCandlestickOptions, CandlestickPoint, ParseOptions, ParsedOhlcMetadata, ParsedOhlcResult } from '@features/charts/ohlc/types.ts';

const decodeOhlcMetadata = (metadata: HardwareHistoryResponse['metadata'] | MetricsHistoryPayload['metadata'], intervalMs: number, aggregation: string): ParsedOhlcMetadata => {
    const parsed: ParsedOhlcMetadata = { intervalMs };
    if (aggregation) parsed.aggregation = aggregation;
    const monitoringIntervalMs = readRuntimeFiniteNumberOrFallbackValue('monitoringIntervalMs' in metadata ? metadata.monitoringIntervalMs : null, null);
    const loggingIntervalMs = readRuntimeFiniteNumberOrFallbackValue('loggingIntervalMs' in metadata ? metadata.loggingIntervalMs : null, null);
    const maxPoints = readRuntimeFiniteNumberOrFallbackValue(metadata.maxPoints, null);
    const effectivePoints = readRuntimeFiniteNumberOrFallbackValue(metadata.effectivePoints, null);
    const requestedPoints = readRuntimeFiniteNumberOrFallbackValue(metadata.requestedPoints, null);
    const points = readRuntimeFiniteNumberOrFallbackValue(metadata.points, null);
    const bucketGapCount = readRuntimeFiniteNumberOrFallbackValue(metadata.bucketGapCount, null);
    if (monitoringIntervalMs !== null) parsed.monitoringIntervalMs = monitoringIntervalMs;
    if (loggingIntervalMs !== null) parsed.loggingIntervalMs = loggingIntervalMs;
    if (maxPoints !== null) parsed.maxPoints = maxPoints;
    if (effectivePoints !== null) parsed.effectivePoints = effectivePoints;
    if (requestedPoints !== null) parsed.requestedPoints = requestedPoints;
    if (points !== null) parsed.points = points;
    if (bucketGapCount !== null) parsed.bucketGapCount = bucketGapCount;
    const component = 'component' in metadata ? metadata.component : undefined;
    const deviceId = 'deviceId' in metadata ? metadata.deviceId : undefined;
    const identifier = 'identifier' in metadata ? metadata.identifier : undefined;
    if (typeof component === 'string') parsed.component = component;
    if (typeof deviceId === 'string' || deviceId === null) parsed.deviceId = deviceId;
    if (typeof identifier === 'string' || identifier === null) parsed.identifier = identifier;
    return parsed;
};

const parseBackendOhlcResponse = (payload: HardwareHistoryResponse | MetricsHistoryPayload, options: ParseOptions = {}): ParsedOhlcResult | null => {
    try {
        if (!isObject(payload)) {
            throw new TypeError('parseBackendOhlcResponse payload must be an object');
        }

        const transform = options.transform ?? ((value: number): number => value);
        const requireAggregation = options.requireAggregation !== false;
        const metadata = payload.metadata;
        const aggregation = payload.aggregation || metadata.aggregation;
        if (requireAggregation && aggregation !== OHLC) {
            throw new TypeError(`parseBackendOhlcResponse expected aggregation="${OHLC}"`);
        }

        const timestamps = payload.timestampsMs;
        const resolvedInterval = readRuntimeFiniteNumberOrFallbackValue(payload.intervalMs ?? metadata.intervalMs, null);
        if (resolvedInterval === null || resolvedInterval <= 0) {
            throw new TypeError('parseBackendOhlcResponse requires intervalMs');
        }
        const intervalMs = Math.max(1, Math.round(resolvedInterval));
        const parsedMetadata = decodeOhlcMetadata(metadata, intervalMs, aggregation);
        if (!timestamps.length) {
            return {
                candles: [],
                metadata: parsedMetadata,
                intervalMs,
                candlestickBuckets: new Map<number, CandlestickPoint & { count: number }>()
            };
        }

        let ohlcRows: ReadonlyArray<JsonValue | null | undefined>;
        const explicitOhlcRows = 'ohlc' in payload ? payload.ohlc : null;
        if (isArray(explicitOhlcRows)) {
            ohlcRows = explicitOhlcRows;
        } else {
            const metricKey = options.metricKey?.trim() ?? '';
            if (!metricKey) {
                throw new TypeError('parseBackendOhlcResponse requires options.metricKey when payload.ohlc is absent');
            }
            const dataRows = 'data' in payload ? payload.data : [];
            if (dataRows.length !== timestamps.length) {
                throw new TypeError(`parseBackendOhlcResponse data/timestamps length mismatch (${dataRows.length} vs ${timestamps.length})`);
            }
            ohlcRows = dataRows.map((row): JsonValue | null | undefined => {
                if (!isObject(row)) {
                    throw new TypeError('parseBackendOhlcResponse data row must be an object');
                }
                return row[metricKey];
            });
        }

        if (!ohlcRows.length) {
            throw new TypeError('parseBackendOhlcResponse requires non-empty OHLC rows when timestamps are present');
        }
        if (ohlcRows.length !== timestamps.length) {
            throw new TypeError(`parseBackendOhlcResponse ohlc/timestamps length mismatch (${ohlcRows.length} vs ${timestamps.length})`);
        }
        const rowCount = timestamps.length;

        const candles: CandlestickPoint[] = [];
        const buckets: Map<number, CandlestickPoint & { count: number }> = new Map();
        let validCount = 0;
        let invalidCount = 0;

        for (let index = 0; index < rowCount; index += 1) {
            const timestampMs = toTimestampMs(timestamps[index]);
            if (timestampMs === null) {
                throw new TypeError('parseBackendOhlcResponse requires epoch millisecond timestamps');
            }

            const normalized = normalizeOhlcRecord(ohlcRows[index], transform);
            if (!normalized) {
                invalidCount += 1;
                continue;
            }

            const candle: CandlestickPoint = {
                timestamp: timestampMs,
                open: normalized.open,
                high: normalized.high,
                low: normalized.low,
                close: normalized.close,
                value: normalized.close,
                mode: OHLC,
                sourceMode: OHLC
            };
            candles.push(candle);
            buckets.set(timestampMs, { ...candle, count: normalized.count });
            validCount += 1;
        }

        if (!validCount) {
            logDebug(`parseBackendOhlcResponse: No valid candles created from ${invalidCount} records. This may indicate insufficient data for the requested time range.`);
        }

        if (invalidCount > 0) {
            const ratio = formatPercentFromFraction(invalidCount / (validCount + invalidCount));
            logDebug(`parseBackendOhlcResponse: Created ${validCount} valid candles, skipped ${invalidCount} (${ratio} sparse data)`);
        }

        const sorted = candles.slice().sort((left: CandlestickPoint, right: CandlestickPoint): number => left.timestamp - right.timestamp);
        const continuityLimit = Math.min(20000, Math.max(sorted.length * 2, 120));
        const finalCandles = ensureContinuousCandles(sorted, intervalMs, { maxFill: continuityLimit });

        for (const candle of finalCandles) {
            if (!buckets.has(candle.timestamp)) {
                buckets.set(candle.timestamp, { ...candle, count: 0 });
            }
        }

        logDebug(`parseBackendOhlcResponse: Parsed ${validCount} candles, intervalMs=${intervalMs}`);
        return {
            candles: finalCandles,
            metadata: parsedMetadata,
            intervalMs,
            candlestickBuckets: buckets
        };
    } catch (error) {
        const runtimeError = ensureError(error);
        logError('parseBackendOhlcResponse: Fatal error during OHLC parsing', runtimeError);
        throw new Error(`OHLC parsing failed: ${runtimeError.message}`);
    }
};

const buildCandlestickSeries = (data: JsonValue | null | undefined, options: BuildCandlestickOptions = {}): CandlestickPoint[] => {
    if (!isArray(data) || !data.length) {
        return [];
    }

    const maxPoints = options.maxPoints ?? Number.POSITIVE_INFINITY;
    const timeRangeMs = options.timeRangeMs ?? Number.POSITIVE_INFINITY;
    const intervalMs = options.intervalMs;
    if (!isFiniteNumber(intervalMs) || intervalMs === null || intervalMs <= 0) {
        throw new TypeError('buildCandlestickSeries requires a positive intervalMs');
    }

    const hardLimit = isFiniteNumber(maxPoints) && maxPoints > 0 ? Math.floor(maxPoints) : null;

    const preNormalized = isPreNormalizedOhlcSeries(data);
    const baseSeries = preNormalized ? data : normalizeCandlestickInput(data);
    if (!baseSeries.length) {
        return [];
    }

    const sorted = isSortedByTimestamp(baseSeries) ? baseSeries.slice() : baseSeries.slice().sort((left: CandlestickPoint, right: CandlestickPoint): number => left.timestamp - right.timestamp);

    const lastElement = sorted[sorted.length - 1];
    const lastTimestamp = lastElement ? +lastElement.timestamp : null;

    let filtered: CandlestickPoint[] = sorted;
    if (isFiniteNumber(timeRangeMs) && timeRangeMs > 0 && isFiniteNumber(lastTimestamp) && lastTimestamp !== null) {
        const tolerance = Math.max(250, Math.round(intervalMs * 0.75));
        const cutoff = lastTimestamp - timeRangeMs - tolerance;
        if (isFiniteNumber(cutoff)) {
            filtered = sorted.slice(lowerBoundTimestamp(sorted, cutoff));
        }
    }

    if (hardLimit && filtered.length > hardLimit) {
        filtered = filtered.slice(-hardLimit);
    }
    if (!filtered.length) {
        return [];
    }

    const continuityLimit = Math.min(20000, Math.max((hardLimit || filtered.length) * 2, filtered.length * 2, 120));
    const finalSeries = ensureContinuousCandles(filtered, intervalMs, { maxFill: continuityLimit });

    return hardLimit && finalSeries.length > hardLimit ? finalSeries.slice(-hardLimit) : finalSeries;
};

export { buildCandlestickSeries, parseBackendOhlcResponse };
