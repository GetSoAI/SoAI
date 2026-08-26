/* SoAI - Hardware page history chunk fetch [frontend/assets/ts/pages/hardware/services/history/hardwareHistoryChunkFetch.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import { isArray, isFiniteNumber } from '@core/typeGuards.ts';
import type { CandlestickPoint } from '@features/charts/public.ts';
import { STR_AVG, STR_OHLC } from '@pages/hardware/contracts/hardwarePageSupport.ts';
import type { HistoryDataPoint, HistoryMetadata, HistoryRequestParameters, HistorySeriesResult } from '@pages/hardware/types.ts';

interface HardwareHistoryChunkHost {
    candlestickHistoryExhausted: boolean;
    lineHistoryExhausted: boolean;
    candlestickData: CandlestickPoint[];
    historyData: HistoryDataPoint[];
    currentHistoryPointBudget: number;
    timeRange: number;
    monitoringIntervalMs: number;
    historyMetadata: HistoryMetadata | null;
    candlestickMetadata: HistoryMetadata | null;
    candlestickBuckets: Map<number, CandlestickPoint & { count: number }>;
    lastResolvedCandlestickIntervalMs: number | undefined;
    buildHistoryRequestParameters(): HistoryRequestParameters;
    getEffectiveCandlestickIntervalMs(): number;
    clampHistoryPoints(value: number, min?: number): number;
    runHistoryFetch(parameters: HistoryRequestParameters, onResolve: (result: JsonValue) => Promise<void>): Promise<void>;
    buildHistorySeriesFromPayload(payload: JsonValue): HistorySeriesResult | null;
    mergeSeriesByTimestamp<T extends { timestamp: number }>(series: readonly T[], existing: readonly T[]): T[];
    trimCandlestickData(force: boolean): boolean;
    trimHistoryData(force: boolean): boolean;
    updateMainChart(): void;
}

const fetchHardwareHistoryChunk = async (host: HardwareHistoryChunkHost, isCandlestick: boolean, timestamp: number): Promise<void> => {
    if (!isFiniteNumber(timestamp)) return;
    if (isCandlestick ? host.candlestickHistoryExhausted : host.lineHistoryExhausted) return;
    const currentSeries = isCandlestick ? host.candlestickData : host.historyData;
    const intervalMs = isCandlestick ? host.getEffectiveCandlestickIntervalMs() : Math.max(1, host.monitoringIntervalMs);
    const earliestTimestampMs = Math.round(currentSeries[0]?.timestamp ?? timestamp);
    const endTimestampMs = earliestTimestampMs - intervalMs;
    if (endTimestampMs <= 0) {
        if (isCandlestick) host.candlestickHistoryExhausted = true;
        else host.lineHistoryExhausted = true;
        return;
    }
    const baseParameters = host.buildHistoryRequestParameters();
    const windowMs = baseParameters.endTsMs - baseParameters.startTsMs;
    if (!Number.isFinite(windowMs) || windowMs <= 0) {
        throw new TypeError('History request window must be a positive duration');
    }
    const parameters: HistoryRequestParameters = {
        ...baseParameters,
        endTsMs: endTimestampMs,
        aggregation: isCandlestick ? STR_OHLC : STR_AVG
    };
    parameters.startTsMs = Math.max(0, parameters.endTsMs - windowMs);
    if (isCandlestick) parameters.intervalMs = intervalMs;
    if (parameters.startTsMs >= parameters.endTsMs) {
        if (isCandlestick) host.candlestickHistoryExhausted = true;
        else host.lineHistoryExhausted = true;
        return;
    }
    const pointsByWindow = Math.ceil(windowMs / intervalMs);
    parameters.points = host.clampHistoryPoints(Math.max(baseParameters.points, pointsByWindow));
    await host.runHistoryFetch(parameters, async (result: JsonValue) => {
        const payload = host.buildHistorySeriesFromPayload(result);
        const previousTimestamp = currentSeries[0]?.timestamp;
        if (isCandlestick) {
            if (!payload || payload.type !== STR_OHLC || !payload.series.length) {
                host.candlestickHistoryExhausted = true;
                return;
            }
            if (!isArray(payload.series)) {
                throw new TypeError('Hardware candlestick series must be an array');
            }
            host.candlestickData = host.mergeSeriesByTimestamp(payload.series, host.candlestickData);
            host.candlestickMetadata = payload.metadata;
            host.candlestickBuckets = payload.candlestickBuckets;
            host.lastResolvedCandlestickIntervalMs = Math.max(1, Math.round(payload.intervalMs));
            host.trimCandlestickData(true);
        } else {
            if (!payload || payload.type !== 'value' || !payload.series.length) {
                host.lineHistoryExhausted = true;
                return;
            }
            if (!isArray(payload.series)) {
                throw new TypeError('Hardware line history series must be an array');
            }
            host.historyData = host.mergeSeriesByTimestamp(payload.series, host.historyData);
            host.historyMetadata = payload.metadata;
            host.trimHistoryData(true);
        }
        const updatedSeries = isCandlestick ? host.candlestickData : host.historyData;
        const firstTimestamp = updatedSeries[0]?.timestamp;
        if (firstTimestamp !== undefined && previousTimestamp !== undefined && firstTimestamp >= previousTimestamp) {
            if (isCandlestick) host.candlestickHistoryExhausted = true;
            else host.lineHistoryExhausted = true;
        }
        host.updateMainChart();
    });
};

export { fetchHardwareHistoryChunk };
export type { HardwareHistoryChunkHost };
