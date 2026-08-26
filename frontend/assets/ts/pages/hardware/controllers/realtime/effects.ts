/* SoAI - Hardware page realtime effects [frontend/assets/ts/pages/hardware/controllers/realtime/effects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import { APIError } from '@core/apiError.ts';
import type { UnsubscribeTarget } from '@core/realtime/streammanager/service.ts';
import { createAbortError, isAbortError, throwIfAborted } from '@core/errors/abort.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { readCoercedFiniteNumberOrNullValue } from '@core/types/numberCoercionReaders.ts';
import { requestWebSocketSnapshotRecord } from '@core/websocketclient/snapshotPayload.ts';
import { serializeHardwareHistoryRequest } from '@core/api/contracts/hardwareRequestContracts.ts';
import type { StreamRuntimeOwners } from '@core/realtime/streammanager/public.ts';
import type { PeekStreamManagerOptions } from '@core/lifecyclemodel/types.ts';
import { hasFunctionProperty, isArray, isNullOrUndefined, isObject } from '@core/typeGuards.ts';
import type { HistoryStateManager } from '@features/hardware/public.ts';
import { STR_OHLC } from '@pages/hardware/contracts/hardwarePageSupport.ts';
import { buildHardwareHistorySeries, buildHistoryRequestParameters, isCandlestickActive, trimCandlestickData, trimHistoryData, type HardwareHistoryContext } from '@pages/hardware/controllers/data/effects.ts';
import type { HardwareDataController } from '@pages/hardware/controllers/dataController.ts';
import { getHistoryChunkHost, getHistoryMetadataHost, getHistoryRealtimeHost, type HardwareHistoryHostCache, type HardwareHistoryHostDependencies } from '@pages/hardware/controllers/realtime/service.ts';
import type { HardwareHistoryAbortHandle, HardwareHistoryCloseHandle, HardwareHistoryStreamHandle, HardwareHistoryStreamState, HardwareHistoryUnsubscribeHandle } from '@pages/hardware/controllers/realtime/state.ts';
import { beginMainChartLoad, completeMainChartLoad, updateMainChart, type HardwareChartLoadToken } from '@pages/hardware/controllers/render/effects.ts';
import { refreshChartControls } from '@pages/hardware/controllers/render/events.ts';
import { setHistoryStatus } from '@pages/hardware/controllers/render/rendering.ts';
import type { HardwareRenderController } from '@pages/hardware/controllers/renderController.ts';
import { formatHistoryErrorMessage } from '@pages/hardware/mappers/mappers.ts';
import { applyHardwareHistoryRealtimeUpdate, parseHardwareHistoryResponseMetadata } from '@pages/hardware/realtime/hardwareHistoryRealtimeUpdate.ts';
import { fetchHardwareHistoryChunk } from '@pages/hardware/services/history/hardwareHistoryChunkFetch.ts';
import type { HardwarePageState } from '@pages/hardware/state/state.ts';
import type { HardwarePageSnapshot, ModuleLoggerFunctionValue } from '@pages/hardware/types.ts';

type HardwareHistoryStreamDependencies = {
    state: HardwarePageState;
    dataController: HardwareDataController;
    renderController: HardwareRenderController;
    historyStateManager: HistoryStateManager;
    logger: ModuleLoggerFunctionValue;
    runWithBoundary: <T>(boundaryKey: string, functionValue: () => Promise<T>) => Promise<T>;
    handleError: (error: Error, message: string, options?: { notify?: boolean }) => void;
    prepareRealtimeResources: (options: { signal?: AbortSignal | undefined }) => Promise<void>;
    peekStreamManager: (options: PeekStreamManagerOptions) => StreamRuntimeOwners | null;
    historyHostDependencies: HardwareHistoryHostDependencies;
};

type HardwareHistoryRuntime = {
    historyState: HardwareHistoryStreamState;
    historyHostCache: HardwareHistoryHostCache;
};
const buildHistoryContext = (dependencies: HardwareHistoryStreamDependencies): HardwareHistoryContext => ({
    state: dependencies.state,
    chartOhlc: dependencies.historyHostDependencies.chartOhlc,
    historyControlsManager: dependencies.historyHostDependencies.historyControlsManager,
    getSelectedHistoryTarget: () => dependencies.dataController.getSelectedHistoryTarget(),
    resolveSupportedHistoryComponent: (component: JsonValue) => dependencies.dataController.resolveSupportedHistoryComponent(component)
});
const startHistoryStream = async (dependencies: HardwareHistoryStreamDependencies, runtime: HardwareHistoryRuntime, { resetView = false, signal = null }: { resetView?: boolean; signal?: AbortSignal | null | undefined } = {}): Promise<void> => {
    return dependencies.runWithBoundary('hardware:startHistoryStream', async () => {
        const streamState = runtime.historyState;
        const checkAbort = (): void => {
            throwIfAborted(signal);
            if (streamState.historyStreamAbortController?.signal?.aborted) {
                throw createAbortError();
            }
        };

        await dependencies.prepareRealtimeResources({ signal: signal ?? undefined });
        checkAbort();

        const capabilities = dependencies.state.hardwareCapabilities;
        if (!isObject(capabilities)) {
            throw new TypeError('Hardware capabilities are required before starting history stream');
        }
        const historyConfig = capabilities.historyConfig;
        if (!isObject(historyConfig)) {
            throw new TypeError('Hardware capabilities must include historyConfig');
        }
        await refreshChartControls(dependencies.renderController.filtersContext);
        checkAbort();
        if (historyConfig['enabled'] !== true) {
            setHistoryStatus(dependencies.renderController.actionsContext, dependencies.renderController.renderCache, i18n.t('hardware.cards.history.disabledByBackend'), 'info');
            return;
        }

        cleanupHistoryStream(dependencies, runtime);
        streamState.historyStreamAbortController = new AbortController();
        streamState.activeHistoryRequest = null;
        streamState.historyStateBackup = dependencies.historyStateManager.snapshot(dependencies.state);
        streamState.historyStreamInitialized = false;
        setHistoryStatus(dependencies.renderController.actionsContext, dependencies.renderController.renderCache, null);
        const chartLoadToken = beginMainChartLoad(dependencies.renderController.chartContext);
        const token = Symbol('hardware-history');
        streamState.historyRequestToken = token;
        checkAbort();
        const historyContext = buildHistoryContext(dependencies);
        const parameters = buildHistoryRequestParameters(historyContext);
        streamState.activeHistoryRequest = { token, parameters: { ...parameters } };
        streamState.lastHistoryRequest = { resource: 'hardware.history', ...parameters };
        checkAbort();
        try {
            const data = await requestWebSocketSnapshotRecord('hardware.history', serializeHardwareHistoryRequest(parameters));
            checkAbort();
            if (token !== streamState.historyRequestToken) return;
            streamState.historyStreamId = null;
            await handleHistoryInitial(dependencies, runtime, data, token, { resetView, chartLoadToken });
        } catch (error) {
            const runtimeError = ensureError(error);
            handleHistoryStreamError(dependencies, runtime, runtimeError, token, chartLoadToken);
        }
    });
};
const handleHistoryInitial = async (dependencies: HardwareHistoryStreamDependencies, runtime: HardwareHistoryRuntime, data: JsonValue, token: symbol | null, options: { resetView?: boolean | undefined; chartLoadToken: HardwareChartLoadToken }): Promise<void> => {
    if (token !== runtime.historyState.historyRequestToken) return;
    const resetView = options.resetView ?? false;
    runtime.historyState.historyStreamInitialized = true;
    runtime.historyState.historyStateBackup = null;
    setHistoryStatus(dependencies.renderController.actionsContext, dependencies.renderController.renderCache, null);
    const historyContext = buildHistoryContext(dependencies);
    const result = buildHardwareHistorySeries(historyContext, data);
    if (!result) {
        updateMainChart(dependencies.renderController.chartContext, { resetView });
        completeMainChartLoad(dependencies.renderController.chartContext, options.chartLoadToken);
        return;
    }
    const { series, metadata, type } = result;
    const isOhlc = type === STR_OHLC;
    if (!isObject(metadata)) throw new TypeError('history result metadata must be an object');
    if (!metadata.aggregation || typeof metadata.aggregation !== 'string') {
        throw new TypeError('history result metadata.aggregation is required');
    }
    const effective = { ...metadata, aggregation: isOhlc ? STR_OHLC : metadata.aggregation };
    if (isOhlc) {
        if (!isArray(series)) throw new TypeError('candlestick series must be an array');
        dependencies.state.candlestickData = [...series];
        dependencies.state.candlestickMetadata = effective;
        const intervalMs = readCoercedFiniteNumberOrNullValue(effective.intervalMs);
        if (intervalMs === null || intervalMs <= 0) {
            throw new TypeError('history result metadata.intervalMs must be a positive number');
        }
        dependencies.state.lastResolvedCandlestickIntervalMs = Math.max(1, Math.round(intervalMs));
        const intervalMin = Math.max(1, Math.round(intervalMs / 60_000));
        if (intervalMin !== dependencies.state.candlestickIntervalMinutes) {
            dependencies.state.candlestickIntervalMinutes = intervalMin;
            await refreshChartControls(dependencies.renderController.filtersContext, { range: false, candles: true });
        }
        trimCandlestickData(dependencies.state, true);
    } else {
        if (!isArray(series)) throw new TypeError('line series must be an array');
        dependencies.state.historyData = [...series];
        dependencies.state.historyMetadata = effective;
        trimHistoryData(dependencies.state, true);
    }
    dependencies.state.lineHistoryExhausted = false;
    dependencies.state.candlestickHistoryExhausted = false;
    parseHardwareHistoryResponseMetadata(getHistoryMetadataHost(runtime.historyHostCache, dependencies.historyHostDependencies), metadata);
    updateMainChart(dependencies.renderController.chartContext, { resetView });
    completeMainChartLoad(dependencies.renderController.chartContext, options.chartLoadToken);
};
const handleHistoryUpdate = (dependencies: HardwareHistoryStreamDependencies, runtime: HardwareHistoryRuntime, data: HardwarePageSnapshot, token: symbol | null = runtime.historyState.historyRequestToken): void => {
    applyHardwareHistoryRealtimeUpdate(getHistoryRealtimeHost(runtime.historyHostCache, dependencies.historyHostDependencies), data, token);
};
const handleHistoryStreamError = (dependencies: HardwareHistoryStreamDependencies, runtime: HardwareHistoryRuntime, error: Error, token: symbol | null, chartLoadToken: HardwareChartLoadToken): void => {
    const streamState = runtime.historyState;
    if (token !== streamState.historyRequestToken) return;
    if (isAbortError(error)) {
        cleanupHistoryStream(dependencies, runtime);
        if (token === streamState.historyRequestToken) streamState.historyRequestToken = streamState.activeHistoryRequest = null;
        return;
    }
    dependencies.logger('error', 'History stream failed', error);
    if (!streamState.historyStreamInitialized && streamState.historyStateBackup) {
        dependencies.historyStateManager.restore(dependencies.state, streamState.historyStateBackup);
        streamState.historyStateBackup = null;
        updateMainChart(dependencies.renderController.chartContext, { resetView: false });
        completeMainChartLoad(dependencies.renderController.chartContext, chartLoadToken);
    }
    setHistoryStatus(dependencies.renderController.actionsContext, dependencies.renderController.renderCache, formatHistoryErrorMessage(error), 'error');
    const status = error instanceof APIError ? error.status : 0;
    if ([400, 413, 422, 429, 500].includes(status)) {
        dependencies.state.historyApiPointCap = Math.max(150, Math.floor((dependencies.state.historyApiPointCap || 2000) * 0.6));
    }
    cleanupHistoryStream(dependencies, runtime);
    streamState.historyRequestToken = streamState.activeHistoryRequest = null;
    dependencies.handleError(error, i18n.t('hardware.errors.historyInitFailed'), { notify: true });
};
const handleChartHistoricalRequest = (dependencies: HardwareHistoryStreamDependencies, runtime: HardwareHistoryRuntime, timestamp: number): Promise<void> => {
    if (!Number.isFinite(timestamp)) return (async (): Promise<void> => undefined)();
    return fetchHardwareHistoryChunk(getHistoryChunkHost(runtime.historyHostCache, dependencies.historyHostDependencies), isCandlestickActive(dependencies.state), timestamp);
};
const cleanupHistoryStream = (dependencies: HardwareHistoryStreamDependencies, runtime: HardwareHistoryRuntime): void => {
    const streamState = runtime.historyState;
    const handle = streamState.historyStreamId;
    if (!handle) return;
    const isUnsubscribeHandle = (value: HardwareHistoryStreamHandle | undefined): value is HardwareHistoryUnsubscribeHandle => isObject(value) && hasFunctionProperty(value, 'unsubscribe');
    const isCloseHandle = (value: HardwareHistoryStreamHandle | undefined): value is HardwareHistoryCloseHandle => isObject(value) && hasFunctionProperty(value, 'close');
    const isAbortHandle = (value: HardwareHistoryStreamHandle | undefined): value is HardwareHistoryAbortHandle => isObject(value) && hasFunctionProperty(value, 'abort');
    const isManagerUnsubscribeTarget = (value: HardwareHistoryStreamHandle | undefined): value is UnsubscribeTarget => typeof value === 'function' || typeof value === 'string' || isNullOrUndefined(value) || isUnsubscribeHandle(value) || isCloseHandle(value);

    if (isUnsubscribeHandle(handle)) {
        handle.unsubscribe();
    } else if (isAbortHandle(handle)) {
        handle.abort();
    } else {
        const manager = dependencies.peekStreamManager({ required: false });
        if (manager && isManagerUnsubscribeTarget(handle)) {
            manager.subscriptions.unsubscribe(handle);
        }
    }
    streamState.historyStreamId = null;
    if (streamState.historyStreamAbortController) {
        streamState.historyStreamAbortController.abort();
        streamState.historyStreamAbortController = null;
    }
    streamState.historyStreamInitialized = false;
    streamState.historyRequestToken = null;
    streamState.activeHistoryRequest = null;
};
export { cleanupHistoryStream, handleChartHistoricalRequest, handleHistoryInitial, handleHistoryStreamError, handleHistoryUpdate, startHistoryStream };
export type { HardwareHistoryStreamDependencies, HardwareHistoryRuntime };
