/* SoAI - Metrics page stored history lifecycle [frontend/assets/ts/pages/metrics/controllers/page/metricsHistoryController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { serializeSystemMetricsHistoryRequest, type SystemMetricsHistoryRequest } from '@core/api/contracts/systemMetricsRequestContracts.ts';
import { isAbortError, throwIfAborted } from '@core/errors/abort.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { decodeMetricsHistoryPayload, type MetricsHistoryPayload } from '@core/realtime/metricsHistoryContracts.ts';
import { serverEpochMs } from '@core/time/clock.ts';
import { requestWebSocketSnapshotRecord } from '@core/websocketclient/snapshotPayload.ts';
import { FILTER_TYPES, followHistoryRange, HistoryPager, HistoryRangeAvailability, HistoryResolutionFollower, HistorySession, renderHistoryChartStatus, resolveHistoryChartStatusElement, resolveHistoryResolutionChange, settleHistoryAvailability, type HistoryPageWindow, type HistoryPagerPage, type HistoryResolutionWindow } from '@features/charts/public.ts';
import { METRICS_ACTION_HISTORY_RETRY } from '@pages/metrics/actions.ts';
import { applyMetricsCandlestickHistory, applyMetricsValueHistory, prependMetricsCandlestickHistory, resolveMetricsCandlestickHistoryRequest, resolveMetricsValueHistoryRequest } from '@pages/metrics/controllers/page/adapters.ts';
import type { MetricsPageEffectsHost } from '@pages/metrics/controllers/page/contracts.ts';
import { getMetricsChartPresentation } from '@pages/metrics/controllers/page/effects.ts';
import { applyRealtimeMetricsChartValue, buildMetricsDisplaySeries, resetMetricsData, updateMetricsMainChart } from '@pages/metrics/controllers/page/metricsUpdateProcessing.ts';
import { persistMetricsPageControls } from '@pages/metrics/controllers/page/metricsPageControlsController.ts';
import { getEffectiveMetricsCandlestickIntervalMs, getMetricsHistoryKey, getMetricsHistoryPointBudgetConfig, isMetricsCandlestickActive, resolveMetricsValueIntervalMs } from '@pages/metrics/controllers/page/state.ts';
import type { CandlestickDataPoint, MetricsHistoryPoint } from '@pages/metrics/types.ts';

class MetricsHistoryController {
    readonly rangeAvailability: HistoryRangeAvailability;
    readonly pager: HistoryPager;
    readonly #resolution: HistoryResolutionFollower;
    readonly #session = new HistorySession<{ timestamp: number; value: number }>();
    readonly #host: MetricsPageEffectsHost;
    #clearedThroughMs = 0;

    constructor(host: MetricsPageEffectsHost) {
        this.#host = host;
        this.pager = new HistoryPager({
            getChart: () => host.state.mainChart,
            source: { earliestTs: () => this.#activeSeries()[0]?.timestamp ?? null, fetchPage: (window, signal) => this.#fetchOlderPage(window, signal) },
            report: (error) => host.operations.logger('warn', 'Metrics older history request failed', error)
        });
        this.#resolution = new HistoryResolutionFollower({
            resolve: (visibleStartTs, visibleEndTs) => this.#resolveResolution(visibleStartTs, visibleEndTs),
            reload: (window) => this.#resample(window),
            report: (error) => host.operations.logger('warn', 'Metrics history resolution reload failed', error)
        });
        this.rangeAvailability = new HistoryRangeAvailability(() => {
            this.#session.probeOnce(
                () => this.#recheckAvailability(),
                (error) => host.operations.logger('warn', 'Metrics history availability recheck failed', error)
            );
        });
    }

    async #recheckAvailability(): Promise<void> {
        const host = this.#host;
        const lease = this.#session.request.current();
        if (!lease || !this.#session.initialized || !host.state.mainChart) return;
        const signature = this.#signature();
        const isCurrent = (): boolean => this.#session.request.isCurrent(lease) && this.#signature() === signature;
        const requestedRange = host.state.timeRange;
        try {
            const request = isMetricsCandlestickActive(host) ? resolveMetricsCandlestickHistoryRequest(host, null) : resolveMetricsValueHistoryRequest(host, null);
            if (!request?.intervalMs) throw new Error('Metrics availability request requires a history interval');
            const endTsMs = request.endTsMs;
            const response = await this.#request({ ...request, startTsMs: Math.max(0, endTsMs - request.intervalMs), points: 1, includeAvailability: true }, lease.signal);
            if (!isCurrent()) return;
            if (!response.metadata.availability || response.metadata.availability.observedAtMs < this.#clearedThroughMs) throw new Error('Metrics availability is missing or predates the last reset');
            const settlement = await settleHistoryAvailability({
                rangeAvailability: this.rangeAvailability,
                seriesKey: this.seriesKey(),
                availability: response.metadata.availability,
                loggingIntervalMs: response.metadata.loggingIntervalMs,
                requestedRange,
                getTimeRange: () => host.state.timeRange,
                syncTimeRange: async () => {
                    await host.operations.syncChartControls({ range: true, candles: false });
                    return isCurrent();
                },
                isCurrent
            });
            if (settlement === 'corrected' && isCurrent()) {
                persistMetricsPageControls(host.state);
                await this.load();
            }
        } catch (error) {
            const runtimeError = ensureError(error);
            if (!isCurrent() || isAbortError(runtimeError)) return;
            this.rangeAvailability.retryRecheck(30_000);
            host.operations.logger('warn', 'Metrics history availability recheck failed', runtimeError);
        }
    }

    seriesKey(): string {
        return getMetricsHistoryKey(this.#host) ?? '';
    }

    isInitialized(): boolean {
        return this.#session.initialized;
    }

    acceptRealtimeTimestamp(timestamp: number): boolean {
        return this.#session.acceptRealtimeTimestamp(timestamp);
    }

    captureRealtimeSample(timestamp: number, value: number): void {
        this.#session.captureRealtimeSample({ timestamp, value });
    }

    followRange(visibleStartTs: number, visibleEndTs: number): void {
        const host = this.#host;
        this.#resolution.observe(visibleStartTs, visibleEndTs);
        const chartFilters = host.state.chartFilters;
        if (!chartFilters || !this.#session.initialized) return;
        const series = this.#activeSeries();
        followHistoryRange({
            availableMinutes: host.state.availableTimeRanges,
            selectedMinutes: host.state.timeRange,
            visibleStartTs,
            visibleEndTs,
            newestTs: series[series.length - 1]?.timestamp ?? null,
            apply: (minutes) => {
                host.state.timeRange = minutes;
                chartFilters.setValue(FILTER_TYPES.TIME_RANGE, minutes, false);
                persistMetricsPageControls(host.state);
            }
        });
    }

    readonly load = async (): Promise<void> => {
        const host = this.#host;
        this.#session.invalidate();
        this.#resolution.cancel();
        this.pager.reset();
        const lease = this.#session.request.begin();
        const signature = this.#signature();
        const isCurrent = (): boolean => this.#session.request.isCurrent(lease) && this.#signature() === signature;
        const presentation = getMetricsChartPresentation(host);
        const presentationSequence = presentation.begin();
        const completePresentation = (): void => presentation.complete(presentationSequence);
        this.#status(i18n.t('charts.loadingState'), 'loading', true, null);
        if (!host.state.metricsHistoryEnabled || !host.state.mainChart) {
            if (isCurrent()) {
                updateMetricsMainChart(host, { resetView: true });
                this.#status(null);
                completePresentation();
            }
            return;
        }
        this.#session.beginRealtimeCapture();
        try {
            for (let attempt = 0; attempt < 4 && isCurrent(); attempt += 1) {
                const requestedRange = host.state.timeRange;
                const candlestick = isMetricsCandlestickActive(host);
                const request = candlestick ? resolveMetricsCandlestickHistoryRequest(host, null) : resolveMetricsValueHistoryRequest(host, null);
                if (!request) throw new Error('Metrics history request could not be resolved');
                const response = await this.#request({ ...request, includeAvailability: true }, lease.signal);
                if (!isCurrent()) return;
                if (!response.metadata.availability || response.metadata.availability.observedAtMs < this.#clearedThroughMs) {
                    throw new Error('Metrics history availability is missing or predates the last reset');
                }
                const settlement = await settleHistoryAvailability({
                    rangeAvailability: this.rangeAvailability,
                    seriesKey: this.seriesKey(),
                    availability: response.metadata.availability,
                    loggingIntervalMs: response.metadata.loggingIntervalMs,
                    requestedRange,
                    getTimeRange: () => host.state.timeRange,
                    syncTimeRange: async () => {
                        await host.operations.syncChartControls({ range: true, candles: true });
                        return isCurrent();
                    },
                    isCurrent
                });
                if (settlement === 'stale') return;
                if (settlement === 'corrected') {
                    persistMetricsPageControls(host.state);
                    continue;
                }
                if (!isCurrent()) return;
                if (candlestick) {
                    const candleIntervalChanged = applyMetricsCandlestickHistory(host, response);
                    if (candleIntervalChanged) {
                        await host.operations.syncChartControls({ range: false, candles: true });
                        if (!isCurrent()) return;
                    }
                } else {
                    applyMetricsValueHistory(host, response, 'refresh');
                }
                this.#session.setRealtimeBoundary(response.metadata.availability.newestSampleTsMs, response.metadata.endTsMs);
                this.#session.initialized = true;
                this.#startPager(candlestick, response.metadata.availability.oldestSampleTsMs);
                updateMetricsMainChart(host, { resetView: true });
                this.#session.replayRealtimeSamples((sample) => applyRealtimeMetricsChartValue(host, sample.timestamp, sample.value));
                const empty = this.#activeSeries().length === 0;
                this.#status(empty ? i18n.t('charts.emptyState') : null, empty ? 'info' : null, true, null);
                completePresentation();
                return;
            }
            if (isCurrent()) throw new Error('Metrics history range did not settle');
        } catch (error) {
            const runtimeError = ensureError(error);
            if (!isCurrent() || isAbortError(runtimeError)) return;
            this.rangeAvailability.accept(this.seriesKey(), null, 0);
            this.#status(i18n.t('charts.historyFailed'), 'error', true, METRICS_ACTION_HISTORY_RETRY);
            completePresentation();
            host.operations.logger('error', 'Metrics history load failed', runtimeError);
        } finally {
            this.#session.releaseRealtimeCapture(lease);
        }
    };

    #resolveResolution(visibleStartTs: number, visibleEndTs: number): HistoryResolutionWindow | null {
        const host = this.#host;
        if (!this.#session.initialized || !host.state.mainChart) return null;
        return resolveHistoryResolutionChange({
            budget: getMetricsHistoryPointBudgetConfig(host),
            supportedIntervalsMs: host.state.supportedHistoryIntervalsMs,
            loadedIntervalMs: host.state.historyIntervalMs,
            visibleStartTs,
            visibleEndTs,
            nowMs: serverEpochMs()
        });
    }

    async #resample(window: HistoryResolutionWindow): Promise<void> {
        const host = this.#host;
        const lease = this.#session.request.current();
        if (!lease || !this.#session.initialized || isMetricsCandlestickActive(host)) return;
        const signature = this.#signature();
        const isCurrent = (): boolean => this.#session.request.isCurrent(lease) && this.#signature() === signature;
        const request = resolveMetricsValueHistoryRequest(host, window);
        if (!request) return;
        this.pager.suspend();
        this.#session.beginRealtimeCapture();
        try {
            const response = await this.#request({ ...request, includeAvailability: true }, lease.signal);
            if (!isCurrent()) return;
            const availability = response.metadata.availability;
            if (!availability || availability.observedAtMs < this.#clearedThroughMs) throw new Error('Metrics resolution availability is missing or predates the last reset');
            applyMetricsValueHistory(host, response, 'refresh');
            this.#session.setRealtimeBoundary(availability.newestSampleTsMs, response.metadata.endTsMs);
            this.#startPager(false, availability.oldestSampleTsMs);
            updateMetricsMainChart(host, { morph: true });
            this.#session.replayRealtimeSamples((sample) => applyRealtimeMetricsChartValue(host, sample.timestamp, sample.value));
        } catch (error) {
            if (isCurrent()) throw error;
        } finally {
            this.#session.releaseRealtimeCapture(lease);
            this.pager.resume();
        }
    }

    #startPager(candlestick: boolean, oldestSampleTs: number | null): void {
        const state = this.#host.state;
        this.pager.start({ intervalMs: this.#intervalMs(candlestick), pointCap: Math.max(1, Math.min(state.historyApiPointCap, state.maxHistoryPoints)), oldestSampleTs });
    }

    async #fetchOlderPage(window: HistoryPageWindow, signal: AbortSignal): Promise<HistoryPagerPage> {
        const host = this.#host;
        const candlestick = isMetricsCandlestickActive(host);
        const request = candlestick ? resolveMetricsCandlestickHistoryRequest(host, window) : resolveMetricsValueHistoryRequest(host, window);
        if (!request) throw new Error('Metrics older history request could not be resolved');
        const response = await this.#request(request, signal);
        throwIfAborted(signal);
        const { prepended, capped } = candlestick ? prependMetricsCandlestickHistory(host, response) : applyMetricsValueHistory(host, response, 'prepend');
        return { points: buildMetricsDisplaySeries(host, prepended, candlestick), capped };
    }

    reset(clearedThroughMs: number): void {
        this.#clearedThroughMs = Math.max(this.#clearedThroughMs, clearedThroughMs);
        getMetricsChartPresentation(this.#host).begin();
        this.#session.invalidate();
        this.rangeAvailability.reset();
        resetMetricsData(this.#host, true);
        updateMetricsMainChart(this.#host, { resetView: true });
        void this.load().catch((error) => this.#host.operations.logger('error', 'Metrics history reset reload failed', ensureError(error)));
    }

    reconnect(): void {
        if (this.#host.state.mainChart) {
            void this.load().catch((error) => this.#host.operations.logger('error', 'Metrics history reconnect reload failed', ensureError(error)));
        }
    }

    dispose(): void {
        this.#session.invalidate();
        this.#resolution.cancel();
        this.pager.reset();
        this.rangeAvailability.reset();
    }

    #signature(): string {
        return `${this.seriesKey()}:${isMetricsCandlestickActive(this.#host) ? 'ohlc' : 'value'}`;
    }

    #activeSeries(): readonly (MetricsHistoryPoint | CandlestickDataPoint)[] {
        return isMetricsCandlestickActive(this.#host) ? this.#host.state.candlestickData : this.#host.state.metricsHistory;
    }

    #intervalMs(candlestick: boolean): number {
        return candlestick ? getEffectiveMetricsCandlestickIntervalMs(this.#host) : resolveMetricsValueIntervalMs(this.#host);
    }

    async #request(request: SystemMetricsHistoryRequest, signal: AbortSignal): Promise<MetricsHistoryPayload> {
        const payload = await requestWebSocketSnapshotRecord('system.metrics.history', serializeSystemMetricsHistoryRequest(request), { signal });
        const response = decodeMetricsHistoryPayload(payload);
        if (response.metadata.metricKey !== request.metricKey || response.metadata.aggregation !== request.aggregation || response.aggregation !== request.aggregation) {
            throw new TypeError('Metrics history response does not match its request');
        }
        if (response.intervalMs !== response.metadata.intervalMs) throw new TypeError('Metrics history interval differs between payload and metadata');
        return response;
    }

    #status(message: string | null, tone: string | null = null, overlay = false, retryAction: string | null = null): void {
        const container = this.#host.operations.getCachedUI('mainChartContainer') ?? this.#host.owners.pageDom.requireHTMLElement('#mainChartContainer');
        const element = resolveHistoryChartStatusElement(container);
        renderHistoryChartStatus(element, message ? { message, tone, overlay, retryAction } : null);
    }
}

export { MetricsHistoryController };
