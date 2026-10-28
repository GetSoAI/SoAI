/* SoAI - Charts feature demand-driven older history pager [frontend/assets/ts/features/charts/historyPager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isAbortError } from '@core/errors/abort.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { clampNumber } from '@core/primitives/clampNumber.ts';
import { createMicrotaskScheduler } from '@core/primitives/microtaskScheduler.ts';
import type { ChartHistoryPort, ChartHistoryStatus } from '@features/charts/chartTypes.ts';
import type { ChartPointInput } from '@features/charts/data/chartPointTypes.ts';
import type { ChartPrependResult } from '@features/charts/session/ChartDataCommands.ts';
import { MAX_HISTORY_PAGE_REQUESTS, resolveOlderHistoryPage, type HistoryPageWindow } from '@features/charts/historyPageWindow.ts';
import { HISTORY_CHART_MIN_POINTS } from '@features/charts/historyPointBudget.ts';
import { HistoryRequestFence, type HistoryRequestLease } from '@features/charts/historyRequestFence.ts';

interface HistoryPagerChart {
    data: { prepend(points: ReadonlyArray<ChartPointInput>): ChartPrependResult };
    view: { syncToSeries(): void };
}

interface HistoryPagerPage {
    points: ChartPointInput[];
    capped: boolean;
}

interface HistoryPagerSource {
    earliestTs(): number | null;
    fetchPage(window: HistoryPageWindow, signal: AbortSignal): Promise<HistoryPagerPage>;
}

interface HistoryPagerSession {
    intervalMs: number;
    pointCap: number;
    oldestSampleTs: number | null;
}

interface HistoryPagerDependencies {
    getChart(): HistoryPagerChart | null;
    source: HistoryPagerSource;
    report(error: Error): void;
}

const PREFETCH_SCREENS = 1;

class HistoryPager implements ChartHistoryPort {
    readonly #fence = new HistoryRequestFence();
    readonly #dependencies: HistoryPagerDependencies;
    readonly #schedulePump: () => void;
    #session: HistoryPagerSession | null = null;
    #status: ChartHistoryStatus = 'idle';
    #boundaryTs: number | null = null;
    #targetTs = Number.NaN;
    #running = false;
    #suspended = false;

    constructor(dependencies: HistoryPagerDependencies) {
        this.#dependencies = dependencies;
        this.#schedulePump = createMicrotaskScheduler(() => this.#pump(), { label: 'HistoryPager' });
    }

    get status(): ChartHistoryStatus {
        return this.#suspended ? 'loading' : this.#status;
    }

    get oldestNavigableTs(): number | null {
        return this.#session ? this.#boundaryTs : this.#dependencies.source.earliestTs();
    }

    demand(visibleStartTs: number, visibleEndTs: number): void {
        if (!Number.isFinite(visibleStartTs) || !Number.isFinite(visibleEndTs)) return;
        this.#targetTs = visibleStartTs - Math.max(0, visibleEndTs - visibleStartTs) * PREFETCH_SCREENS;
        if (this.#session && this.#status === 'idle' && !this.#running) this.#schedulePump();
    }

    retry(): void {
        if (!this.#session || this.#status !== 'failed') return;
        this.#setStatus('idle', null);
        this.#schedulePump();
    }

    start(session: HistoryPagerSession): void {
        if (!(session.intervalMs >= 1) || !(session.pointCap >= 1) || (session.oldestSampleTs !== null && !Number.isFinite(session.oldestSampleTs))) {
            throw new TypeError('History pager requires a positive interval, point cap, and finite oldest sample');
        }
        this.#fence.begin();
        this.#running = false;
        this.#suspended = false;
        this.#session = { ...session };
        this.#applyStatus('idle', null);
        this.#schedulePump();
    }

    suspend(): void {
        if (!this.#session || this.#suspended) return;
        this.#fence.begin();
        this.#running = false;
        this.#suspended = true;
        if (this.#status === 'loading') this.#setStatus('idle', null);
        else this.#dependencies.getChart()?.view.syncToSeries();
    }

    resume(): void {
        if (!this.#suspended) return;
        this.#suspended = false;
        this.#dependencies.getChart()?.view.syncToSeries();
        this.#schedulePump();
    }

    reset(): void {
        const active = this.#session !== null;
        this.#fence.invalidate();
        this.#running = false;
        this.#suspended = false;
        this.#session = null;
        this.#targetTs = Number.NaN;
        this.#status = 'idle';
        this.#boundaryTs = null;
        if (active) this.#dependencies.getChart()?.view.syncToSeries();
    }

    #pump(): void {
        const session = this.#session;
        const lease = this.#fence.current();
        if (!session || !lease || this.#suspended || this.#running || this.#status !== 'idle' || !this.#needsOlder()) return;
        this.#running = true;
        this.#setStatus('loading', null);
        void this.#fill(session, lease)
            .then((status) => {
                if (!this.#fence.isCurrent(lease)) return;
                this.#running = false;
                this.#setStatus(status, status === 'exhausted' || status === 'capped' ? this.#dependencies.source.earliestTs() : null);
                if (status === 'idle') this.#schedulePump();
            })
            .catch((error) => {
                if (this.#fence.isCurrent(lease)) {
                    this.#running = false;
                    this.#status = 'failed';
                }
                this.#dependencies.report(ensureError(error));
            });
    }

    #needsOlder(): boolean {
        const earliest = this.#dependencies.source.earliestTs();
        return earliest !== null && Number.isFinite(this.#targetTs) && earliest > this.#targetTs;
    }

    async #fill(session: HistoryPagerSession, lease: HistoryRequestLease): Promise<ChartHistoryStatus> {
        let cursorTs = this.#dependencies.source.earliestTs();
        if (cursorTs === null) return 'idle';
        let pagePoints = this.#resolvePagePoints(session, cursorTs);
        try {
            for (let page = 0; page < MAX_HISTORY_PAGE_REQUESTS; page += 1) {
                const window = resolveOlderHistoryPage(cursorTs, session.oldestSampleTs ?? 0, session.intervalMs, pagePoints);
                if (!window) return 'exhausted';
                const result = await this.#dependencies.source.fetchPage(window, lease.signal);
                if (!this.#fence.isCurrent(lease)) return 'idle';
                const chart = this.#dependencies.getChart();
                if (!chart) return 'failed';
                const prepended = chart.data.prepend(result.points);
                if (result.capped || prepended.truncated) return 'capped';
                if (prepended.added === 0 && session.oldestSampleTs === null) return 'exhausted';
                if (prepended.added > 0 && !this.#needsOlder()) return 'idle';
                cursorTs = window.startTsMs;
                pagePoints = prepended.added === 0 ? Math.min(session.pointCap, pagePoints * 2) : this.#resolvePagePoints(session, cursorTs);
            }
            throw new Error('Older history exceeded the bounded page count');
        } catch (error) {
            const runtimeError = ensureError(error);
            if (this.#fence.isCurrent(lease) && !isAbortError(runtimeError)) this.#dependencies.report(runtimeError);
            return 'failed';
        }
    }

    #resolvePagePoints(session: HistoryPagerSession, cursorTs: number): number {
        const missingPoints = Math.ceil((cursorTs - this.#targetTs) / session.intervalMs);
        return Number.isFinite(missingPoints) ? clampNumber(missingPoints, Math.min(HISTORY_CHART_MIN_POINTS, session.pointCap), session.pointCap) : session.pointCap;
    }

    #setStatus(status: ChartHistoryStatus, boundaryTs: number | null): void {
        if (this.#status === status && this.#boundaryTs === boundaryTs) return;
        this.#applyStatus(status, boundaryTs);
    }

    #applyStatus(status: ChartHistoryStatus, boundaryTs: number | null): void {
        this.#status = status;
        this.#boundaryTs = boundaryTs;
        this.#dependencies.getChart()?.view.syncToSeries();
    }
}

export { HistoryPager };
export type { HistoryPagerChart, HistoryPagerDependencies, HistoryPagerPage, HistoryPagerSession, HistoryPagerSource };
