/* SoAI - Hardware page realtime service [frontend/assets/ts/pages/hardware/controllers/realtime/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import { isAbortError } from '@core/errors/abort.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { requestWebSocketSnapshotRecord } from '@core/websocketclient/snapshotPayload.ts';
import { serializeHardwareHistoryRequest } from '@core/api/contracts/hardwareRequestContracts.ts';
import type { CandlestickPoint, HistoryChartControlsManager } from '@features/charts/public.ts';
import type { ChartDataTransformsContract, ChartOhlcContract } from '@pages/hardware/contracts/contracts.ts';
import { buildHardwareHistorySeries, buildHistoryRequestParameters, clampHistoryPoints, getEffectiveCandlestickIntervalMs, isCandlestickActive, resolveHistoryPointLimit, trimCandlestickData, trimHistoryData, updateRealtimeCandlestick, type HardwareHistoryContext } from '@pages/hardware/controllers/data/effects.ts';
import type { HardwareDataController } from '@pages/hardware/controllers/dataController.ts';
import { createHardwareHistoryChunkHost, createHardwareHistoryMetadataHost, createHardwareHistoryRealtimeHost } from '@pages/hardware/controllers/hardwarehistoryhostbuilders/service.ts';
import type { HardwareHistoryStreamState } from '@pages/hardware/controllers/realtime/state.ts';
import { applyChartDataLimits, updateMainChart } from '@pages/hardware/controllers/render/effects.ts';
import type { HardwareRenderController } from '@pages/hardware/controllers/renderController.ts';
import { getMetricKey, getMetricLabel } from '@pages/hardware/mappers/mappers.ts';
import type { HardwareHistoryMetadataHost, HardwareHistoryRealtimeHost } from '@pages/hardware/realtime/hardwareHistoryRealtimeUpdate.ts';
import type { HardwareHistoryChunkHost } from '@pages/hardware/services/history/hardwareHistoryChunkFetch.ts';
import { mergeSeriesByTimestamp } from '@pages/hardware/state/history/hardwareSeriesBuilders.ts';
import type { HardwarePageState } from '@pages/hardware/state/state.ts';
import type { HistoryDataPoint, HistoryMetadata, HistoryRequestParameters, ModuleLoggerFunctionValue } from '@pages/hardware/types.ts';

type HardwareHistoryHostCache = {
    metadataHost: HardwareHistoryMetadataHost | null;
    realtimeHost: HardwareHistoryRealtimeHost | null;
    chunkHost: HardwareHistoryChunkHost | null;
};

type HardwareHistoryHostDependencies = {
    state: HardwarePageState;
    dataController: HardwareDataController;
    renderController: HardwareRenderController;
    chartDataTransforms: ChartDataTransformsContract;
    chartOhlc: ChartOhlcContract;
    historyControlsManager: HistoryChartControlsManager;
    getHistoryRequestToken: () => symbol | null;
    runHistoryFetch: (parameters: HistoryRequestParameters, onResolve: (result: JsonValue) => Promise<void>) => Promise<void>;
};

type HardwareHistoryFetchDependencies = {
    logger: ModuleLoggerFunctionValue;
};

const createHardwareHistoryHostCache = (): HardwareHistoryHostCache => ({
    metadataHost: null,
    realtimeHost: null,
    chunkHost: null
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
            getHistoryRequestToken: (): symbol | null => dependencies.getHistoryRequestToken(),
            chartOhlc: dependencies.chartOhlc,
            getMetricKey: (): string | undefined => getMetricKey(dependencies.state.selectedMetric, dependencies.dataController.getSelectedHistoryTarget().type),
            getSelectedHistoryTarget: () => dependencies.dataController.getSelectedHistoryTarget(),
            getHistoryData: (): HistoryDataPoint[] => dependencies.state.historyData,
            chartDataTransforms: dependencies.chartDataTransforms,
            getMonitoringIntervalMs: (): number => dependencies.state.monitoringIntervalMs,
            resolveHistoryPointLimit: (): number => resolveHistoryPointLimit(dependencies.state),
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

const getHistoryChunkHost = (cache: HardwareHistoryHostCache, dependencies: HardwareHistoryHostDependencies): HardwareHistoryChunkHost => {
    if (!cache.chunkHost) {
        const context = buildHistoryContext(dependencies);
        cache.chunkHost = createHardwareHistoryChunkHost({
            getCandlestickHistoryExhausted: (): boolean => dependencies.state.candlestickHistoryExhausted,
            setCandlestickHistoryExhausted: (value: boolean): void => {
                dependencies.state.candlestickHistoryExhausted = value;
            },
            getLineHistoryExhausted: (): boolean => dependencies.state.lineHistoryExhausted,
            setLineHistoryExhausted: (value: boolean): void => {
                dependencies.state.lineHistoryExhausted = value;
            },
            getCandlestickData: (): CandlestickPoint[] => dependencies.state.candlestickData,
            setCandlestickData: (value: CandlestickPoint[]): void => {
                dependencies.state.candlestickData = value;
            },
            getHistoryData: (): HistoryDataPoint[] => dependencies.state.historyData,
            setHistoryData: (value: HistoryDataPoint[]): void => {
                dependencies.state.historyData = value;
            },
            getCurrentHistoryPointBudget: (): number => dependencies.state.currentHistoryPointBudget,
            getTimeRange: (): number => dependencies.state.timeRange,
            getMonitoringIntervalMs: (): number => dependencies.state.monitoringIntervalMs,
            getHistoryMetadata: (): HistoryMetadata | null => dependencies.state.historyMetadata,
            setHistoryMetadata: (value: HistoryMetadata | null): void => {
                dependencies.state.historyMetadata = value;
            },
            getCandlestickMetadata: (): HistoryMetadata | null => dependencies.state.candlestickMetadata,
            setCandlestickMetadata: (value: HistoryMetadata | null): void => {
                dependencies.state.candlestickMetadata = value;
            },
            getCandlestickBuckets: (): Map<number, CandlestickPoint & { count: number }> => dependencies.state.candlestickBuckets,
            setCandlestickBuckets: (value: Map<number, CandlestickPoint & { count: number }>): void => {
                dependencies.state.candlestickBuckets = value;
            },
            getLastResolvedCandlestickIntervalMs: (): number | undefined => dependencies.state.lastResolvedCandlestickIntervalMs,
            setLastResolvedCandlestickIntervalMs: (value: number | undefined): void => {
                dependencies.state.lastResolvedCandlestickIntervalMs = value;
            },
            buildHistoryRequestParameters: (): HistoryRequestParameters => buildHistoryRequestParameters(context),
            getEffectiveCandlestickIntervalMs: (): number => getEffectiveCandlestickIntervalMs(context),
            clampHistoryPoints: (value: number, min?: number): number => clampHistoryPoints(dependencies.state, value, min),
            runHistoryFetch: (parameters, onResolve): Promise<void> => dependencies.runHistoryFetch(parameters, onResolve),
            buildHistorySeriesFromPayload: (payload: JsonValue) => buildHardwareHistorySeries(context, payload),
            mergeSeriesByTimestamp: <T extends { timestamp: number }>(series: readonly T[], existing: readonly T[]): T[] => mergeSeriesByTimestamp(series, existing),
            trimCandlestickData: (force: boolean): boolean => trimCandlestickData(dependencies.state, force),
            trimHistoryData: (force: boolean): boolean => trimHistoryData(dependencies.state, force),
            updateMainChart: (): void => updateMainChart(dependencies.renderController.chartContext)
        });
    }
    return cache.chunkHost;
};

const runHistoryFetch = async (dependencies: HardwareHistoryFetchDependencies, historyState: HardwareHistoryStreamState, parameters: HistoryRequestParameters, onResolve: (result: JsonValue) => Promise<void>): Promise<void> => {
    const requestToken = Symbol('hardware-history-fetch');
    historyState.historyFetchRequestToken = requestToken;
    try {
        const result = await requestWebSocketSnapshotRecord('hardware.history', serializeHardwareHistoryRequest(parameters));
        if (historyState.historyFetchRequestToken !== requestToken) {
            return;
        }
        await onResolve(result);
        if (historyState.historyFetchRequestToken === requestToken) {
            historyState.historyFetchRequestToken = null;
        }
    } catch (error) {
        if (historyState.historyFetchRequestToken === requestToken) {
            historyState.historyFetchRequestToken = null;
        }
        const runtimeError = ensureError(error);
        if (isAbortError(runtimeError)) return;
        dependencies.logger('warn', 'History snapshot fetch failed', runtimeError);
        throw runtimeError;
    }
};

export { createHardwareHistoryHostCache, getHistoryChunkHost, getHistoryMetadataHost, getHistoryRealtimeHost, runHistoryFetch };
export type { HardwareHistoryHostCache, HardwareHistoryHostDependencies, HardwareHistoryFetchDependencies };
