/* SoAI - Charts feature zoom-driven history resolution [frontend/assets/ts/features/charts/historyResolution.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isAbortError } from '@core/errors/abort.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { throttle } from '@core/primitives/timing.ts';
import { resolveSupportedIntervalMs } from '@features/charts/datatransforms/guards.ts';
import type { HistoryPageWindow } from '@features/charts/historyPageWindow.ts';
import { computeHistoryChartPointBudget, resolveHistoryChartPointLimit, type HistoryChartPointBudgetConfig } from '@features/charts/historyPointBudget.ts';

interface HistoryResolutionInput {
    budget: HistoryChartPointBudgetConfig;
    supportedIntervalsMs: number[] | null | undefined;
    loadedIntervalMs: number | null;
    visibleStartTs: number;
    visibleEndTs: number;
    nowMs: number;
}

interface HistoryResolutionWindow extends HistoryPageWindow {
    intervalMs: number;
}

interface HistoryResolutionFollowerDependencies {
    resolve(visibleStartTs: number, visibleEndTs: number): HistoryResolutionWindow | null;
    reload(window: HistoryResolutionWindow): Promise<void>;
    report(error: Error): void;
}

const HISTORY_RESOLUTION_TOLERANCE = 1.25;
const HISTORY_RESOLUTION_SETTLE_MS = 250;
const HISTORY_RESOLUTION_RETRY_MS = 30_000;

const resolveHistoryResolutionChange = ({ budget, supportedIntervalsMs, loadedIntervalMs, visibleStartTs, visibleEndTs, nowMs }: HistoryResolutionInput): HistoryResolutionWindow | null => {
    const spanMs = visibleEndTs - visibleStartTs;
    if (budget.candlestickActive || !supportedIntervalsMs?.length || loadedIntervalMs === null || !Number.isFinite(visibleStartTs) || !Number.isFinite(nowMs) || !(spanMs > 0) || !Number.isFinite(spanMs)) return null;
    const startTsMs = Math.max(0, Math.floor(Math.min(visibleStartTs, nowMs - spanMs)));
    const endTsMs = Math.floor(nowMs);
    const pointLimit = resolveHistoryChartPointLimit(budget);
    if (endTsMs <= startTsMs) return null;
    const requiredMs = Math.max(spanMs / computeHistoryChartPointBudget(budget, spanMs), (endTsMs - startTsMs) / Math.max(1, pointLimit - 1), budget.monitoringIntervalMs);
    const resolveSnappedIntervalMs = (targetMs: number): number => resolveSupportedIntervalMs(targetMs, supportedIntervalsMs, budget.monitoringIntervalMs);
    if (loadedIntervalMs >= resolveSnappedIntervalMs(requiredMs / HISTORY_RESOLUTION_TOLERANCE) && loadedIntervalMs <= resolveSnappedIntervalMs(requiredMs)) return null;
    const intervalMs = resolveSnappedIntervalMs(requiredMs);
    return intervalMs !== loadedIntervalMs && Math.ceil((endTsMs - startTsMs) / intervalMs) + 1 <= pointLimit ? { startTsMs, endTsMs, intervalMs } : null;
};

class HistoryResolutionFollower {
    readonly #dependencies: HistoryResolutionFollowerDependencies;
    readonly #schedule = throttle((visibleStartTs: number, visibleEndTs: number) => this.#evaluate(visibleStartTs, visibleEndTs), HISTORY_RESOLUTION_SETTLE_MS);
    #deferred: [number, number] | null = null;
    #failure: { intervalMs: number; retryAtMs: number } | null = null;
    #reloading = false;

    constructor(dependencies: HistoryResolutionFollowerDependencies) {
        this.#dependencies = dependencies;
    }

    observe(visibleStartTs: number, visibleEndTs: number): void {
        if (Number.isFinite(visibleStartTs) && Number.isFinite(visibleEndTs)) this.#schedule(visibleStartTs, visibleEndTs);
    }

    cancel(): void {
        this.#schedule.cancel();
        this.#deferred = null;
        this.#failure = null;
    }

    #evaluate(visibleStartTs: number, visibleEndTs: number): void {
        if (this.#reloading) {
            this.#deferred = [visibleStartTs, visibleEndTs];
            return;
        }
        let window: HistoryResolutionWindow | null;
        try {
            window = this.#dependencies.resolve(visibleStartTs, visibleEndTs);
        } catch (error) {
            this.#dependencies.report(ensureError(error));
            return;
        }
        if (!window || (window.intervalMs === this.#failure?.intervalMs && Date.now() < this.#failure.retryAtMs)) return;
        this.#reloading = true;
        void this.#dependencies
            .reload(window)
            .then(() => {
                this.#failure = null;
            })
            .catch((error) => {
                const runtimeError = ensureError(error);
                if (isAbortError(runtimeError)) return;
                this.#failure = { intervalMs: window.intervalMs, retryAtMs: Date.now() + HISTORY_RESOLUTION_RETRY_MS };
                this.#dependencies.report(runtimeError);
            })
            .finally(() => {
                this.#reloading = false;
                const deferred = this.#deferred;
                this.#deferred = null;
                if (deferred) this.#schedule(...deferred);
            });
    }
}

export { HistoryResolutionFollower, resolveHistoryResolutionChange };
export type { HistoryResolutionFollowerDependencies, HistoryResolutionInput, HistoryResolutionWindow };
