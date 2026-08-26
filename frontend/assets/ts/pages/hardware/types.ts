/* SoAI - Hardware page public contracts [frontend/assets/ts/pages/hardware/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import type { HardwareCapabilitiesResponse, HardwareHistoryConfiguration, HardwareSnapshotResponse } from '@core/api/contracts/hardwareContracts.ts';
import type { SystemMetricsResponse } from '@core/api/contracts/systemMetricsContracts.ts';
import type { CandlestickPoint, ChartColorContext, FilterOption } from '@features/charts/public.ts';

type LogLevel = 'debug' | 'info' | 'warn' | 'error';

type HardwarePageSnapshot = HardwareSnapshotResponse;
type HistoryConfig = HardwareHistoryConfiguration;
type HardwareCapabilities = HardwareCapabilitiesResponse;

type MetricsData = SystemMetricsResponse;

type DeviceSelection = {
    type: string;
    identifier: string | number | null;
    identifierKey: string | null;
    gpuIndex: number | null;
    value: string;
};

type QuerySelection = {
    selectionValue: string;
    metric: string | null;
    component: string;
};

interface HistoryDataPoint {
    timestamp: number;
    value?: number | undefined;
    open?: number | undefined;
    high?: number | undefined;
    low?: number | undefined;
    close?: number | undefined;
}

interface HistoryMetadata {
    aggregation?: string | undefined;
    intervalMs: number;
    monitoringIntervalMs?: number | undefined;
    maxPoints?: number | undefined;
    effectivePoints?: number | undefined;
    points?: number | undefined;
    requestedPoints?: number | undefined;
    component?: string | undefined;
    deviceId?: string | null | undefined;
    identifier?: string | null | undefined;
    bucketGapCount?: number | undefined;
}

type ValueHistorySeriesResult = {
    type: 'value';
    series: HistoryDataPoint[];
    metadata: HistoryMetadata;
};

type OhlcHistorySeriesResult = {
    type: 'ohlc';
    series: CandlestickPoint[];
    metadata: HistoryMetadata;
    candlestickBuckets: Map<number, CandlestickPoint & { count: number }>;
    intervalMs: number;
};

type HistorySeriesResult = ValueHistorySeriesResult | OhlcHistorySeriesResult;

type HistoryRequestParameters = {
    component: string;
    aggregation: string;
    points: number;
    startTsMs: number;
    endTsMs: number;
    gpuIndex?: number;
    identifier?: string;
    intervalMs?: number;
};

type MetricConfigEntry = {
    key?: string | undefined;
    devices?: string[] | undefined;
    bounds?: { min?: number | undefined; max?: number | undefined } | undefined;
    format?: ((value: number) => string) | undefined;
};

type CategoryOption = FilterOption & {
    value: string;
    label: string;
    selected?: boolean | undefined;
};

type MetricOption = FilterOption & {
    value: string;
    label: string;
    selected?: boolean | undefined;
};

type ApplyDeviceSelectionOptions = {
    restart?: boolean | undefined;
    updateSelector?: boolean | undefined;
    preferredMetric?: string | null | undefined;
    skipRender?: boolean | undefined;
};

type ChartDefaultsInput = {
    timeRanges?: number[] | undefined;
    candleIntervals?: number[] | undefined;
};

type HardwareLogFields = Record<string, JsonValue | Error | undefined>;
type ModuleLoggerPayload = JsonValue | Error | HardwareLogFields | null;
type ModuleLoggerFunctionValue = (level: LogLevel, message: string, data?: ModuleLoggerPayload) => void;

interface DiskSpeedData {
    status: string;
    observedAtMs?: number | undefined;
}

export type { ApplyDeviceSelectionOptions, ChartColorContext, ChartDefaultsInput, DeviceSelection, HistoryRequestParameters, HistorySeriesResult, MetricConfigEntry, QuerySelection, CandlestickPoint, CategoryOption, MetricOption, DiskSpeedData };

export type { HardwareCapabilities, HardwarePageSnapshot, HistoryConfig, HistoryDataPoint, HistoryMetadata, MetricsData };

export type { ModuleLoggerFunctionValue };
