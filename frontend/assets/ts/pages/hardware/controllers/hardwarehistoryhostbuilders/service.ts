/* SoAI - Hardware history host builder service [frontend/assets/ts/pages/hardware/controllers/hardwarehistoryhostbuilders/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import type { CandlestickPoint } from '@features/charts/public.ts';
import type { HardwareHistoryMetadataHostInput, HardwareHistoryRealtimeHostInput } from '@pages/hardware/controllers/hardwarehistoryhostbuilders/types.ts';
import type { HardwareHistoryMetadataHost, HardwareHistoryRealtimeHost } from '@pages/hardware/realtime/hardwareHistoryRealtimeUpdate.ts';
import type { HistoryDataPoint } from '@pages/hardware/types.ts';

const createHardwareHistoryMetadataHost = (input: HardwareHistoryMetadataHostInput): HardwareHistoryMetadataHost => ({
    chartOhlc: input.chartOhlc,
    get monitoringIntervalMs() {
        return input.getMonitoringIntervalMs();
    },
    set monitoringIntervalMs(value: number) {
        input.setMonitoringIntervalMs(value);
    },
    get historyApiPointCap() {
        return input.getHistoryApiPointCap();
    },
    set historyApiPointCap(value: number) {
        input.setHistoryApiPointCap(value);
    },
    get maxHistoryPoints() {
        return input.getMaxHistoryPoints();
    },
    set maxHistoryPoints(value: number) {
        input.setMaxHistoryPoints(value);
    },
    get chartHardLimit() {
        return input.getChartHardLimit();
    },
    get maxRetentionMinutes() {
        return input.getMaxRetentionMinutes();
    },
    get currentHistoryPointBudget() {
        return input.getCurrentHistoryPointBudget();
    },
    set currentHistoryPointBudget(value: number) {
        input.setCurrentHistoryPointBudget(value);
    },
    applyChartDataLimits: (): void => input.applyChartDataLimits(),
    resolveHistoryPointLimit: (): number => input.resolveHistoryPointLimit()
});

const createHardwareHistoryRealtimeHost = (input: HardwareHistoryRealtimeHostInput): HardwareHistoryRealtimeHost => ({
    get clearedThroughMs() {
        return input.getClearedThroughMs();
    },
    chartOhlc: input.chartOhlc,
    getMetricKey: (): string | undefined => input.getMetricKey(),
    getSelectedHistoryTarget: () => input.getSelectedHistoryTarget(),
    get historyData(): HistoryDataPoint[] {
        return input.getHistoryData();
    },
    get historyMetadata() {
        return input.getHistoryMetadata();
    },
    acceptRealtimeTimestamp: (timestamp: number): boolean => input.acceptRealtimeTimestamp(timestamp),
    trimHistoryData: (force?: boolean): boolean => input.trimHistoryData(force),
    get mainChart() {
        return input.getMainChart();
    },
    isCandlestickActive: (): boolean => input.isCandlestickActive(),
    updateRealtimeCandlestick: (timestamp: JsonValue, value: JsonValue) => input.updateRealtimeCandlestick(timestamp, value),
    trimCandlestickData: (force?: boolean): boolean => input.trimCandlestickData(force),
    get candlestickData(): CandlestickPoint[] {
        return input.getCandlestickData();
    },
    updateMainChart: (options?: { resetView?: boolean }): void => input.updateMainChart(options),
    getMetricLabel: (): string => input.getMetricLabel()
});

export { createHardwareHistoryMetadataHost, createHardwareHistoryRealtimeHost };
