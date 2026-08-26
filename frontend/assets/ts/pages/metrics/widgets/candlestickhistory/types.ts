/* SoAI - Metrics page candlestick history contracts [frontend/assets/ts/pages/metrics/widgets/candlestickhistory/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import type { HistoryChartInstance, HistoryChartOhlcModule, ParsedOhlcResult } from '@features/charts/public.ts';
import type { CandlestickDataPoint, CandlestickMetadata, CandlestickResult, MetricsCatalogEntry } from '@pages/metrics/types.ts';

interface CandlestickHistoryQueryPort {
    runWithBoundary<T>(name: string, functionValue: () => Promise<T>): Promise<T>;
    getMetricHistoryKey(): string | null;
    getMetricHistoryOhlcAggregation(): string;
    getCatalogEntry(metricKey: string): MetricsCatalogEntry | null;
    getMetricTransform(): (value: number) => number;
    getEffectiveCandlestickIntervalMs(): number;
    syncChartControls(options: { range?: boolean; candles?: boolean }): Promise<void>;
    isCandlestickActive(): boolean;
    updateMainChart(options: { resetView?: boolean }): void;
    getRequestSignature(): string | null;
    setRequestSignature(signature: string | null): void;
    isRequestActive(): boolean;
    setRequestActive(active: boolean): void;
}

interface CandlestickHistoryLimitsPort {
    supportsOhlc: boolean;
    timeRange: number;
    maxRetentionMinutes: number | null;
    supportedHistoryIntervalsMs: number[] | null;
    pointBudget: number;
    historyTrimRatio: number;
    chartHardLimit: number;
    monitoringIntervalMs: number;
    historyApiPointCap: number;
    maxHistoryPoints: number;
    currentHistoryPointBudget: number;
}

interface CandlestickHistoryStatePort {
    candlestickHistoryExhausted: boolean;
    candlestickIntervalMinutes: number;
    lastResolvedCandlestickIntervalMs: number | null;
    baseCandleIntervals: number[] | null;
    candlestickData: CandlestickDataPoint[];
    candlestickBuckets: Map<number, CandlestickDataPoint & { count: number }>;
    candlestickMetadata: CandlestickMetadata | null;
}

interface CandlestickChartPort {
    mainChart: HistoryChartInstance | null;
}

interface CandlestickHistoryContext {
    query: CandlestickHistoryQueryPort;
    limits: CandlestickHistoryLimitsPort;
    state: CandlestickHistoryStatePort;
    chart: CandlestickChartPort;
}

type OhlcParserHost = Pick<HistoryChartOhlcModule, 'parseBackendOhlcResponse'> & {
    parseBackendOhlcResponse(response: JsonValue, options: { transform: (value: number) => number; requireAggregation?: boolean | undefined }): ParsedOhlcResult | null;
};

export type { CandlestickHistoryContext, CandlestickResult, OhlcParserHost };
