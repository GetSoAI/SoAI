/* SoAI - Chart data workflow coordination [frontend/assets/ts/features/charts/session/ChartDataCommands.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import { isFin } from '@features/charts/component/chartComponentStatics.ts';
import type { DatasetInput } from '@features/charts/chartTypes.ts';
import type { ChartPointCandidate } from '@features/charts/data/chartPointTypes.ts';
import type { ChartRedrawQueue } from '@features/charts/session/ChartRedrawQueue.ts';
import type { ChartSeriesStore } from '@features/charts/session/ChartSeriesStore.ts';
import type { ChartInteractionState, ChartViewportState } from '@features/charts/session/chartState.ts';

interface ChartDataViewportPort {
    resetZoom(): void;
    capture(): Record<string, JsonValue | null | undefined>;
    restore(snapshot: Record<string, JsonValue | null | undefined>): void;
    recalculateZoomBounds(): void;
    clampPanOffset(): void;
    getMaxOffset(): number;
    applyIntent(source: string): void;
}

interface ChartDataCommandsDependencies {
    store: ChartSeriesStore;
    viewportState: ChartViewportState;
    interaction: ChartInteractionState;
    viewport: ChartDataViewportPort;
    redraw: ChartRedrawQueue;
}

class ChartDataCommands {
    readonly #store: ChartSeriesStore;
    readonly #viewportState: ChartViewportState;
    readonly #interaction: ChartInteractionState;
    readonly #viewport: ChartDataViewportPort;
    readonly #redraw: ChartRedrawQueue;

    constructor({ store, viewportState, interaction, viewport, redraw }: ChartDataCommandsDependencies) {
        this.#store = store;
        this.#viewportState = viewportState;
        this.#interaction = interaction;
        this.#viewport = viewport;
        this.#redraw = redraw;
    }

    replace(points: ReadonlyArray<ChartPointCandidate> | null, options: { preserveView?: boolean; assumeSorted?: boolean } = {}): void {
        const preserveView = options.preserveView !== false;
        const hadPriorData = this.#store.dataLength > 0;
        const snapshot = preserveView && hadPriorData ? this.#viewport.capture() : null;
        const result = this.#store.replace(points, options.assumeSorted === undefined ? {} : { assumeSorted: options.assumeSorted });
        this.#viewport.recalculateZoomBounds();
        if (result.empty) {
            this.#clearEmptyView();
            this.#viewport.resetZoom();
        } else if (!hadPriorData || !snapshot) {
            this.#viewport.resetZoom();
        } else {
            this.#viewport.restore(this.#adjustSnapshot(snapshot, result.startIndex));
        }
        this.#redraw.request({ static: true, data: true, interaction: true });
        this.#applyPendingIntent();
    }

    prepend(points: ReadonlyArray<ChartPointCandidate> | null): void {
        const result = this.#store.prepend(points);
        if (!result.changed) return;
        this.#viewport.recalculateZoomBounds();
        this.#viewportState.pan.offset += result.addedToHead;
        this.#viewportState.pan.startOffset = this.#viewportState.pan.offset;
        this.#viewportState.pan.targetOffset = this.#viewportState.pan.offset;
        this.#viewport.clampPanOffset();
        this.#redraw.request({ data: true });
        this.#applyPendingIntent();
    }

    appendPoint(point: ChartPointCandidate): void {
        const result = this.#store.appendPoint(point);
        if (!result.changed) return;
        if (result.nextLength !== result.previousLength) this.#viewport.recalculateZoomBounds();
        if (result.removedFromHead > 0 && !this.#viewportState.pan.isAtTail) this.#viewportState.pan.offset = Math.max(0, this.#viewportState.pan.offset - result.removedFromHead);
        if (this.#viewportState.pan.isAtTail) this.#viewportState.pan.offset = this.#viewport.getMaxOffset();
        this.#viewportState.pan.startOffset = this.#viewportState.pan.offset;
        this.#viewportState.pan.targetOffset = this.#viewportState.pan.offset;
        this.#viewportState.pan.isZooming = false;
        this.#viewport.clampPanOffset();
        this.#redraw.request();
        this.#applyPendingIntent();
    }

    updateCurrentBar(point: ChartPointCandidate): void {
        const result = this.#store.updateCurrentBar(point);
        if (!result.changed) return;
        if (result.previousLength === 0) this.#viewport.recalculateZoomBounds();
        this.#redraw.request();
        this.#applyPendingIntent();
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
        const result = this.#store.resizeCapacity(capacity);
        this.#viewportState.pan.offset = Math.max(0, this.#viewportState.pan.offset - result.removedFromHead);
        this.#viewportState.pan.startOffset = this.#viewportState.pan.offset;
        this.#viewportState.pan.targetOffset = this.#viewportState.pan.offset;
        this.#redraw.visiblePoints = null;
    }

    #clearEmptyView(): void {
        this.#viewportState.lastEmittedTimeRange = { start: 0, end: 0, startTs: null, endTs: null };
        this.#viewportState.visibleRange = { start: 0, end: 0, displayCount: 0, totalSlots: 0, marginSlots: 0, offsetFraction: 0 };
        this.#viewportState.visibleRangeStats = { min: null, max: null, sum: 0, count: 0 };
        this.#viewportState.scale.min = null;
        this.#viewportState.scale.max = null;
        Object.assign(this.#interaction.crosshair, { visible: false, dataIndex: -1, rawIndex: null });
    }

    #adjustSnapshot(snapshot: Record<string, JsonValue | null | undefined>, removedFromHead: number): Record<string, JsonValue | null | undefined> {
        if (removedFromHead <= 0) return snapshot;
        const adjusted = { ...snapshot };
        if (isFin(adjusted['panOffset'])) adjusted['panOffset'] = Math.max(0, Number(adjusted['panOffset']) - removedFromHead);
        if (isFin(adjusted['panTargetOffset'])) adjusted['panTargetOffset'] = Math.max(0, Number(adjusted['panTargetOffset']) - removedFromHead);
        return adjusted;
    }

    #applyPendingIntent(): void {
        if (this.#viewportState.pendingViewportIntent) this.#viewport.applyIntent('data');
    }
}

export { ChartDataCommands };
export type { ChartDataCommandsDependencies, ChartDataViewportPort };
