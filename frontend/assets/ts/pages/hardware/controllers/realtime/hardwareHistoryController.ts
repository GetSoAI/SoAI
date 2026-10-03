/* SoAI - Hardware page history controller [frontend/assets/ts/pages/hardware/controllers/realtime/hardwareHistoryController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import type { HistoryResetEvent } from '@core/realtime/eventcontracts/historyResetContracts.ts';
import { HistoryPager, HistoryResolutionFollower, type HistoryChartControlsManager } from '@features/charts/public.ts';
import type { ChartOhlcContract } from '@pages/hardware/contracts/contracts.ts';
import { isCandlestickActive, resolveHardwareHistoryIntervalMs } from '@pages/hardware/controllers/data/effects.ts';
import { handleHistoryUpdate, invalidateHistoryRuntime, recheckHistoryAvailability, resampleHardwareHistory, resolveHardwareHistoryResolution, type HardwareHistoryRuntime, type HardwareHistoryStreamDependencies } from '@pages/hardware/controllers/realtime/effects.ts';
import { createHardwareHistoryHostCache, createHardwareOlderHistoryHost } from '@pages/hardware/controllers/realtime/service.ts';
import { HardwareHistorySession } from '@pages/hardware/controllers/realtime/state.ts';
import { fetchHardwareOlderPage } from '@pages/hardware/services/history/hardwareOlderHistoryPage.ts';
import type { HardwarePageSnapshot } from '@pages/hardware/types.ts';

type HardwareHistoryControllerDependencies = Omit<HardwareHistoryStreamDependencies, 'historyHostDependencies'> & {
    chartOhlc: ChartOhlcContract;
    historyControlsManager: HistoryChartControlsManager;
    scheduleChartBootstrap: (options: { force: boolean; resetView: boolean }) => Promise<void>;
    handleChartBootstrapError: (error: Error) => void;
};

class HardwareHistoryController {
    readonly session = new HardwareHistorySession();
    readonly streamDependencies: HardwareHistoryStreamDependencies;
    readonly runtime: HardwareHistoryRuntime;
    readonly #scheduleChartBootstrap: HardwareHistoryControllerDependencies['scheduleChartBootstrap'];
    readonly #handleChartBootstrapError: (error: Error) => void;

    constructor(dependencies: HardwareHistoryControllerDependencies) {
        const { chartOhlc, historyControlsManager, scheduleChartBootstrap, handleChartBootstrapError, ...streamDependencies } = dependencies;
        this.#scheduleChartBootstrap = scheduleChartBootstrap;
        this.#handleChartBootstrapError = handleChartBootstrapError;
        this.streamDependencies = {
            ...streamDependencies,
            historyHostDependencies: {
                state: dependencies.state,
                dataController: dependencies.dataController,
                renderController: dependencies.renderController,
                chartOhlc,
                historyControlsManager,
                getClearedThroughMs: () => this.session.clearedThroughMs,
                acceptRealtimeTimestamp: (timestamp) => this.session.lifecycle.acceptRealtimeTimestamp(timestamp)
            }
        };
        const state = dependencies.state;
        const olderHistoryHost = createHardwareOlderHistoryHost(this.streamDependencies.historyHostDependencies);
        const pager = new HistoryPager({
            getChart: () => state.mainChart,
            source: {
                earliestTs: () => (isCandlestickActive(state) ? state.candlestickData : state.historyData)[0]?.timestamp ?? null,
                fetchPage: (window, signal) => {
                    const candlestick = isCandlestickActive(state);
                    return fetchHardwareOlderPage(olderHistoryHost, candlestick, resolveHardwareHistoryIntervalMs(state, candlestick), window, signal);
                }
            },
            report: (error) => dependencies.logger('warn', 'Hardware older history request failed', error)
        });
        const resolution = new HistoryResolutionFollower({
            resolve: (visibleStartTs, visibleEndTs) => resolveHardwareHistoryResolution(this.streamDependencies, this.runtime, visibleStartTs, visibleEndTs),
            reload: (window) => resampleHardwareHistory(this.streamDependencies, this.runtime, window),
            report: (error) => dependencies.logger('warn', 'Hardware history resolution reload failed', error)
        });
        this.runtime = { session: this.session, historyHostCache: createHardwareHistoryHostCache(), pager, resolution };
    }

    invalidate(): void {
        invalidateHistoryRuntime(this.runtime);
    }

    reset(): void {
        invalidateHistoryRuntime(this.runtime);
        this.streamDependencies.rangeAvailability.reset();
    }

    handleUpdate(snapshot: HardwarePageSnapshot): void {
        handleHistoryUpdate(this.streamDependencies, this.runtime, snapshot);
    }

    recheckAvailability(): void {
        this.session.lifecycle.probeOnce(
            async () => {
                if (await recheckHistoryAvailability(this.streamDependencies, this.runtime)) await this.#scheduleChartBootstrap({ force: true, resetView: true });
            },
            (error) => this.#handleChartBootstrapError(error)
        );
    }

    handleReset(event: HistoryResetEvent): void {
        this.session.clearedThroughMs = Math.max(this.session.clearedThroughMs, event.clearedThroughMs);
        this.streamDependencies.rangeAvailability.reset();
        this.handleReconnect();
    }

    handleReconnect(): void {
        if (!this.streamDependencies.state.mainChart) return;
        void this.#scheduleChartBootstrap({ force: true, resetView: true }).catch((error) => this.#handleChartBootstrapError(ensureError(error)));
    }
}

export { HardwareHistoryController };
