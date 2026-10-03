/* SoAI - Hardware page realtime effects [frontend/assets/ts/pages/hardware/controllers/realtime/effects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import { APIError } from '@core/apiError.ts';
import type { HardwareHistoryResponse } from '@core/api/contracts/hardwareContracts.ts';
import { isAbortError, throwIfAborted } from '@core/errors/abort.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { serverEpochMs } from '@core/time/clock.ts';
import { readCoercedFiniteNumberOrNullValue } from '@core/types/numberCoercionReaders.ts';
import { isArray, isObject } from '@core/typeGuards.ts';
import { FILTER_TYPES, followHistoryRange, resolveHistoryPagePoints, resolveHistoryResolutionChange, settleHistoryAvailability, type HistoryAvailabilitySettlement, type HistoryPager, type HistoryRangeAvailability, type HistoryResolutionFollower, type HistoryResolutionWindow } from '@features/charts/public.ts';
import type { HistoryStateManager } from '@features/hardware/public.ts';
import { HARDWARE_ACTION_HISTORY_RETRY } from '@pages/hardware/actions.ts';
import { STR_OHLC } from '@pages/hardware/contracts/hardwarePageSupport.ts';
import { buildHardwareHistorySeries, buildHistoryAvailabilityRequestParameters, buildHistoryRequestParameters, getHistoryPointBudgetConfig, isCandlestickActive, resolveHardwareHistoryIntervalMs, resolveHistoryRequestKey, resolveHistorySeriesKey, resolveHistorySeriesMetric, trimCandlestickData, trimHistoryData, type HardwareHistoryContext } from '@pages/hardware/controllers/data/effects.ts';
import type { HardwareDataController } from '@pages/hardware/controllers/dataController.ts';
import { getHistoryMetadataHost, getHistoryRealtimeHost, requestHardwareHistory, type HardwareHistoryHostCache, type HardwareHistoryHostDependencies } from '@pages/hardware/controllers/realtime/service.ts';
import type { HardwareHistorySession } from '@pages/hardware/controllers/realtime/state.ts';
import { beginMainChartLoad, completeMainChartLoad, updateMainChart, type HardwareChartLoadToken } from '@pages/hardware/controllers/render/effects.ts';
import { refreshChartControls } from '@pages/hardware/controllers/render/events.ts';
import { setHistoryStatus } from '@pages/hardware/controllers/render/rendering.ts';
import type { HardwareRenderController } from '@pages/hardware/controllers/renderController.ts';
import { formatHistoryErrorMessage } from '@pages/hardware/mappers/mappers.ts';
import { applyHardwareHistoryRealtimeUpdate, parseHardwareHistoryResponseMetadata } from '@pages/hardware/realtime/hardwareHistoryRealtimeUpdate.ts';
import type { HardwarePageState } from '@pages/hardware/state/state.ts';
import type { HardwarePageSnapshot, ModuleLoggerFunctionValue } from '@pages/hardware/types.ts';

type HardwareHistoryStreamDependencies = {
    state: HardwarePageState;
    dataController: HardwareDataController;
    renderController: HardwareRenderController;
    historyStateManager: HistoryStateManager;
    rangeAvailability: HistoryRangeAvailability;
    logger: ModuleLoggerFunctionValue;
    runWithBoundary: <T>(boundaryKey: string, functionValue: () => Promise<T>) => Promise<T>;
    handleError: (error: Error, message: string, options?: { notify?: boolean }) => void;
    prepareRealtimeResources: (options: { signal?: AbortSignal | undefined }) => Promise<void>;
    persistPageControls: () => void;
    historyHostDependencies: HardwareHistoryHostDependencies;
};

type HardwareHistoryRuntime = {
    session: HardwareHistorySession;
    historyHostCache: HardwareHistoryHostCache;
    pager: HistoryPager;
    resolution: HistoryResolutionFollower;
};

const invalidateHistoryRuntime = (runtime: HardwareHistoryRuntime): void => {
    runtime.session.invalidate();
    runtime.resolution.cancel();
    runtime.pager.reset();
};

const buildHistoryContext = (dependencies: HardwareHistoryStreamDependencies): HardwareHistoryContext => ({
    state: dependencies.state,
    chartOhlc: dependencies.historyHostDependencies.chartOhlc,
    historyControlsManager: dependencies.historyHostDependencies.historyControlsManager,
    getSelectedHistoryTarget: () => dependencies.dataController.getSelectedHistoryTarget(),
    resolveSupportedHistoryComponent: (component: JsonValue) => dependencies.dataController.resolveSupportedHistoryComponent(component)
});

const setHistoryLoadStatus = (dependencies: HardwareHistoryStreamDependencies, message: string | null = null, tone: string | null = null, retryAction: string | null = null): void => {
    setHistoryStatus(dependencies.renderController.actionsContext, dependencies.renderController.renderCache, message, tone, retryAction);
};

const settleHardwareHistoryAvailability = (dependencies: HardwareHistoryStreamDependencies, historyContext: HardwareHistoryContext, response: HardwareHistoryResponse, requestedRange: number, isCurrent: () => boolean): Promise<HistoryAvailabilitySettlement> => {
    return settleHistoryAvailability({
        rangeAvailability: dependencies.rangeAvailability,
        seriesKey: resolveHistorySeriesKey(dependencies.state, historyContext.getSelectedHistoryTarget()),
        availability: response.metadata.availability,
        loggingIntervalMs: response.metadata.loggingIntervalMs,
        requestedRange,
        getTimeRange: () => dependencies.state.timeRange,
        syncTimeRange: () => refreshChartControls(dependencies.renderController.filtersContext),
        isCurrent
    });
};

const startHistoryStream = async (dependencies: HardwareHistoryStreamDependencies, runtime: HardwareHistoryRuntime, { resetView = false, signal = null }: { resetView?: boolean; signal?: AbortSignal | null | undefined } = {}): Promise<void> => {
    return dependencies.runWithBoundary('hardware:startHistoryStream', async () => {
        await dependencies.prepareRealtimeResources({ signal: signal ?? undefined });
        throwIfAborted(signal);
        const historyConfig = dependencies.state.hardwareCapabilities?.historyConfig;
        if (!isObject(historyConfig)) {
            throw new TypeError('Hardware capabilities must include historyConfig');
        }
        const session = runtime.session;
        invalidateHistoryRuntime(runtime);
        if (historyConfig['enabled'] !== true) {
            await refreshChartControls(dependencies.renderController.filtersContext);
            setHistoryLoadStatus(dependencies, i18n.t('hardware.cards.history.disabledByBackend'), 'info');
            return;
        }
        const lease = session.lifecycle.request.begin();
        session.lifecycle.beginRealtimeCapture();
        const historyContext = buildHistoryContext(dependencies);
        const readRequestKey = (): string => resolveHistoryRequestKey(dependencies.state, historyContext.getSelectedHistoryTarget());
        const requestKey = readRequestKey();
        const isCurrent = (): boolean => session.lifecycle.request.isCurrent(lease) && signal?.aborted !== true && readRequestKey() === requestKey;
        session.backup = dependencies.historyStateManager.snapshot(dependencies.state);
        const chartLoadToken = beginMainChartLoad(dependencies.renderController.chartContext, { presentation: resetView });
        if (resetView) setHistoryLoadStatus(dependencies, i18n.t('charts.loadingState'), 'loading');
        const availabilityMetric = resolveHistorySeriesMetric(dependencies.state, historyContext.getSelectedHistoryTarget());
        try {
            await refreshChartControls(dependencies.renderController.filtersContext);
            for (let attempt = 0; attempt < 4 && isCurrent(); attempt += 1) {
                const requestedRange = dependencies.state.timeRange;
                const parameters = buildHistoryRequestParameters(historyContext);
                const response = await requestHardwareHistory(availabilityMetric === undefined ? parameters : { ...parameters, availabilityMetric }, lease.signal);
                if (!isCurrent()) return;
                const settlement = await settleHardwareHistoryAvailability(dependencies, historyContext, response, requestedRange, isCurrent);
                if (settlement === 'stale') return;
                if (settlement === 'unchanged') {
                    await applyHistoryResponse(dependencies, runtime, historyContext, response, { resetView, morph: false, chartLoadToken, isCurrent });
                    return;
                }
                dependencies.persistPageControls();
            }
            if (isCurrent()) throw new Error('Hardware history range did not settle');
        } catch (error) {
            const runtimeError = ensureError(error);
            if (!isCurrent() || isAbortError(runtimeError)) return;
            handleHistoryLoadError(dependencies, runtime, runtimeError, chartLoadToken);
        } finally {
            session.lifecycle.releaseRealtimeCapture(lease);
        }
    });
};

const applyHistoryResponse = async (dependencies: HardwareHistoryStreamDependencies, runtime: HardwareHistoryRuntime, historyContext: HardwareHistoryContext, response: HardwareHistoryResponse, options: { resetView: boolean; morph: boolean; chartLoadToken: HardwareChartLoadToken; isCurrent: () => boolean }): Promise<void> => {
    const state = dependencies.state;
    const result = buildHardwareHistorySeries(historyContext, response);
    if (result.type === STR_OHLC) {
        if (!isArray(result.series)) throw new TypeError('candlestick series must be an array');
        const intervalMs = readCoercedFiniteNumberOrNullValue(result.metadata.intervalMs);
        if (intervalMs === null || intervalMs <= 0) {
            throw new TypeError('history result metadata.intervalMs must be a positive number');
        }
        state.candlestickData = [...result.series];
        state.candlestickBuckets = new Map(result.candlestickBuckets);
        state.candlestickMetadata = { ...result.metadata, aggregation: STR_OHLC };
        state.lastResolvedCandlestickIntervalMs = Math.max(1, Math.round(intervalMs));
        const intervalMinutes = Math.max(1, Math.round(intervalMs / 60_000));
        if (intervalMinutes !== state.candlestickIntervalMinutes) {
            state.candlestickIntervalMinutes = intervalMinutes;
            await refreshChartControls(dependencies.renderController.filtersContext, { range: false, candles: true });
            if (!options.isCurrent()) return;
        }
    } else {
        if (!isArray(result.series)) throw new TypeError('line series must be an array');
        state.historyData = [...result.series];
        state.historyMetadata = result.metadata;
    }
    parseHardwareHistoryResponseMetadata(getHistoryMetadataHost(runtime.historyHostCache, dependencies.historyHostDependencies), result.metadata);
    if (result.type === STR_OHLC) trimCandlestickData(state, true);
    else trimHistoryData(state, true);
    runtime.session.lifecycle.setRealtimeBoundary(response.metadata.availability?.newestSampleTsMs ?? null, response.metadata.endTsMs);
    runtime.session.lifecycle.initialized = true;
    const candlestick = result.type === STR_OHLC;
    runtime.pager.start({ intervalMs: resolveHardwareHistoryIntervalMs(state, candlestick), pointCap: Math.max(1, Math.min(state.historyApiPointCap, state.maxHistoryPoints)), oldestSampleTs: response.metadata.availability?.oldestSampleTsMs ?? null });
    updateMainChart(dependencies.renderController.chartContext, { resetView: options.resetView, morph: options.morph });
    runtime.session.lifecycle.replayRealtimeSamples((snapshot) => applyHardwareHistoryRealtimeUpdate(getHistoryRealtimeHost(runtime.historyHostCache, dependencies.historyHostDependencies), snapshot));
    runtime.session.backup = null;
    completeMainChartLoad(dependencies.renderController.chartContext, options.chartLoadToken);
    const activeSeries = candlestick ? state.candlestickData : state.historyData;
    setHistoryLoadStatus(dependencies, activeSeries.length === 0 ? i18n.t('charts.emptyState') : null, activeSeries.length === 0 ? 'info' : null);
};

const handleHistoryLoadError = (dependencies: HardwareHistoryStreamDependencies, runtime: HardwareHistoryRuntime, error: Error, chartLoadToken: HardwareChartLoadToken): void => {
    const session = runtime.session;
    dependencies.logger('error', 'History load failed', error);
    if (session.backup) {
        dependencies.historyStateManager.restore(dependencies.state, session.backup);
        updateMainChart(dependencies.renderController.chartContext, { resetView: false });
    }
    invalidateHistoryRuntime(runtime);
    completeMainChartLoad(dependencies.renderController.chartContext, chartLoadToken);
    setHistoryLoadStatus(dependencies, formatHistoryErrorMessage(error), 'error', HARDWARE_ACTION_HISTORY_RETRY);
    const status = error instanceof APIError ? error.status : 0;
    if ([400, 413, 422, 429, 500].includes(status)) {
        dependencies.state.historyApiPointCap = Math.max(150, Math.floor((dependencies.state.historyApiPointCap || 2000) * 0.6));
    }
    dependencies.handleError(error, i18n.t('hardware.errors.historyInitFailed'), { notify: true });
};

const recheckHistoryAvailability = async (dependencies: HardwareHistoryStreamDependencies, runtime: HardwareHistoryRuntime): Promise<boolean> => {
    const session = runtime.session;
    const lease = session.lifecycle.request.current();
    const historyContext = buildHistoryContext(dependencies);
    const readSeriesKey = (): string => resolveHistorySeriesKey(dependencies.state, historyContext.getSelectedHistoryTarget());
    const metric = resolveHistorySeriesMetric(dependencies.state, historyContext.getSelectedHistoryTarget());
    if (!lease || !session.lifecycle.initialized || metric === undefined) return false;
    const seriesKey = readSeriesKey();
    const isCurrent = (): boolean => session.lifecycle.request.isCurrent(lease) && readSeriesKey() === seriesKey;
    const requestedRange = dependencies.state.timeRange;
    try {
        const response = await requestHardwareHistory(buildHistoryAvailabilityRequestParameters(historyContext, metric), lease.signal);
        if (!isCurrent()) return false;
        if ((await settleHardwareHistoryAvailability(dependencies, historyContext, response, requestedRange, isCurrent)) !== 'corrected') return false;
        dependencies.persistPageControls();
        return true;
    } catch (error) {
        const runtimeError = ensureError(error);
        if (isCurrent() && !isAbortError(runtimeError)) {
            dependencies.rangeAvailability.retryRecheck(30_000);
            dependencies.logger('warn', 'History availability recheck failed', runtimeError);
        }
    }
    return false;
};

const resolveHardwareHistoryResolution = (dependencies: HardwareHistoryStreamDependencies, runtime: HardwareHistoryRuntime, visibleStartTs: number, visibleEndTs: number): HistoryResolutionWindow | null => {
    const state = dependencies.state;
    if (!runtime.session.lifecycle.initialized || !state.mainChart) return null;
    return resolveHistoryResolutionChange({
        budget: getHistoryPointBudgetConfig(state),
        supportedIntervalsMs: state.supportedHistoryIntervalsMs,
        loadedIntervalMs: state.historyMetadata?.intervalMs ?? null,
        visibleStartTs,
        visibleEndTs,
        nowMs: serverEpochMs()
    });
};

const resampleHardwareHistory = async (dependencies: HardwareHistoryStreamDependencies, runtime: HardwareHistoryRuntime, window: HistoryResolutionWindow): Promise<void> => {
    const lifecycle = runtime.session.lifecycle;
    const lease = lifecycle.request.current();
    if (!lease || !lifecycle.initialized || isCandlestickActive(dependencies.state)) return;
    const historyContext = buildHistoryContext(dependencies);
    const readRequestKey = (): string => resolveHistoryRequestKey(dependencies.state, historyContext.getSelectedHistoryTarget());
    const requestKey = readRequestKey();
    const isCurrent = (): boolean => lifecycle.request.isCurrent(lease) && readRequestKey() === requestKey;
    const availabilityMetric = resolveHistorySeriesMetric(dependencies.state, historyContext.getSelectedHistoryTarget());
    const parameters = { ...buildHistoryRequestParameters(historyContext), ...window, points: resolveHistoryPagePoints(window, window.intervalMs) };
    runtime.pager.suspend();
    lifecycle.beginRealtimeCapture();
    try {
        const response = await requestHardwareHistory(availabilityMetric === undefined ? parameters : { ...parameters, availabilityMetric }, lease.signal);
        if (!isCurrent()) return;
        const chartContext = dependencies.renderController.chartContext;
        await applyHistoryResponse(dependencies, runtime, historyContext, response, { resetView: false, morph: true, chartLoadToken: chartContext.currentChartPresentationLoad(), isCurrent });
    } catch (error) {
        if (isCurrent()) throw error;
    } finally {
        lifecycle.releaseRealtimeCapture(lease);
        runtime.pager.resume();
    }
};

const handleHistoryUpdate = (dependencies: HardwareHistoryStreamDependencies, runtime: HardwareHistoryRuntime, data: HardwarePageSnapshot): void => {
    runtime.session.lifecycle.captureRealtimeSample(data);
    if (!runtime.session.lifecycle.initialized) return;
    applyHardwareHistoryRealtimeUpdate(getHistoryRealtimeHost(runtime.historyHostCache, dependencies.historyHostDependencies), data);
};

const followHardwareHistoryRange = (dependencies: HardwareHistoryStreamDependencies, runtime: HardwareHistoryRuntime, visibleStartTs: number, visibleEndTs: number): void => {
    const state = dependencies.state;
    const chartFilters = dependencies.renderController.chartFilters;
    runtime.resolution.observe(visibleStartTs, visibleEndTs);
    if (!chartFilters || !runtime.session.lifecycle.initialized) return;
    const series = isCandlestickActive(state) ? state.candlestickData : state.historyData;
    followHistoryRange({
        availableMinutes: state.availableTimeRanges,
        selectedMinutes: state.timeRange,
        visibleStartTs,
        visibleEndTs,
        newestTs: series[series.length - 1]?.timestamp ?? null,
        apply: (minutes) => {
            state.timeRange = minutes;
            chartFilters.setValue(FILTER_TYPES.TIME_RANGE, minutes, false);
            dependencies.persistPageControls();
        }
    });
};

export { followHardwareHistoryRange, handleHistoryUpdate, invalidateHistoryRuntime, recheckHistoryAvailability, resampleHardwareHistory, resolveHardwareHistoryResolution, startHistoryStream };
export type { HardwareHistoryStreamDependencies, HardwareHistoryRuntime };
