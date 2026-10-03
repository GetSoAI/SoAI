/* SoAI - Hardware history host builder contracts [frontend/assets/ts/pages/hardware/controllers/hardwarehistoryhostbuilders/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import type { CandlestickPoint } from '@features/charts/public.ts';
import type { HardwareHistoryMetadataHost, HardwareHistoryRealtimeHost } from '@pages/hardware/realtime/hardwareHistoryRealtimeUpdate.ts';
import type { DeviceSelection, HistoryDataPoint, HistoryMetadata } from '@pages/hardware/types.ts';

export interface HardwareHistoryMetadataHostInput {
    chartOhlc: HardwareHistoryMetadataHost['chartOhlc'];
    getMonitoringIntervalMs: () => number;
    setMonitoringIntervalMs: (value: number) => void;
    getHistoryApiPointCap: () => number;
    setHistoryApiPointCap: (value: number) => void;
    getMaxHistoryPoints: () => number;
    setMaxHistoryPoints: (value: number) => void;
    getChartHardLimit: () => number;
    getMaxRetentionMinutes: () => number | null;
    getCurrentHistoryPointBudget: () => number;
    setCurrentHistoryPointBudget: (value: number) => void;
    applyChartDataLimits: () => void;
    resolveHistoryPointLimit: () => number;
}

export interface HardwareHistoryRealtimeHostInput {
    getClearedThroughMs: () => number;
    chartOhlc: HardwareHistoryRealtimeHost['chartOhlc'];
    getMetricKey: () => string | undefined;
    getSelectedHistoryTarget: () => DeviceSelection;
    getHistoryData: () => HistoryDataPoint[];
    getHistoryMetadata: () => HistoryMetadata | null;
    acceptRealtimeTimestamp: (timestamp: number) => boolean;
    trimHistoryData: (force?: boolean) => boolean;
    getMainChart: () => HardwareHistoryRealtimeHost['mainChart'];
    isCandlestickActive: () => boolean;
    updateRealtimeCandlestick: (timestamp: JsonValue, value: JsonValue) => { appended: boolean } | null;
    trimCandlestickData: (force?: boolean) => boolean;
    getCandlestickData: () => CandlestickPoint[];
    updateMainChart: (options?: { resetView?: boolean }) => void;
    getMetricLabel: () => string;
}
