/* SoAI - Hardware page realtime service [frontend/assets/ts/pages/hardware/controllers/realtime/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import { decodeHardwareHistory, type HardwareHistoryResponse } from '@core/api/contracts/hardwareContracts.ts';
import { requestWebSocketSnapshotRecord } from '@core/websocketclient/snapshotPayload.ts';
import { serializeHardwareHistoryRequest } from '@core/api/contracts/hardwareRequestContracts.ts';
import type { CandlestickPoint, HistoryChartControlsManager } from '@features/charts/public.ts';
import type { ChartOhlcContract } from '@pages/hardware/contracts/contracts.ts';
import { buildHardwareHistorySeries, buildHistoryRequestParameters, isCandlestickActive, resolveHistoryPointLimit, trimCandlestickData, trimHistoryData, updateRealtimeCandlestick, type HardwareHistoryContext } from '@pages/hardware/controllers/data/effects.ts';
import type { HardwareDataController } from '@pages/hardware/controllers/dataController.ts';
import { createHardwareHistoryMetadataHost, createHardwareHistoryRealtimeHost } from '@pages/hardware/controllers/hardwarehistoryhostbuilders/service.ts';
import { applyChartDataLimits, buildHardwareDisplaySeries, updateMainChart } from '@pages/hardware/controllers/render/effects.ts';
import type { HardwareRenderController } from '@pages/hardware/controllers/renderController.ts';
import { getMetricKey, getMetricLabel } from '@pages/hardware/mappers/mappers.ts';
import type { HardwareHistoryMetadataHost, HardwareHistoryRealtimeHost } from '@pages/hardware/realtime/hardwareHistoryRealtimeUpdate.ts';
import type { HardwareOlderHistoryHost } from '@pages/hardware/services/history/hardwareOlderHistoryPage.ts';
import type { HardwarePageState } from '@pages/hardware/state/state.ts';
import type { HistoryDataPoint, HistoryMetadata, HistoryRequestParameters } from '@pages/hardware/types.ts';

type HardwareHistoryHostCache = {
    metadataHost: HardwareHistoryMetadataHost | null;
    realtimeHost: HardwareHistoryRealtimeHost | null;
};

type HardwareHistoryHostDependencies = {
    state: HardwarePageState;
    dataController: HardwareDataController;
    renderController: HardwareRenderController;
    chartOhlc: ChartOhlcContract;
    historyControlsManager: HistoryChartControlsManager;
    getClearedThroughMs: () => number;
    acceptRealtimeTimestamp: (timestamp: number) => boolean;
};

const createHardwareHistoryHostCache = (): HardwareHistoryHostCache => ({
    metadataHost: null,
    realtimeHost: null
});

const buildHistoryContext = (dependencies: HardwareHistoryHostDependencies): HardwareHistoryContext => ({
    state: dependencies.state,
    chartOhlc: dependencies.chartOhlc,
    historyControlsManager: dependencies.historyControlsManager,
    getSelectedHistoryTarget: () => dependencies.dataController.getSelectedHistoryTarget(),
    resolveSupportedHistoryComponent: (component: JsonValue) => dependencies.dataController.resolveSupportedHistoryComponent(component)
});

const getHistoryMetadataHost = (cache: HardwareHistoryHostCache, dependencies: HardwareHistoryHostDependencies): HardwareHistoryMetadataHost => {
    if (!cache.metadataHost) {
        cache.metadataHost = createHardwareHistoryMetadataHost({
            chartOhlc: dependencies.chartOhlc,
            getMonitoringIntervalMs: (): number => dependencies.state.monitoringIntervalMs,
            setMonitoringIntervalMs: (value: number): void => {
                dependencies.state.monitoringIntervalMs = value;
            },
            getHistoryApiPointCap: (): number => dependencies.state.historyApiPointCap,
            setHistoryApiPointCap: (value: number): void => {
                dependencies.state.historyApiPointCap = value;
            },
            getMaxHistoryPoints: (): number => dependencies.state.maxHistoryPoints,
            setMaxHistoryPoints: (value: number): void => {
                dependencies.state.maxHistoryPoints = value;
            },
            getChartHardLimit: (): number => dependencies.state.chartHardLimit,
            getMaxRetentionMinutes: (): number | null => dependencies.state.maxRetentionMinutes,
            getCurrentHistoryPointBudget: (): number => dependencies.state.currentHistoryPointBudget,
            setCurrentHistoryPointBudget: (value: number): void => {
                dependencies.state.currentHistoryPointBudget = value;
            },
            applyChartDataLimits: (): void => applyChartDataLimits(dependencies.renderController.chartContext),
            resolveHistoryPointLimit: (): number => resolveHistoryPointLimit(dependencies.state)
        });
    }
    return cache.metadataHost;
};

const getHistoryRealtimeHost = (cache: HardwareHistoryHostCache, dependencies: HardwareHistoryHostDependencies): HardwareHistoryRealtimeHost => {
    if (!cache.realtimeHost) {
        const context = buildHistoryContext(dependencies);
        cache.realtimeHost = createHardwareHistoryRealtimeHost({
            getClearedThroughMs: (): number => dependencies.getClearedThroughMs(),
            chartOhlc: dependencies.chartOhlc,
            getMetricKey: (): string | undefined => getMetricKey(dependencies.state.selectedMetric, dependencies.dataController.getSelectedHistoryTarget().type),
            getSelectedHistoryTarget: () => dependencies.dataController.getSelectedHistoryTarget(),
            getHistoryData: (): HistoryDataPoint[] => dependencies.state.historyData,
            getHistoryMetadata: (): HistoryMetadata | null => dependencies.state.historyMetadata,
            acceptRealtimeTimestamp: (timestamp: number): boolean => dependencies.acceptRealtimeTimestamp(timestamp),
            trimHistoryData: (force?: boolean): boolean => trimHistoryData(dependencies.state, force),
            getMainChart: () => dependencies.state.mainChart,
            isCandlestickActive: (): boolean => isCandlestickActive(dependencies.state),
            updateRealtimeCandlestick: (timestamp: JsonValue, value: JsonValue) => updateRealtimeCandlestick(context, timestamp, value),
            trimCandlestickData: (force?: boolean): boolean => trimCandlestickData(dependencies.state, force),
            getCandlestickData: (): CandlestickPoint[] => dependencies.state.candlestickData,
            updateMainChart: (options?: { resetView?: boolean }): void => updateMainChart(dependencies.renderController.chartContext, options),
            getMetricLabel: (): string => getMetricLabel(dependencies.state)
        });
    }
    return cache.realtimeHost;
};

const createHardwareOlderHistoryHost = (dependencies: HardwareHistoryHostDependencies): HardwareOlderHistoryHost => {
    const context = buildHistoryContext(dependencies);
    return {
        state: dependencies.state,
        buildHistoryRequestParameters: (): HistoryRequestParameters => buildHistoryRequestParameters(context),
        requestHistory: (parameters: HistoryRequestParameters, signal: AbortSignal): Promise<HardwareHistoryResponse> => requestHardwareHistory(parameters, signal),
        buildHistorySeriesFromPayload: (payload: HardwareHistoryResponse) => buildHardwareHistorySeries(context, payload),
        buildDisplaySeries: (source: readonly HistoryDataPoint[], candlestick: boolean) => buildHardwareDisplaySeries(dependencies.renderController.chartContext, source, candlestick)
    };
};

const requestHardwareHistory = async (parameters: HistoryRequestParameters, signal: AbortSignal): Promise<HardwareHistoryResponse> => decodeHardwareHistory(await requestWebSocketSnapshotRecord('hardware.history', serializeHardwareHistoryRequest(parameters), { signal }));

export { createHardwareHistoryHostCache, createHardwareOlderHistoryHost, getHistoryMetadataHost, getHistoryRealtimeHost, requestHardwareHistory };
export type { HardwareHistoryHostCache, HardwareHistoryHostDependencies };
