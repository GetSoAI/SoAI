/* SoAI - Hardware history host builder service [frontend/assets/ts/pages/hardware/controllers/hardwarehistoryhostbuilders/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import type { CandlestickPoint } from '@features/charts/public.ts';
import type { HardwareHistoryChunkHostInput, HardwareHistoryMetadataHostInput, HardwareHistoryRealtimeHostInput } from '@pages/hardware/controllers/hardwarehistoryhostbuilders/types.ts';
import type { HardwareHistoryMetadataHost, HardwareHistoryRealtimeHost } from '@pages/hardware/realtime/hardwareHistoryRealtimeUpdate.ts';
import type { HardwareHistoryChunkHost } from '@pages/hardware/services/history/hardwareHistoryChunkFetch.ts';
import type { HistoryDataPoint, HistoryMetadata, HistoryRequestParameters, HistorySeriesResult } from '@pages/hardware/types.ts';

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
    get historyRequestToken() {
        return input.getHistoryRequestToken();
    },
    chartOhlc: input.chartOhlc,
    getMetricKey: (): string | undefined => input.getMetricKey(),
    getSelectedHistoryTarget: () => input.getSelectedHistoryTarget(),
    get historyData(): HistoryDataPoint[] {
        return input.getHistoryData();
    },
    chartDataTransforms: input.chartDataTransforms,
    get monitoringIntervalMs() {
        return input.getMonitoringIntervalMs();
    },
    resolveHistoryPointLimit: (): number => input.resolveHistoryPointLimit(),
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

const createHardwareHistoryChunkHost = (input: HardwareHistoryChunkHostInput): HardwareHistoryChunkHost => ({
    get candlestickHistoryExhausted() {
        return input.getCandlestickHistoryExhausted();
    },
    set candlestickHistoryExhausted(value: boolean) {
        input.setCandlestickHistoryExhausted(value);
    },
    get lineHistoryExhausted() {
        return input.getLineHistoryExhausted();
    },
    set lineHistoryExhausted(value: boolean) {
        input.setLineHistoryExhausted(value);
    },
    get candlestickData(): CandlestickPoint[] {
        return input.getCandlestickData();
    },
    set candlestickData(value: CandlestickPoint[]) {
        input.setCandlestickData(value);
    },
    get historyData(): HistoryDataPoint[] {
        return input.getHistoryData();
    },
    set historyData(value: HistoryDataPoint[]) {
        input.setHistoryData(value);
    },
    get currentHistoryPointBudget() {
        return input.getCurrentHistoryPointBudget();
    },
    get timeRange() {
        return input.getTimeRange();
    },
    get monitoringIntervalMs() {
        return input.getMonitoringIntervalMs();
    },
    get historyMetadata(): HistoryMetadata | null {
        return input.getHistoryMetadata();
    },
    set historyMetadata(value: HistoryMetadata | null) {
        input.setHistoryMetadata(value);
    },
    get candlestickMetadata(): HistoryMetadata | null {
        return input.getCandlestickMetadata();
    },
    set candlestickMetadata(value: HistoryMetadata | null) {
        input.setCandlestickMetadata(value);
    },
    get candlestickBuckets(): Map<number, CandlestickPoint & { count: number }> {
        return input.getCandlestickBuckets();
    },
    set candlestickBuckets(value: Map<number, CandlestickPoint & { count: number }>) {
        input.setCandlestickBuckets(value);
    },
    get lastResolvedCandlestickIntervalMs() {
        return input.getLastResolvedCandlestickIntervalMs();
    },
    set lastResolvedCandlestickIntervalMs(value: number | undefined) {
        input.setLastResolvedCandlestickIntervalMs(value);
    },
    buildHistoryRequestParameters: (): HistoryRequestParameters => input.buildHistoryRequestParameters(),
    getEffectiveCandlestickIntervalMs: (): number => input.getEffectiveCandlestickIntervalMs(),
    clampHistoryPoints: (value: number, min?: number): number => input.clampHistoryPoints(value, min),
    runHistoryFetch: (parameters, onResolve): Promise<void> => input.runHistoryFetch(parameters, onResolve),
    buildHistorySeriesFromPayload: (payload: JsonValue): HistorySeriesResult | null => input.buildHistorySeriesFromPayload(payload),
    mergeSeriesByTimestamp: <T extends { timestamp: number }>(series: readonly T[], existing: readonly T[]): T[] => input.mergeSeriesByTimestamp(series, existing),
    trimCandlestickData: (force: boolean): boolean => input.trimCandlestickData(force),
    trimHistoryData: (force: boolean): boolean => input.trimHistoryData(force),
    updateMainChart: (): void => input.updateMainChart()
});

export { createHardwareHistoryChunkHost, createHardwareHistoryMetadataHost, createHardwareHistoryRealtimeHost };
