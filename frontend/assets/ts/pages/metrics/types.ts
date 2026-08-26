/* SoAI - Metrics page contracts [frontend/assets/ts/pages/metrics/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { TrustedHtml } from '@core/security/public.ts';
import type { ApiKeyUsageRow } from '@core/settings/apiKeyPayloads.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import type { SystemMetricsResponse } from '@core/api/contracts/systemMetricsContracts.ts';
import type { MetricsCapabilities, MetricsCatalogEntry } from '@core/realtime/streammanager/resources/systemMetricsMetadataContracts.ts';
import type { CandlestickPoint, ChartColorContext, HistoryChartInstance } from '@features/charts/public.ts';
import type { Metrics } from '@features/metrics/public.ts';

export interface MetricExtractors {
    [key: string]: (match: MetricsData) => number | null;
}

export type MetricsData = Metrics & SystemMetricsResponse;

export interface MetricsHistoryPoint {
    timestamp: number;
    value: number;
}

export type CandlestickDataPoint = CandlestickPoint;

export interface TableBodyContext {
    table: HTMLElement;
    bodyElement: HTMLElement;
    rows: HTMLTableRowElement[];
}

export interface PluginHealthRow {
    name: string;
    requests: number;
    requestsLabel: string;
    tokens: number;
    tokensLabel: string;
    status: string;
    statusLabel: string;
    badge: TrustedHtml;
}

export type { ApiKeyUsageRow };

export interface ScaleBounds {
    min?: number | undefined;
    max?: number | undefined;
}

export interface ChartModuleDefaults {
    timeRanges?: number[] | undefined;
    candleIntervals?: number[] | undefined;
    constants?: JsonValue | null | undefined;
}

export type ChartInstanceWithMethods = HistoryChartInstance;

export interface CandlestickMetadata {
    intervalMs: number;
    monitoringIntervalMs?: number | undefined;
    loggingIntervalMs?: number | undefined;
    maxPoints?: number | undefined;
    effectivePoints?: number | undefined;
    requestedPoints?: number | undefined;
    points?: number | undefined;
}

export interface CandlestickResult {
    candles: CandlestickDataPoint[];
    candlestickBuckets: Map<number, CandlestickDataPoint & { count: number }>;
    metadata: CandlestickMetadata;
    intervalMs: number;
}

export interface RealtimeCandlestickUpdate {
    updated: boolean;
    appended: boolean;
    point: CandlestickDataPoint | null;
}

export interface ParsedHistoryResponse {
    points: MetricsHistoryPoint[];
    intervalMs: number | null;
}

export interface ValueHistoryResult {
    added: number;
    prepended: MetricsHistoryPoint[];
    replaced: boolean;
}

export type CapabilitiesData = MetricsCapabilities;

export type HistoryResponse = JsonValue;
export type { ChartColorContext, MetricsCatalogEntry };
