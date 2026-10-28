/* SoAI - Hardware page history realtime update [frontend/assets/ts/pages/hardware/realtime/hardwareHistoryRealtimeUpdate.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isArray, isFiniteNumber } from '@core/typeGuards.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { appendHistoryValue, resolveHistoryChartStorageCapacity, type CandlestickPoint, type HistoryChartInstance } from '@features/charts/public.ts';
import { extractRealtimeMetricValue, resolveRealtimeMetricTimestamp } from '@pages/hardware/realtime/hardwarerealtimemetricresolvers/service.ts';
import type { DeviceSelection, HardwarePageSnapshot, HistoryDataPoint, HistoryMetadata } from '@pages/hardware/types.ts';

interface HardwareHistoryMetadataHost {
    chartOhlc: {
        resolveNumeric(...values: (JsonValue | undefined)[]): number | null;
    };
    monitoringIntervalMs: number;
    historyApiPointCap: number;
    maxHistoryPoints: number;
    chartHardLimit: number;
    maxRetentionMinutes: number | null;
    currentHistoryPointBudget: number;
    applyChartDataLimits(): void;
    resolveHistoryPointLimit(): number;
}

interface HardwareHistoryRealtimeHost {
    clearedThroughMs: number;
    chartOhlc: {
        resolveNumeric(...values: (JsonValue | undefined)[]): number | null;
        toTimestampMs(value: JsonValue | undefined): number | null;
    };
    getMetricKey(): string | undefined;
    getSelectedHistoryTarget(): DeviceSelection;
    historyData: HistoryDataPoint[];
    historyMetadata: HistoryMetadata | null;
    acceptRealtimeTimestamp(timestamp: number): boolean;
    trimHistoryData(force?: boolean): boolean;
    mainChart: HistoryChartInstance | null;
    isCandlestickActive(): boolean;
    updateRealtimeCandlestick(timestamp: JsonValue, value: JsonValue): { appended: boolean } | null;
    trimCandlestickData(force?: boolean): boolean;
    candlestickData: CandlestickPoint[];
    updateMainChart(options?: { resetView?: boolean }): void;
    getMetricLabel(): string;
}

const parseHardwareHistoryResponseMetadata = (host: HardwareHistoryMetadataHost, metadata: HistoryMetadata | null | undefined): void => {
    if (!metadata) return;
    const toInt = (...values: (JsonValue | undefined)[]): number | null => {
        const value = Math.round(host.chartOhlc.resolveNumeric(...values) ?? -1);
        return value > 0 ? value : null;
    };
    const monitoringIntervalMs = toInt(metadata.monitoringIntervalMs);
    if (monitoringIntervalMs) host.monitoringIntervalMs = monitoringIntervalMs;
    const maxPoints = toInt(metadata.maxPoints);
    if (maxPoints) {
        host.historyApiPointCap = Math.min(host.chartHardLimit, maxPoints);
        host.maxHistoryPoints = resolveHistoryChartStorageCapacity(host.historyApiPointCap, host.maxRetentionMinutes, host.monitoringIntervalMs, host.chartHardLimit);
        host.applyChartDataLimits();
    }
    const historyPointLimit = host.resolveHistoryPointLimit();
    host.currentHistoryPointBudget = Math.min(historyPointLimit, toInt(metadata.effectivePoints) ?? historyPointLimit);
};

const applyHardwareHistoryRealtimeUpdate = (host: HardwareHistoryRealtimeHost, payload: HardwarePageSnapshot): void => {
    if (!payload) return;
    const timestamp = host.chartOhlc.toTimestampMs(resolveRealtimeMetricTimestamp({ metricKey: host.getMetricKey(), selectedTarget: host.getSelectedHistoryTarget(), payload }));
    const value = extractRealtimeMetricValue({
        metricKey: host.getMetricKey(),
        selectedTarget: host.getSelectedHistoryTarget(),
        payload,
        networkSpeedSources: [payload.networkSpeed],
        chartOhlc: host.chartOhlc
    });
    if (!isFiniteNumber(timestamp) || !isFiniteNumber(value) || timestamp <= host.clearedThroughMs) return;
    if (!isArray(host.historyData)) throw new TypeError('historyData must be an array');
    const candlestick = host.isCandlestickActive();
    const metadata = candlestick ? null : host.historyMetadata;
    if (!candlestick && !metadata) throw new TypeError('Value history metadata is required for realtime updates');
    if (!host.acceptRealtimeTimestamp(timestamp)) return;
    if (candlestick) {
        const result = host.updateRealtimeCandlestick(timestamp, value);
        if (!result) {
            return;
        }
        const appended = result.appended;
        if (host.trimCandlestickData(appended)) return host.updateMainChart({ resetView: false });
        const latest = host.candlestickData[host.candlestickData.length - 1];
        if (host.mainChart && latest) {
            if (appended) {
                host.mainChart.data.appendPoint({ ...latest });
            } else {
                host.mainChart.data.updateCurrentBar({ ...latest });
            }
        }
    } else {
        if (!metadata) throw new TypeError('Value history metadata is required for realtime updates');
        const appendResult = appendHistoryValue(host.historyData, timestamp, value, metadata.intervalMs, metadata.aggregation ?? 'avg');
        if (appendResult === 'ignored') return;
        const trimmed = host.trimHistoryData();
        if (trimmed) return host.updateMainChart({ resetView: false });
        const latest = host.historyData[host.historyData.length - 1];
        if (!latest) throw new TypeError('Realtime history sample was not retained');
        if (latest.value === undefined) throw new TypeError('Realtime history sample requires a value');
        const chartPoint = { timestamp: latest.timestamp, value: latest.value };
        if (appendResult === 'updated') host.mainChart?.data.updateCurrentBar(chartPoint);
        else host.mainChart?.data.appendPoint(chartPoint);
    }
    host.mainChart?.settings.setMetricName(host.getMetricLabel());
};

export { applyHardwareHistoryRealtimeUpdate, parseHardwareHistoryResponseMetadata };
export type { HardwareHistoryMetadataHost, HardwareHistoryRealtimeHost };
