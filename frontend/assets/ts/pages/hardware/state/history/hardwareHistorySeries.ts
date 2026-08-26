/* SoAI - Hardware page history series [frontend/assets/ts/pages/hardware/state/history/hardwareHistorySeries.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { HardwareHistoryResponse } from '@core/api/contracts/hardwareContracts.ts';
import { buildHardwareValueSeriesFromHistoryPayload } from '@features/hardware/public.ts';
import type { ChartOhlcContract } from '@pages/hardware/contracts/contracts.ts';
import type { HistoryMetadata, HistorySeriesResult } from '@pages/hardware/types.ts';

const STR_OHLC = 'ohlc';

const normalizeAggregation = (value: string): string | null => {
    if (typeof value !== 'string') {
        return null;
    }
    const trimmed = value.trim();
    if (!trimmed) {
        return null;
    }
    return trimmed.toLowerCase();
};

export const buildHistorySeriesFromPayload = (inputArguments: { payload: HardwareHistoryResponse; aggregation: string; metricKey: string | undefined; monitoringIntervalMs: number; chartOhlc: ChartOhlcContract }): HistorySeriesResult | null => {
    if (!Number.isFinite(inputArguments.monitoringIntervalMs) || inputArguments.monitoringIntervalMs <= 0) {
        throw new TypeError('History series builder requires a valid monitoringIntervalMs');
    }
    const payload = inputArguments.payload;
    const aggregation = normalizeAggregation(payload.metadata.aggregation);
    if (!aggregation) {
        throw new TypeError('history payload metadata.aggregation is required');
    }
    const chartOhlc = inputArguments.chartOhlc;

    if (aggregation === STR_OHLC) {
        if (!inputArguments.metricKey) {
            throw new TypeError('history payload metricKey is required for ohlc aggregation');
        }
        const parsed = chartOhlc.parseBackendOhlcResponse(payload, { metricKey: inputArguments.metricKey });
        if (!parsed) return null;
        const series = parsed.candles;
        if (series.length === 0) return null;
        const intervalMs = parsed.metadata.intervalMs;
        if (!Number.isFinite(intervalMs) || intervalMs <= 0) {
            throw new TypeError('ohlc metadata.intervalMs must be a positive number');
        }
        const metadata: HistoryMetadata = { ...parsed.metadata, intervalMs: Math.max(1, Math.round(intervalMs)) };

        return {
            type: STR_OHLC,
            series,
            metadata,
            candlestickBuckets: parsed.candlestickBuckets,
            intervalMs: parsed.intervalMs
        };
    }

    const buildOptions: { metricKey?: string; parsers?: typeof chartOhlc } = { parsers: chartOhlc };
    if (inputArguments.metricKey !== undefined) {
        buildOptions.metricKey = inputArguments.metricKey;
    }
    const result = buildHardwareValueSeriesFromHistoryPayload(payload, buildOptions);
    if (!result) {
        return null;
    }
    return {
        type: 'value',
        series: result.series,
        metadata: result.metadata
    };
};
