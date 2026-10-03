/* SoAI - Metrics page value history [frontend/assets/ts/pages/metrics/state/valueHistory.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { SystemMetricsHistoryRequest } from '@core/api/contracts/systemMetricsRequestContracts.ts';
import { readTimestampValueHistoryPayload } from '@core/realtime/historyPayloads.ts';
import type { MetricsHistoryPayload } from '@core/realtime/metricsHistoryContracts.ts';
import { serverEpochMs } from '@core/time/clock.ts';
import { hasFunctionProperty, isArray, isFiniteNumber, isObject } from '@core/typeGuards.ts';
import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';
import { readRoundedIntegerAtLeastValue } from '@core/types/numberCoercionReaders.ts';
import { resolveHistoryPagePoints, type HistoryChartDataTransformsModule, type HistoryChartRuntimeContract, type HistoryPageWindow, type HistoryResolutionWindow } from '@features/charts/public.ts';
import { resolveHistoryIntervalMs } from '@pages/metrics/mappers/metricsHistoryMapping.ts';
import type { MetricsCatalogEntry, MetricsHistoryPoint, ParsedHistoryResponse, ValueHistoryResult } from '@pages/metrics/types.ts';

interface ValueHistoryContext {
    chartRuntime: Pick<HistoryChartRuntimeContract, 'getCachedModules'>;
    getMetricHistoryKey(): string | null;
    getMetricHistoryAggregation(): string;
    getCatalogEntry(metricKey: string): MetricsCatalogEntry | null;
    trimMetricsHistory(force?: boolean): boolean;

    timeRange: number;
    pointBudget: number;
    monitoringIntervalMs: number;
    historyIntervalMs: number | null;
    supportedHistoryIntervalsMs: number[] | null;
    maxHistoryPoints: number;

    metricsHistory: MetricsHistoryPoint[];
}

type ValueSeriesBuilder = Pick<HistoryChartDataTransformsModule, 'buildValueSeriesFromPairs'>;
type PointsSanitizer = Pick<HistoryChartDataTransformsModule, 'sanitizePoints'>;

const isMetricsHistoryPoint = <T>(value: T | JsonValue): value is T & MetricsHistoryPoint => {
    if (!isObject(value)) return false;
    return 'timestamp' in value && isFiniteNumber(value['timestamp']) && 'value' in value && isFiniteNumber(value['value']);
};

const isValueSeriesBuilder = <T>(value: T): value is T & ValueSeriesBuilder => {
    return isObject(value) && hasFunctionProperty(value, 'buildValueSeriesFromPairs');
};

const isPointsSanitizer = <T>(value: T): value is T & PointsSanitizer => {
    return isObject(value) && hasFunctionProperty(value, 'sanitizePoints');
};

const toJsonValuePoint = (point: MetricsHistoryPoint): JsonObject => ({
    timestamp: point.timestamp,
    value: point.value
});

const parseValueHistoryResponse = (context: ValueHistoryContext, response: MetricsHistoryPayload): ParsedHistoryResponse => {
    const payload = readTimestampValueHistoryPayload(response);
    const points = buildPointsFromTimestampPairs(context, payload.timestamps, payload.values);
    const counts = new Map<number, number>();
    response.sampleCounts?.forEach((count, index) => {
        const timestamp = payload.timestamps[index];
        if (timestamp !== undefined && count > 0) counts.set(timestamp, count);
    });
    for (const point of points) {
        const count = counts.get(point.timestamp);
        if (count === undefined) throw new TypeError('Metrics value history sample count is missing or invalid');
        point.sampleCount = count;
    }
    return { points, intervalMs: payload.intervalMs };
};

const buildPointsFromTimestampPairs = (context: ValueHistoryContext, timestamps: number[], values: number[]): MetricsHistoryPoint[] => {
    const dataTransforms = context.chartRuntime.getCachedModules()?.data;
    if (!isValueSeriesBuilder(dataTransforms)) {
        throw new TypeError('Metrics chart data module must implement buildValueSeriesFromPairs');
    }
    const series = dataTransforms.buildValueSeriesFromPairs(timestamps, values);
    if (!isArray(series)) {
        throw new TypeError('buildValueSeriesFromPairs must return an array');
    }
    const points = series.filter(isMetricsHistoryPoint);
    if (points.length !== series.length) {
        throw new TypeError('buildValueSeriesFromPairs returned invalid history points');
    }
    return points;
};

const integrateValueHistoryPoints = (context: ValueHistoryContext, points: MetricsHistoryPoint[], { mode = 'refresh' }: { mode?: string } = {}): ValueHistoryResult => {
    const dataTransforms = context.chartRuntime.getCachedModules()?.data;
    if (!isPointsSanitizer(dataTransforms)) {
        throw new TypeError('Metrics chart data module must implement sanitizePoints');
    }
    const sanitizedRaw = dataTransforms.sanitizePoints(points.map(toJsonValuePoint), { assumeSorted: false });
    if (!isArray(sanitizedRaw)) {
        throw new TypeError('sanitizePoints must return an array');
    }
    const counts = new Map(points.map((point) => [point.timestamp, point.sampleCount]));
    const sanitized = sanitizedRaw.filter(isMetricsHistoryPoint).map((point) => ({ ...point, sampleCount: counts.get(point.timestamp) }));
    if (sanitized.length !== sanitizedRaw.length) {
        throw new TypeError('sanitizePoints returned invalid history points');
    }
    if (context.metricsHistory.length === 0 || mode === 'refresh') {
        context.metricsHistory = sanitized;
        context.trimMetricsHistory(true);
        return { added: context.metricsHistory.length, prepended: [], replaced: true, capped: false };
    }
    const earliestTimestamp = context.metricsHistory[0]?.timestamp ?? Infinity;
    let cutoffIndex = -1;
    for (let index = sanitized.length - 1; index >= 0; index -= 1) {
        const entry = sanitized[index];
        if (!entry) {
            throw new Error(`Sanitized metrics history entry ${index} is missing`);
        }
        if (entry.timestamp < earliestTimestamp) {
            cutoffIndex = index;
            break;
        }
    }
    if (cutoffIndex === -1) {
        return { added: 0, prepended: [], replaced: false, capped: false };
    }
    const newEntries = sanitized.slice(0, cutoffIndex + 1);
    const room = Math.max(0, context.maxHistoryPoints - context.metricsHistory.length);
    const prepended = newEntries.slice(Math.max(0, newEntries.length - room));
    const capped = prepended.length < newEntries.length;
    if (prepended.length) context.metricsHistory = [...prepended, ...context.metricsHistory];
    return { added: prepended.length, prepended, replaced: false, capped };
};

const applyValueHistory = (context: ValueHistoryContext, response: MetricsHistoryPayload, { mode = 'refresh' }: { mode?: string } = {}): ValueHistoryResult & { intervalMs: number | null } => {
    const parsed = parseValueHistoryResponse(context, response);
    const intervalMs = readRoundedIntegerAtLeastValue(parsed.intervalMs, 'intervalMs', 1);
    if (mode === 'prepend' && intervalMs !== (context.historyIntervalMs ?? context.monitoringIntervalMs)) {
        throw new TypeError('Metrics older history interval differs from the displayed series');
    }
    context.historyIntervalMs = intervalMs;
    const result = integrateValueHistoryPoints(context, parsed.points, { mode });
    return { ...result, intervalMs: parsed.intervalMs };
};

const resolveValueHistoryRequest = (context: ValueHistoryContext, page: HistoryPageWindow | HistoryResolutionWindow | null): SystemMetricsHistoryRequest | null => {
    const metricKey = context.getMetricHistoryKey();
    if (!metricKey || !context.chartRuntime.getCachedModules()?.data) {
        return null;
    }
    const catalogEntry = context.getCatalogEntry(metricKey);
    if (!catalogEntry) {
        throw new Error(`Missing metricsCatalog entry for: ${metricKey}`);
    }
    const aggregation = context.getMetricHistoryAggregation();
    const aggregations = isArray(catalogEntry.aggregations) ? catalogEntry.aggregations : [];
    if (!aggregations.includes(aggregation)) {
        throw new Error(`metricsCatalog entry for ${metricKey} does not support ${aggregation}`);
    }
    if (page) {
        const pageIntervalMs = readRoundedIntegerAtLeastValue('intervalMs' in page ? page.intervalMs : (context.historyIntervalMs ?? context.monitoringIntervalMs), 'historyIntervalMs', 1);
        return { metricKey, startTsMs: page.startTsMs, endTsMs: page.endTsMs, points: resolveHistoryPagePoints(page, pageIntervalMs), intervalMs: pageIntervalMs, aggregation };
    }
    const intervalMs = readRoundedIntegerAtLeastValue(context.monitoringIntervalMs, 'monitoringIntervalMs', 1);
    const endMs = Math.floor(serverEpochMs());
    const baseRangeMs = Math.max(intervalMs, Math.round(context.timeRange * 60_000));
    const startMs = Math.max(0, endMs - Math.max(baseRangeMs, Math.min(baseRangeMs * 4, intervalMs * Math.max(4, Math.min(context.pointBudget, 2000)))));
    if (endMs <= 0 || startMs >= endMs) {
        return null;
    }
    return {
        metricKey,
        startTsMs: startMs,
        endTsMs: endMs,
        points: context.pointBudget,
        intervalMs: resolveHistoryIntervalMs({ startTsMs: startMs, endTsMs: endMs, requestedIntervalMs: intervalMs, pointBudget: context.pointBudget, supportedIntervalsMs: context.supportedHistoryIntervalsMs }),
        aggregation
    };
};

export { applyValueHistory, resolveValueHistoryRequest };
export type { ValueHistoryContext };
