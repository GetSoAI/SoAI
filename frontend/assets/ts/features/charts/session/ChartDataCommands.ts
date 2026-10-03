/* SoAI - Chart data workflow coordination [frontend/assets/ts/features/charts/session/ChartDataCommands.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { DatasetInput } from '@features/charts/chartTypes.ts';
import type { ChartPointCandidate } from '@features/charts/data/chartPointTypes.ts';
import { EMPTY_VISIBLE_RANGE } from '@features/charts/component/data/visibleRange.ts';
import { monotonicMs } from '@core/time/clock.ts';
import type { ChartRedrawQueue } from '@features/charts/session/ChartRedrawQueue.ts';
import type { ChartSeriesMorph } from '@features/charts/session/ChartSeriesMorph.ts';
import type { ChartSeriesStore } from '@features/charts/session/ChartSeriesStore.ts';
import type { ChartInteractionState, ChartViewportState } from '@features/charts/session/chartState.ts';

interface ChartPrependResult {
    added: number;
    truncated: boolean;
}

interface ChartDataViewportPort {
    syncToSeries(previousNewestTs: number): void;
    requestDataFit(): void;
}

interface ChartDataCommandsDependencies {
    store: ChartSeriesStore;
    viewportState: ChartViewportState;
    interaction: ChartInteractionState;
    viewport: ChartDataViewportPort;
    redraw: ChartRedrawQueue;
    morph: ChartSeriesMorph;
}

class ChartDataCommands {
    readonly #store: ChartSeriesStore;
    readonly #viewportState: ChartViewportState;
    readonly #interaction: ChartInteractionState;
    readonly #viewport: ChartDataViewportPort;
    readonly #redraw: ChartRedrawQueue;
    readonly #morph: ChartSeriesMorph;

    constructor({ store, viewportState, interaction, viewport, redraw, morph }: ChartDataCommandsDependencies) {
        this.#store = store;
        this.#viewportState = viewportState;
        this.#interaction = interaction;
        this.#viewport = viewport;
        this.#redraw = redraw;
        this.#morph = morph;
    }

    replace(points: ReadonlyArray<ChartPointCandidate> | null, options: { preserveView?: boolean; assumeSorted?: boolean; morph?: boolean } = {}): void {
        const previousNewestTs = this.#newestTs();
        const snapshot = options.morph === true && options.preserveView !== false ? this.#morph.capture() : null;
        this.#morph.stop();
        const result = this.#store.replace(points, options.assumeSorted === undefined ? {} : { assumeSorted: options.assumeSorted });
        if (result.empty) this.#clearEmptyView();
        if (options.preserveView === false) this.#viewport.requestDataFit();
        else this.#viewport.syncToSeries(previousNewestTs);
        this.#morph.begin(snapshot, monotonicMs());
    }

    prepend(points: ReadonlyArray<ChartPointCandidate> | null): ChartPrependResult {
        const previousNewestTs = this.#newestTs();
        const { changed, addedToHead, truncated } = this.#store.prepend(points);
        if (changed) this.#viewport.syncToSeries(previousNewestTs);
        return { added: changed ? addedToHead : 0, truncated };
    }

    appendPoint(point: ChartPointCandidate): void {
        this.#applyLive(() => this.#store.appendPoint(point).changed);
    }

    updateCurrentBar(point: ChartPointCandidate): void {
        this.#applyLive(() => this.#store.updateCurrentBar(point).changed);
    }

    addDataset(definition: DatasetInput): void {
        this.#store.addDataset(definition);
        this.#redraw.request({ data: true });
    }

    clearDatasets(): void {
        this.#store.clearDatasets();
        this.#redraw.request({ data: true });
    }

    applyChartType(type: string): void {
        this.#store.applyChartType(type);
    }

    resizeCapacity(capacity: number): void {
        this.#store.resizeCapacity(capacity);
        this.#redraw.visiblePoints = null;
    }

    #applyLive(mutate: () => boolean): void {
        const previousNewestTs = this.#newestTs();
        const snapshot = this.#viewportState.time.followLive ? this.#morph.capture() : null;
        if (!mutate()) return;
        this.#viewport.syncToSeries(previousNewestTs);
        if (snapshot) this.#morph.begin(snapshot, monotonicMs());
    }

    #newestTs(): number {
        return this.#store.dataLength > 0 ? (this.#store.timestamps[this.#store.dataLength - 1] ?? Number.NaN) : Number.NaN;
    }

    #clearEmptyView(): void {
        this.#viewportState.lastEmittedTimeRange = { startTs: null, endTs: null };
        this.#viewportState.visibleRange = { ...EMPTY_VISIBLE_RANGE };
        this.#viewportState.visibleRangeStats = { min: null, max: null, sum: 0, count: 0 };
        this.#viewportState.scale.min = null;
        this.#viewportState.scale.max = null;
        Object.assign(this.#interaction.crosshair, { visible: false, dataIndex: -1, rawIndex: null });
    }
}

export { ChartDataCommands };
export type { ChartDataCommandsDependencies, ChartDataViewportPort, ChartPrependResult };
