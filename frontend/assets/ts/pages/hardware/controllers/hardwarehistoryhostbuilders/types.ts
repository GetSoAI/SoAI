/* SoAI - Hardware history host builder contracts [frontend/assets/ts/pages/hardware/controllers/hardwarehistoryhostbuilders/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import type { CandlestickPoint } from '@features/charts/public.ts';
import type { HardwareHistoryMetadataHost, HardwareHistoryRealtimeHost } from '@pages/hardware/realtime/hardwareHistoryRealtimeUpdate.ts';
import type { DeviceSelection, HistoryDataPoint, HistoryMetadata, HistoryRequestParameters, HistorySeriesResult } from '@pages/hardware/types.ts';

export interface HardwareHistoryMetadataHostInput {
    chartOhlc: HardwareHistoryMetadataHost['chartOhlc'];
    getMonitoringIntervalMs: () => number;
    setMonitoringIntervalMs: (value: number) => void;
    getHistoryApiPointCap: () => number;
    setHistoryApiPointCap: (value: number) => void;
    getMaxHistoryPoints: () => number;
    setMaxHistoryPoints: (value: number) => void;
    getChartHardLimit: () => number;
    getCurrentHistoryPointBudget: () => number;
    setCurrentHistoryPointBudget: (value: number) => void;
    applyChartDataLimits: () => void;
    resolveHistoryPointLimit: () => number;
}

export interface HardwareHistoryRealtimeHostInput {
    getHistoryRequestToken: () => symbol | null;
    chartOhlc: HardwareHistoryRealtimeHost['chartOhlc'];
    getMetricKey: () => string | undefined;
    getSelectedHistoryTarget: () => DeviceSelection;
    getHistoryData: () => HistoryDataPoint[];
    chartDataTransforms: HardwareHistoryRealtimeHost['chartDataTransforms'];
    getMonitoringIntervalMs: () => number;
    resolveHistoryPointLimit: () => number;
    trimHistoryData: (force?: boolean) => boolean;
    getMainChart: () => HardwareHistoryRealtimeHost['mainChart'];
    isCandlestickActive: () => boolean;
    updateRealtimeCandlestick: (timestamp: JsonValue, value: JsonValue) => { appended: boolean } | null;
    trimCandlestickData: (force?: boolean) => boolean;
    getCandlestickData: () => CandlestickPoint[];
    updateMainChart: (options?: { resetView?: boolean }) => void;
    getMetricLabel: () => string;
}

export interface HardwareHistoryChunkHostInput {
    getCandlestickHistoryExhausted: () => boolean;
    setCandlestickHistoryExhausted: (value: boolean) => void;
    getLineHistoryExhausted: () => boolean;
    setLineHistoryExhausted: (value: boolean) => void;
    getCandlestickData: () => CandlestickPoint[];
    setCandlestickData: (value: CandlestickPoint[]) => void;
    getHistoryData: () => HistoryDataPoint[];
    setHistoryData: (value: HistoryDataPoint[]) => void;
    getCurrentHistoryPointBudget: () => number;
    getTimeRange: () => number;
    getMonitoringIntervalMs: () => number;
    getHistoryMetadata: () => HistoryMetadata | null;
    setHistoryMetadata: (value: HistoryMetadata | null) => void;
    getCandlestickMetadata: () => HistoryMetadata | null;
    setCandlestickMetadata: (value: HistoryMetadata | null) => void;
    getCandlestickBuckets: () => Map<number, CandlestickPoint & { count: number }>;
    setCandlestickBuckets: (value: Map<number, CandlestickPoint & { count: number }>) => void;
    getLastResolvedCandlestickIntervalMs: () => number | undefined;
    setLastResolvedCandlestickIntervalMs: (value: number | undefined) => void;
    buildHistoryRequestParameters: () => HistoryRequestParameters;
    getEffectiveCandlestickIntervalMs: () => number;
    clampHistoryPoints: (value: number, min?: number) => number;
    runHistoryFetch: (parameters: HistoryRequestParameters, onResolve: (result: JsonValue) => Promise<void>) => Promise<void>;
    buildHistorySeriesFromPayload: (payload: JsonValue) => HistorySeriesResult | null;
    mergeSeriesByTimestamp: <T extends { timestamp: number }>(series: readonly T[], existing: readonly T[]) => T[];
    trimCandlestickData: (force: boolean) => boolean;
    trimHistoryData: (force: boolean) => boolean;
    updateMainChart: () => void;
}
