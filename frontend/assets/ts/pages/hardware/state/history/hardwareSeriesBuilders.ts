/* SoAI - Hardware page series builders [frontend/assets/ts/pages/hardware/state/history/hardwareSeriesBuilders.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';
import { isArray } from '@core/typeGuards.ts';
import type { BuildCandlestickOptions, CandlestickPoint, ChartValuePointInput, HistoryChartDataTransformsModule } from '@features/charts/public.ts';
import type { HistoryDataPoint } from '@pages/hardware/types.ts';

interface HardwareValueSeriesHost {
    maxHistoryPoints: number;
    monitoringIntervalMs: number;
    timeRange: number;
    chartType: string;
    chartDataTransforms: HistoryChartDataTransformsModule;
    chartOhlc: {
        buildCandlestickSeries(data: JsonValue, options?: BuildCandlestickOptions): CandlestickPoint[];
    };
}

interface HardwareCandlestickSeriesHost {
    chartOhlc: {
        buildCandlestickSeries(data: JsonValue, options?: BuildCandlestickOptions): CandlestickPoint[];
    };
    candlestickMetadata: { intervalMs: number } | null;
    lastResolvedCandlestickIntervalMs?: number | undefined;
    monitoringIntervalMs: number;
}

const buildHardwareValueSeries = (host: HardwareValueSeriesHost, data: HistoryDataPoint[], maxDataPoints?: number): ChartValuePointInput[] => {
    if (!isArray(data)) throw new TypeError('data must be an array');
    return host.chartDataTransforms.toLineSeries(toJsonHistorySeries(data), maxDataPoints ?? host.maxHistoryPoints, {
        assumeSorted: true,
        fillGaps: true,
        intervalMs: Math.max(1, Math.round(host.monitoringIntervalMs)),
        rangeMs: Math.max(60000, Math.round(host.timeRange * 60000)),
        densityMode: host.chartType === 'bar' ? 'average' : 'shape',
        targetPoints: maxDataPoints ?? host.maxHistoryPoints
    });
};

const buildHardwareCandlestickSeries = (host: HardwareCandlestickSeriesHost, data: HistoryDataPoint[], maxDataPoints?: number): CandlestickPoint[] => {
    const metadataInterval = Number(host.candlestickMetadata?.intervalMs);
    const resolvedInterval = Number(host.lastResolvedCandlestickIntervalMs);
    const monitoringInterval = Number(host.monitoringIntervalMs);
    const intervalMs = Number.isFinite(metadataInterval) && metadataInterval > 0 ? Math.max(1, Math.round(metadataInterval)) : Number.isFinite(resolvedInterval) && resolvedInterval > 0 ? Math.max(1, Math.round(resolvedInterval)) : Number.isFinite(monitoringInterval) && monitoringInterval > 0 ? Math.max(1, Math.round(monitoringInterval)) : NaN;
    if (!Number.isFinite(intervalMs) || intervalMs <= 0) {
        throw new TypeError('Unable to resolve a positive candlestick intervalMs');
    }
    const options: BuildCandlestickOptions = {
        timeRangeMs: Infinity,
        intervalMs
    };
    if (maxDataPoints !== undefined) {
        options.maxPoints = maxDataPoints;
    }
    return host.chartOhlc.buildCandlestickSeries(toJsonHistorySeries(data), options);
};

const toJsonHistorySeries = (data: readonly HistoryDataPoint[]): JsonValue => {
    return data.map((point): JsonObject => {
        const record: JsonObject = { timestamp: point.timestamp };
        const value = point.value;
        const open = point.open;
        const high = point.high;
        const low = point.low;
        const close = point.close;
        if (typeof value === 'number' && Number.isFinite(value)) record['value'] = value;
        if (typeof open === 'number' && Number.isFinite(open)) record['open'] = open;
        if (typeof high === 'number' && Number.isFinite(high)) record['high'] = high;
        if (typeof low === 'number' && Number.isFinite(low)) record['low'] = low;
        if (typeof close === 'number' && Number.isFinite(close)) record['close'] = close;
        return record;
    });
};

const mergeSeriesByTimestamp = <T extends { timestamp: number }>(series: readonly T[], existing: readonly T[]): T[] => {
    const merged = new Map<number, T>();
    existing.forEach((entry) => merged.set(entry.timestamp, entry));
    series.forEach((entry) => merged.set(entry.timestamp, entry));
    return Array.from(merged.values()).sort((left, right) => left.timestamp - right.timestamp);
};

export { buildHardwareCandlestickSeries, buildHardwareValueSeries, mergeSeriesByTimestamp };
export type { HardwareCandlestickSeriesHost, HardwareValueSeriesHost };
