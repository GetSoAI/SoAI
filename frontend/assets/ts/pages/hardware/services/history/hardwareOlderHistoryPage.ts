/* SoAI - Hardware page older history page [frontend/assets/ts/pages/hardware/services/history/hardwareOlderHistoryPage.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { HardwareHistoryResponse } from '@core/api/contracts/hardwareContracts.ts';
import { throwIfAborted } from '@core/errors/abort.ts';
import { filterCandlestickBucketsForSeries, type CandlestickPoint, type ChartPointInput, resolveHistoryPagePoints, type HistoryPagerPage, type HistoryPageWindow } from '@features/charts/public.ts';
import { STR_AVG, STR_OHLC } from '@pages/hardware/contracts/hardwarePageSupport.ts';
import type { HistoryDataPoint, HistoryRequestParameters, HistorySeriesResult } from '@pages/hardware/types.ts';

interface HardwareOlderHistoryState {
    candlestickData: CandlestickPoint[];
    historyData: HistoryDataPoint[];
    candlestickBuckets: Map<number, CandlestickPoint & { count: number }>;
    maxHistoryPoints: number;
}

interface HardwareOlderHistoryHost {
    state: HardwareOlderHistoryState;
    buildHistoryRequestParameters(): HistoryRequestParameters;
    requestHistory(parameters: HistoryRequestParameters, signal: AbortSignal): Promise<HardwareHistoryResponse>;
    buildHistorySeriesFromPayload(payload: HardwareHistoryResponse): HistorySeriesResult;
    buildDisplaySeries(source: readonly HistoryDataPoint[], candlestick: boolean): ChartPointInput[];
}

const selectPrepended = <T extends { timestamp: number }>(series: readonly T[], existing: readonly T[], capacity: number): { prepended: T[]; capped: boolean } => {
    const earliest = existing[0]?.timestamp ?? Number.POSITIVE_INFINITY;
    const older = series.filter((point) => point.timestamp < earliest).sort((left, right) => left.timestamp - right.timestamp);
    const prepended = older.slice(Math.max(0, older.length - Math.max(0, capacity - existing.length)));
    return { prepended, capped: prepended.length < older.length };
};

const fetchHardwareOlderPage = async (host: HardwareOlderHistoryHost, candlestick: boolean, intervalMs: number, window: HistoryPageWindow, signal: AbortSignal): Promise<HistoryPagerPage> => {
    const parameters: HistoryRequestParameters = { ...host.buildHistoryRequestParameters(), ...window, points: resolveHistoryPagePoints(window, intervalMs), intervalMs, aggregation: candlestick ? STR_OHLC : STR_AVG };
    const response = await host.requestHistory(parameters, signal);
    throwIfAborted(signal);
    const payload = host.buildHistorySeriesFromPayload(response);
    const state = host.state;
    if (candlestick) {
        if (payload.type !== STR_OHLC) throw new TypeError('Hardware older candle response is invalid');
        if (payload.intervalMs !== intervalMs) throw new TypeError('Hardware older candle interval differs from the displayed series');
        const { prepended, capped } = selectPrepended(payload.series, state.candlestickData, state.maxHistoryPoints);
        if (prepended.length) {
            state.candlestickData = [...prepended, ...state.candlestickData];
            state.candlestickBuckets = filterCandlestickBucketsForSeries(state.candlestickData, new Map([...payload.candlestickBuckets, ...state.candlestickBuckets]));
        }
        return { points: host.buildDisplaySeries(prepended, true), capped };
    }
    if (payload.type !== 'value') throw new TypeError('Hardware older value response is invalid');
    if (payload.metadata.intervalMs !== intervalMs) throw new TypeError('Hardware older value interval differs from the displayed series');
    const { prepended, capped } = selectPrepended(payload.series, state.historyData, state.maxHistoryPoints);
    if (prepended.length) state.historyData = [...prepended, ...state.historyData];
    return { points: host.buildDisplaySeries(prepended, false), capped };
};

export { fetchHardwareOlderPage };
export type { HardwareOlderHistoryHost, HardwareOlderHistoryState };
