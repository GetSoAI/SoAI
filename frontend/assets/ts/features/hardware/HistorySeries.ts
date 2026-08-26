/* SoAI - Hardware feature history series [frontend/assets/ts/features/hardware/HistorySeries.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { HardwareHistoryResponse } from '@core/api/contracts/hardwareContracts.ts';
import { isFiniteNumber, isNullOrUndefined, isString } from '@core/typeGuards.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';

interface HistoryValueParsers {
    toTimestampMs: (value: JsonValue) => number | null;
    resolveNumeric: (...values: JsonValue[]) => number | null;
}

interface SeriesPoint {
    timestamp: number;
    value: number;
}

interface HistorySeriesResult {
    series: SeriesPoint[];
    metadata: {
        aggregation: string;
        intervalMs: number;
        [key: string]: JsonValue | undefined;
    };
}

interface BuildOptions {
    metricKey?: string;
    parsers?: HistoryValueParsers;
}

const buildHardwareValueSeriesFromHistoryPayload = (payload: HardwareHistoryResponse, { metricKey, parsers }: BuildOptions = {}): HistorySeriesResult | null => {
    if (!metricKey) throw new Error('Hardware history metricKey is required');
    if (!parsers) throw new Error('Hardware history chart parsers are required');

    const meta = payload.metadata;
    const timestamps = payload.timestampsMs;
    const rows = payload.data;

    const primaryKey = isString(metricKey) ? metricKey : null;

    const series: SeriesPoint[] = [];
    for (let index = 0; index < timestamps.length; index += 1) {
        const timestamp = timestamps[index];
        if (timestamp === undefined) continue;
        const ts = parsers.toTimestampMs(timestamp);
        if (!isFiniteNumber(ts)) continue;
        const valueSource = rows[index];
        if (!valueSource) continue;
        const value = primaryKey ? parsers.resolveNumeric(valueSource[primaryKey] ?? null) : null;
        if (isNullOrUndefined(value)) continue;
        series.push({ timestamp: ts, value: value });
    }

    if (!series.length) return null;

    series.sort((firstValue, secondValue) => firstValue.timestamp - secondValue.timestamp);

    const aggregationValue = meta.aggregation;
    if (!isString(aggregationValue) || !aggregationValue.trim()) {
        throw new TypeError('Hardware history metadata.aggregation must be a non-empty string');
    }
    const aggregation = aggregationValue.trim().toLowerCase();
    const intervalCandidate = parsers.resolveNumeric(meta.intervalMs);
    if (!isFiniteNumber(intervalCandidate) || intervalCandidate <= 0) {
        throw new TypeError('Hardware history metadata.intervalMs must be a positive number');
    }
    const intervalMs = Math.max(1, Math.round(intervalCandidate));
    const metadata: HistorySeriesResult['metadata'] = { aggregation, intervalMs };
    Object.entries(meta).forEach(([key, value]) => {
        if (value !== undefined) metadata[key] = value;
    });
    metadata.aggregation = aggregation;
    metadata.intervalMs = intervalMs;

    return {
        series,
        metadata
    };
};

export { buildHardwareValueSeriesFromHistoryPayload };
export type { HistoryValueParsers, SeriesPoint, HistorySeriesResult, BuildOptions };
