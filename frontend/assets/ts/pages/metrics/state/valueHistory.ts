/* SoAI - Metrics page value history [frontend/assets/ts/pages/metrics/state/valueHistory.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { requestWebSocketSnapshotRecord } from '@core/websocketclient/snapshotPayload.ts';
import { serializeSystemMetricsHistoryRequest } from '@core/api/contracts/systemMetricsRequestContracts.ts';
import { readTimestampValueHistoryPayload } from '@core/realtime/historyPayloads.ts';
import { decodeMetricsHistoryPayload } from '@core/realtime/metricsHistoryContracts.ts';
import { serverEpochMs } from '@core/time/clock.ts';
import { hasFunctionProperty, isArray, isFiniteNumber, isNullOrUndefined, isObject } from '@core/typeGuards.ts';
import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';
import { readRoundedIntegerAtLeastValue } from '@core/types/numberCoercionReaders.ts';
import type { HistoryChartDataTransformsModule, HistoryChartRuntimeContract } from '@features/charts/public.ts';
import { resolveHistoryIntervalMs } from '@pages/metrics/mappers/metricsHistoryMapping.ts';
import type { MetricsCatalogEntry, MetricsHistoryPoint, ParsedHistoryResponse, ValueHistoryResult } from '@pages/metrics/types.ts';

interface ValueHistoryContext {
    chartRuntime: Pick<HistoryChartRuntimeContract, 'getCachedModules'>;
    getMetricHistoryKey(): string | null;
    getMetricHistoryAggregation(): string;
    getCatalogEntry(metricKey: string): MetricsCatalogEntry | null;
    isCandlestickActive(): boolean;
    updateMainChart(options: { resetView?: boolean; prepended?: MetricsHistoryPoint[] }): void;
    trimMetricsHistory(force?: boolean): boolean;
    getRequestToken(): number | null;
    setRequestToken(token: number | null): void;

    timeRange: number;
    pointBudget: number;
    monitoringIntervalMs: number;
    supportedHistoryIntervalsMs: number[] | null;
    maxHistoryPoints: number;

    metricsHistory: MetricsHistoryPoint[];
    metricsHistoryExhausted: boolean;
    valueHistoryRequestState: Map<string, string>;
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

const parseValueHistoryResponse = (context: ValueHistoryContext, response: JsonValue): ParsedHistoryResponse => {
    const payload = readTimestampValueHistoryPayload(decodeMetricsHistoryPayload(response));
    const points = buildPointsFromTimestampPairs(context, payload.timestamps, payload.values);
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
    const sanitized = sanitizedRaw.filter(isMetricsHistoryPoint);
    if (sanitized.length !== sanitizedRaw.length) {
        throw new TypeError('sanitizePoints returned invalid history points');
    }
    if (mode === 'refresh' && sanitized.length === 0) {
        throw new Error('Metrics history refresh returned no valid points');
    }
    if (sanitized.length === 0) {
        return { added: 0, prepended: [], replaced: false };
    }
    if (context.metricsHistory.length === 0 || mode === 'refresh') {
        context.metricsHistory = sanitized;
        context.trimMetricsHistory(true);
        return { added: context.metricsHistory.length, prepended: [], replaced: true };
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
        return { added: 0, prepended: [], replaced: false };
    }
    const newEntries = sanitized.slice(0, cutoffIndex + 1);
    const merged = [...newEntries, ...context.metricsHistory];
    const limit = context.maxHistoryPoints > 0 ? context.maxHistoryPoints : 20000;
    const overflow = Math.max(0, merged.length - limit);
    context.metricsHistory = overflow > 0 ? merged.slice(overflow) : merged;
    const retainedPrepended = overflow > 0 ? newEntries.slice(overflow) : newEntries;
    context.trimMetricsHistory(true);
    return { added: retainedPrepended.length, prepended: retainedPrepended, replaced: false };
};

const applyValueHistory = (context: ValueHistoryContext, response: JsonValue, { mode = 'refresh' }: { mode?: string } = {}): ValueHistoryResult & { intervalMs: number | null } => {
    const parsed = parseValueHistoryResponse(context, response);
    context.monitoringIntervalMs = readRoundedIntegerAtLeastValue(parsed.intervalMs, 'intervalMs', 1);
    context.metricsHistoryExhausted = false;
    const result = integrateValueHistoryPoints(context, parsed.points, { mode });
    return { ...result, intervalMs: parsed.intervalMs };
};

const fetchValueHistory = async (context: ValueHistoryContext, options: { resetView?: boolean; beforeTimestamp?: number | null } = {}, hasChartDataTransforms: boolean): Promise<boolean> => {
    const { resetView = false, beforeTimestamp = null } = options;
    const metricKey = context.getMetricHistoryKey();
    if (!metricKey || !hasChartDataTransforms) {
        if (resetView) {
            context.updateMainChart({ resetView });
        }
        return false;
    }
    const catalogEntry = context.getCatalogEntry(metricKey);
    if (!catalogEntry) {
        throw new Error(`Missing metricsCatalog entry for: ${metricKey}`);
    }
    if (!isNullOrUndefined(beforeTimestamp) && context.metricsHistoryExhausted) {
        return false;
    }
    const intervalMs = readRoundedIntegerAtLeastValue(context.monitoringIntervalMs, 'monitoringIntervalMs', 1);
    const earliestTimestamp = context.metricsHistory[0]?.timestamp;
    const earliestMs = isFiniteNumber(earliestTimestamp) ? Math.floor(earliestTimestamp) : null;
    let endMs = Math.floor(beforeTimestamp ?? serverEpochMs());
    if (!isNullOrUndefined(beforeTimestamp)) {
        endMs -= intervalMs;
    }
    if (!isNullOrUndefined(earliestMs)) {
        endMs = Math.min(endMs, earliestMs - intervalMs);
    }
    if (endMs <= 0) {
        if (!isNullOrUndefined(beforeTimestamp)) {
            context.metricsHistoryExhausted = true;
            return true;
        }
        return false;
    }
    const baseRangeMs = Math.max(intervalMs, Math.round(context.timeRange * 60_000));
    const desiredWindowMs = Math.max(baseRangeMs, Math.min(baseRangeMs * 4, intervalMs * Math.max(4, Math.min(context.pointBudget, 2000))));
    const startMs = Math.max(0, endMs - desiredWindowMs);
    const resolvedIntervalMs = resolveHistoryIntervalMs({
        startTsMs: startMs,
        endTsMs: endMs,
        requestedIntervalMs: intervalMs,
        pointBudget: context.pointBudget,
        supportedIntervalsMs: context.supportedHistoryIntervalsMs
    });
    if (startMs >= endMs) {
        if (!isNullOrUndefined(beforeTimestamp)) {
            context.metricsHistoryExhausted = true;
            return true;
        }
        return false;
    }
    const cacheKey = beforeTimestamp ? `${metricKey}:${startMs}:${endMs}:${resolvedIntervalMs}:${context.pointBudget}` : null;
    if (cacheKey) {
        const state = context.valueHistoryRequestState.get(cacheKey);
        if (state === 'pending' || state === 'done') {
            return false;
        }
        context.valueHistoryRequestState.set(cacheKey, 'pending');
    }
    const token = (context.getRequestToken() ?? 0) + 1;
    context.setRequestToken(token);

    let response: JsonObject | undefined;
    try {
        const aggregation = context.getMetricHistoryAggregation();
        const aggregations = isArray(catalogEntry.aggregations) ? catalogEntry.aggregations : [];
        if (!aggregations.includes(aggregation)) {
            throw new Error(`metricsCatalog entry for ${metricKey} does not support ${aggregation}`);
        }
        response = await requestWebSocketSnapshotRecord(
            'system.metrics.history',
            serializeSystemMetricsHistoryRequest({
                metricKey: metricKey,
                startTsMs: startMs,
                endTsMs: endMs,
                points: context.pointBudget,
                intervalMs: resolvedIntervalMs,
                aggregation
            })
        );
    } catch (error) {
        if (cacheKey) {
            context.valueHistoryRequestState.delete(cacheKey);
        }
        if (context.getRequestToken() === token) {
            context.setRequestToken(null);
        }
        throw error;
    }
    if (context.getRequestToken() !== token) {
        if (cacheKey) {
            context.valueHistoryRequestState.delete(cacheKey);
        }
        return false;
    }
    context.setRequestToken(null);
    const mode = isNullOrUndefined(beforeTimestamp) ? 'refresh' : 'prepend';
    const result = applyValueHistory(context, response, { mode });
    if (cacheKey) {
        context.valueHistoryRequestState.set(cacheKey, 'done');
    }
    if (!isNullOrUndefined(beforeTimestamp) && result.added === 0) {
        context.metricsHistoryExhausted = true;
    }
    if (result.added > 0) {
        if (mode === 'prepend' && result.prepended.length && !context.isCandlestickActive()) {
            context.updateMainChart({ prepended: result.prepended });
        } else {
            context.updateMainChart({ resetView: mode === 'refresh' && resetView });
        }
    }
    return true;
};

export { applyValueHistory, fetchValueHistory, integrateValueHistoryPoints, parseValueHistoryResponse };
export type { ValueHistoryContext };
