/* SoAI - Hardware page history realtime update [frontend/assets/ts/pages/hardware/realtime/hardwareHistoryRealtimeUpdate.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isArray, isFiniteNumber } from '@core/typeGuards.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { HISTORY_CHART_MIN_POINTS, scaleHistoryChartPointCount, type CandlestickPoint, type HistoryChartDataTransformsModule, type HistoryChartInstance } from '@features/charts/public.ts';
import { extractRealtimeMetricValue } from '@pages/hardware/realtime/hardwarerealtimemetricresolvers/service.ts';
import type { DeviceSelection, HardwarePageSnapshot, HistoryDataPoint, HistoryMetadata } from '@pages/hardware/types.ts';

interface HardwareHistoryMetadataHost {
    chartOhlc: {
        resolveNumeric(...values: (JsonValue | undefined)[]): number | null;
    };
    monitoringIntervalMs: number;
    historyApiPointCap: number;
    maxHistoryPoints: number;
    chartHardLimit: number;
    currentHistoryPointBudget: number;
    applyChartDataLimits(): void;
    resolveHistoryPointLimit(): number;
}

interface HardwareHistoryRealtimeHost {
    historyRequestToken: symbol | null;
    chartOhlc: {
        resolveNumeric(...values: (JsonValue | undefined)[]): number | null;
        toTimestampMs(value: JsonValue | undefined): number | null;
    };
    getMetricKey(): string | undefined;
    getSelectedHistoryTarget(): DeviceSelection;
    historyData: HistoryDataPoint[];
    chartDataTransforms: HistoryChartDataTransformsModule;
    monitoringIntervalMs: number;
    resolveHistoryPointLimit(): number;
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
        host.historyApiPointCap = host.maxHistoryPoints = Math.min(host.chartHardLimit, Math.max(HISTORY_CHART_MIN_POINTS, scaleHistoryChartPointCount(maxPoints)));
        host.applyChartDataLimits();
    }
    const historyPointLimit = host.resolveHistoryPointLimit();
    host.currentHistoryPointBudget = Math.min(historyPointLimit, toInt(metadata.effectivePoints) ?? historyPointLimit);
};

const applyHardwareHistoryRealtimeUpdate = (host: HardwareHistoryRealtimeHost, payload: HardwarePageSnapshot, token: symbol | null = host.historyRequestToken): void => {
    if (token !== host.historyRequestToken || !payload) return;
    const timestamp = host.chartOhlc.toTimestampMs(payload.timestampMs);
    const value = extractRealtimeMetricValue({
        metricKey: host.getMetricKey(),
        selectedTarget: host.getSelectedHistoryTarget(),
        payload,
        networkSpeedSources: [payload.networkSpeed],
        chartOhlc: host.chartOhlc
    });
    if (!isFiniteNumber(timestamp) || !isFiniteNumber(value)) return;
    if (!isArray(host.historyData)) throw new TypeError('historyData must be an array');
    if (host.historyData.length && host.chartDataTransforms?.buildLineGapFillers) {
        const lastPoint = host.historyData[host.historyData.length - 1];
        if (lastPoint && isFiniteNumber(lastPoint.value)) {
            host.chartDataTransforms
                .buildLineGapFillers({ timestamp: lastPoint.timestamp, value: lastPoint.value }, timestamp, Math.max(1, Math.round(host.monitoringIntervalMs)), {
                    maxFill: host.resolveHistoryPointLimit()
                })
                .forEach((filler) => host.historyData.push({ timestamp: filler.timestamp, value: filler.value }));
        }
    }
    host.historyData.push({ timestamp, value });
    const trimmed = host.trimHistoryData();
    if (host.mainChart?.view.status.isAnimating || host.mainChart?.view.status.isDragging) return;
    if (host.isCandlestickActive()) {
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
    } else if (host.mainChart) {
        if (trimmed) return host.updateMainChart({ resetView: false });
        host.mainChart.data.appendPoint({ timestamp, value });
    }
    host.mainChart?.settings.setMetricName(host.getMetricLabel());
};

export { applyHardwareHistoryRealtimeUpdate, parseHardwareHistoryResponseMetadata };
export type { HardwareHistoryMetadataHost, HardwareHistoryRealtimeHost };
