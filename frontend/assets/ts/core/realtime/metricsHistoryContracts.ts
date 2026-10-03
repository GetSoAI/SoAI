/* SoAI - Frontend realtime metrics history V1 contracts [frontend/assets/ts/core/realtime/metricsHistoryContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { decodeOptionalHistoryAvailability, type HistoryAvailability } from '@core/realtime/historyAvailabilityContracts.ts';
import { hasOwn } from '@core/typeGuards.ts';
import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';
import { readRequiredFiniteNumberValue } from '@core/types/payloadNumberReaders.ts';
import { requireRecord } from '@core/types/payloadRecordReaders.ts';
import { readRequiredBooleanValue, readRequiredTrimmedStringValue } from '@core/types/payloadValueReaders.ts';

interface MetricsHistoryMetadata {
    aggregation: string;
    intervalMs: number;
    requestedIntervalMs: number | null;
    intervalSource: string;
    startTsMs: number;
    requestedStartTsMs: number;
    endTsMs: number;
    requestedEndTsMs: number;
    alignedStartTsMs: number;
    alignedEndTsMs: number;
    durationMs: number;
    requestedDurationMs: number;
    points: number;
    requestedPoints: number;
    effectivePoints: number;
    maxPoints: number;
    bucketCount: number;
    bucketGapCount: number;
    loggingIntervalMs: number;
    supportsOhlc: boolean;
    retentionApplied: boolean;
    retentionStartTsMs: number | null;
    supportedIntervalsMs: number[];
    metricKey: string;
    availability: HistoryAvailability | null;
}

interface MetricsHistoryPayload {
    aggregation: string;
    intervalMs: number;
    timestampsMs: number[];
    values: (number | null)[];
    sampleCounts: number[] | null;
    ohlc: (JsonObject | null)[];
    metadata: MetricsHistoryMetadata;
}

const requiredNumber = (record: JsonObject, key: string, label: string): number => readRequiredFiniteNumberValue(record[key], `${label}.${key}`);

const nullableNumber = (record: JsonObject, key: string, label: string): number | null => {
    const value = record[key];
    return value === null ? null : readRequiredFiniteNumberValue(value, `${label}.${key}`);
};

const numberArray = (value: JsonValue | undefined, label: string): number[] => {
    if (!Array.isArray(value)) throw new TypeError(`${label} must be an array`);
    return value.map((entry, index) => readRequiredFiniteNumberValue(entry, `${label}[${String(index)}]`));
};

const nullableNumberArray = (value: JsonValue | undefined, label: string): (number | null)[] => {
    if (!Array.isArray(value)) throw new TypeError(`${label} must be an array`);
    return value.map((entry, index) => (entry === null ? null : readRequiredFiniteNumberValue(entry, `${label}[${String(index)}]`)));
};

const nullableObjectArray = (value: JsonValue | undefined, label: string): (JsonObject | null)[] => {
    if (!Array.isArray(value)) throw new TypeError(`${label} must be an array`);
    return value.map((entry, index) => (entry === null ? null : requireRecord(entry, `${label}[${String(index)}]`)));
};

const decodeMetricsHistoryMetadata = (value: JsonValue | undefined): MetricsHistoryMetadata => {
    const record = requireRecord(value, 'Metrics history.metadata');
    if (hasOwn(record, 'intervalMs') || hasOwn(record, 'metricKey')) throw new TypeError('Metrics history.metadata must use canonical V1 wire fields');
    return {
        aggregation: readRequiredTrimmedStringValue(record['aggregation'], 'Metrics history.metadata.aggregation'),
        intervalMs: requiredNumber(record, 'interval_ms', 'Metrics history.metadata'),
        requestedIntervalMs: nullableNumber(record, 'requested_interval_ms', 'Metrics history.metadata'),
        intervalSource: readRequiredTrimmedStringValue(record['interval_source'], 'Metrics history.metadata.interval_source'),
        startTsMs: requiredNumber(record, 'start_ts_ms', 'Metrics history.metadata'),
        requestedStartTsMs: requiredNumber(record, 'requested_start_ts_ms', 'Metrics history.metadata'),
        endTsMs: requiredNumber(record, 'end_ts_ms', 'Metrics history.metadata'),
        requestedEndTsMs: requiredNumber(record, 'requested_end_ts_ms', 'Metrics history.metadata'),
        alignedStartTsMs: requiredNumber(record, 'aligned_start_ts_ms', 'Metrics history.metadata'),
        alignedEndTsMs: requiredNumber(record, 'aligned_end_ts_ms', 'Metrics history.metadata'),
        durationMs: requiredNumber(record, 'duration_ms', 'Metrics history.metadata'),
        requestedDurationMs: requiredNumber(record, 'requested_duration_ms', 'Metrics history.metadata'),
        points: requiredNumber(record, 'points', 'Metrics history.metadata'),
        requestedPoints: requiredNumber(record, 'requested_points', 'Metrics history.metadata'),
        effectivePoints: requiredNumber(record, 'effective_points', 'Metrics history.metadata'),
        maxPoints: requiredNumber(record, 'max_points', 'Metrics history.metadata'),
        bucketCount: requiredNumber(record, 'bucket_count', 'Metrics history.metadata'),
        bucketGapCount: requiredNumber(record, 'bucket_gap_count', 'Metrics history.metadata'),
        loggingIntervalMs: requiredNumber(record, 'logging_interval_ms', 'Metrics history.metadata'),
        supportsOhlc: readRequiredBooleanValue(record['supports_ohlc'], 'Metrics history.metadata.supports_ohlc'),
        retentionApplied: readRequiredBooleanValue(record['retention_applied'], 'Metrics history.metadata.retention_applied'),
        retentionStartTsMs: nullableNumber(record, 'retention_start_ts_ms', 'Metrics history.metadata'),
        supportedIntervalsMs: numberArray(record['supported_intervals_ms'], 'Metrics history.metadata.supported_intervals_ms'),
        metricKey: readRequiredTrimmedStringValue(record['metric_key'], 'Metrics history.metadata.metric_key'),
        availability: decodeOptionalHistoryAvailability(record, 'Metrics history.metadata')
    };
};

const decodeMetricsHistoryPayload = (value: JsonValue): MetricsHistoryPayload => {
    const record = requireRecord(value, 'Metrics history');
    if (hasOwn(record, 'timestampsMs') || hasOwn(record, 'intervalMs')) throw new TypeError('Metrics history must use canonical V1 wire fields');
    const timestampsMs = numberArray(record['timestamps_ms'], 'Metrics history.timestamps_ms');
    const values = nullableNumberArray(record['values'], 'Metrics history.values');
    const aggregation = readRequiredTrimmedStringValue(record['aggregation'], 'Metrics history.aggregation');
    if (aggregation !== 'ohlc' && aggregation !== 'delta_ohlc' && record['sample_counts'] === undefined) throw new TypeError('Metrics value history.sample_counts is required');
    const sampleCounts = record['sample_counts'] === undefined ? null : numberArray(record['sample_counts'], 'Metrics history.sample_counts');
    const ohlc = record['ohlc'] === undefined ? [] : nullableObjectArray(record['ohlc'], 'Metrics history.ohlc');
    if (timestampsMs.length !== values.length || (sampleCounts && sampleCounts.length !== timestampsMs.length) || (ohlc.length > 0 && ohlc.length !== timestampsMs.length)) throw new TypeError('Metrics history arrays must have matching lengths');
    if (sampleCounts && sampleCounts.some((count) => !Number.isSafeInteger(count) || count < 0)) throw new TypeError('Metrics history.sample_counts must contain nonnegative integers');
    return {
        aggregation,
        intervalMs: requiredNumber(record, 'interval_ms', 'Metrics history'),
        timestampsMs,
        values,
        sampleCounts,
        ohlc,
        metadata: decodeMetricsHistoryMetadata(record['metadata'])
    };
};

export { decodeMetricsHistoryPayload };
export type { MetricsHistoryMetadata, MetricsHistoryPayload };
