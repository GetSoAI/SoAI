/* SoAI - Chart viewport ownership [frontend/assets/ts/features/charts/session/ChartViewport.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import type { ChartOptions, CrosshairState, OhlcValues } from '@features/charts/chartTypes.ts';
import type { PanState, RedrawRequest, Scale, SlotMetrics, ViewportIntent, VisibleRange, ZoomState } from '@features/charts/component/chartComponentTypes.ts';
import { getMaxOffsetForMetrics, getPixelsPerBar, getSlotMetrics, getSlotMetricsForLevel } from '@features/charts/component/data/visibleRange.ts';
import type { ChartEventDetail } from '@features/charts/component/effects.ts';
import { captureViewState, restoreViewState } from '@features/charts/component/data/viewState.ts';
import { alignToLatest, applyViewportIntent, fitToTimeRangeMinutes, fitToWindow, markViewportManual, resetZoom } from '@features/charts/component/interactions/viewportIntent.ts';
import { normalizeClampedFloat, recalculateZoomBounds } from '@features/charts/component/state/actions.ts';
import { applyInertialPanning, applySmoothZoom, clampPanOffset } from '@features/charts/interaction/viewportMotion.ts';
import type { ChartDimensions } from '@features/charts/rendering/renderingModels.ts';
import { enforceScaleBounds, panVertical } from '@features/charts/scales/scaleBounds.ts';
import type { ChartConfigurationState, ChartInteractionState, ChartViewportState } from '@features/charts/session/chartState.ts';
import type { ChartRedrawQueue } from '@features/charts/session/ChartRedrawQueue.ts';
import type { ChartEvents } from '@features/charts/session/ChartEvents.ts';

interface ChartViewportSeriesPort {
    readonly dataLength: number;
    readonly timestamps: Float64Array;
    effectiveLength(): number;
    closeValue(index: number): number | undefined;
    ohlcAt(index: number, target?: OhlcValues | null): OhlcValues;
}

interface ChartViewportDependencies {
    configuration: ChartConfigurationState;
    state: ChartViewportState;
    interaction: ChartInteractionState;
    series: ChartViewportSeriesPort;
    surface: { readonly element: HTMLElement; getCanvasSize(): { width: number; height: number }; resize(): boolean };
    redraw: ChartRedrawQueue;
    events: ChartEvents;
}

class ChartViewport {
    readonly #configuration: ChartConfigurationState;
    readonly #state: ChartViewportState;
    readonly #interaction: ChartInteractionState;
    readonly #series: ChartViewportSeriesPort;
    readonly #surface: ChartViewportDependencies['surface'];
    readonly #redraw: ChartRedrawQueue;
    readonly #events: ChartEvents;

    constructor({ configuration, state, interaction, series, surface, redraw, events }: ChartViewportDependencies) {
        this.#configuration = configuration;
        this.#state = state;
        this.#interaction = interaction;
        this.#series = series;
        this.#surface = surface;
        this.#redraw = redraw;
        this.#events = events;
    }

    get status(): Readonly<{ isAnimating: boolean; isDragging: boolean; isAtTail: boolean }> {
        return Object.freeze({ isAnimating: this.#state.zoom.isAnimating, isDragging: this.#state.pan.isDragging, isAtTail: this.#state.pan.isAtTail });
    }

    get yAxisMinRange(): number {
        return this.#state.yAxisMinRange;
    }

    resize(): boolean {
        return this.#surface.resize();
    }

    getChartDimensions(): ChartDimensions {
        const { width, height } = this.#surface.getCanvasSize();
        const padding = this.#configuration.padding;
        const chartWidth = Math.max(0, width - padding.left - padding.right);
        const chartHeight = Math.max(0, height - padding.top - padding.bottom - this.#configuration.options.bottomAxisPadding);
        return { top: padding.top, left: padding.left, chartWidth, chartHeight, width, height, right: padding.left + chartWidth };
    }

    getSlotMetrics(): SlotMetrics {
        return getSlotMetrics(this, this);
    }

    getSlotMetricsForLevel(level: number | null | undefined): SlotMetrics {
        return getSlotMetricsForLevel(this, this, level);
    }

    getMaxOffset(metrics: SlotMetrics | null = null): number {
        return getMaxOffsetForMetrics(this, this, metrics);
    }

    getPixelsPerBar(): number {
        return getPixelsPerBar(this, this);
    }

    getMaxOffsetForMetrics(metrics: SlotMetrics | null | undefined = null): number {
        return this.getMaxOffset(metrics);
    }

    recalculateZoomBounds(): void {
        recalculateZoomBounds(this, { preserveLevel: true });
    }

    clampPanOffset(): void {
        clampPanOffset(this);
    }

    resetZoom(options: { alignToTail?: boolean } = {}): void {
        resetZoom(this, options);
    }

    fitTimeRange(minutes: number, options: { align?: string } = {}): boolean {
        return fitToTimeRangeMinutes(this, minutes, options);
    }

    fitWindow(start: number, end: number, options: { align?: string } = {}): boolean {
        return fitToWindow(this, start, end, options);
    }

    alignToLatest(): void {
        alignToLatest(this);
    }

    applyIntent(_source: string = 'default'): void {
        applyViewportIntent(this);
    }

    markManual(source: string = 'manual'): void {
        markViewportManual(this, source);
    }

    capture(): Record<string, JsonValue | null | undefined> {
        return captureViewState(this);
    }

    restore(snapshot: Record<string, JsonValue | null | undefined>): void {
        restoreViewState(this, snapshot);
    }

    setAutoScale(enabled: boolean | string | null | undefined): void {
        const normalized = Boolean(enabled);
        this.#state.scale.auto = normalized;
        this.#configuration.options.autoScale = normalized;
    }

    enforceScaleBounds(options: { preserveRange?: boolean } = {}): void {
        enforceScaleBounds(this, options);
    }

    panVertical(deltaY: number): boolean {
        return panVertical(this, deltaY);
    }

    advanceInertialPanning(): void {
        applyInertialPanning(this);
    }

    advanceSmoothZoom(): void {
        applySmoothZoom(this);
    }

    requestRedraw(requirements?: RedrawRequest): void {
        this.#redraw.request(requirements);
    }

    chartEmit(event: string, detail: ChartEventDetail): void {
        this.#events.emit(event, detail);
    }

    getEffectiveDataLength(): number {
        return this.#series.effectiveLength();
    }
    getCloseValue(index: number): number | undefined {
        return this.#series.closeValue(index);
    }
    getOhlcForIndex(index: number, target?: OhlcValues | null): OhlcValues {
        return this.#series.ohlcAt(index, target ?? null);
    }
    normalizeClampedFloat(value: number | string | null | undefined, fallback: number, min?: number, max?: number): number {
        return normalizeClampedFloat(value, fallback, min, max);
    }
    customBezierEasing(time: number, x1: number, y1: number, x2: number, y2: number): number {
        const cx = 3 * x1;
        const bx = 3 * (x2 - x1) - cx;
        const ax = 1 - cx - bx;
        const cy = 3 * y1;
        const by = 3 * (y2 - y1) - cy;
        const ay = 1 - cy - by;
        let progress = time;
        for (let iteration = 0; iteration < 8; iteration += 1) {
            const offset = ((ax * progress + bx) * progress + cx) * progress - time;
            if (Math.abs(offset) < 0.001) break;
            const derivative = (3 * ax * progress + 2 * bx) * progress + cx;
            if (Math.abs(derivative) < 1e-6) break;
            progress -= offset / derivative;
        }
        return ((ay * progress + by) * progress + cy) * progress;
    }

    get element(): HTMLElement {
        return this.#surface.element;
    }
    get chartOptions(): ChartOptions {
        return this.#configuration.options;
    }
    get dataLength(): number {
        return this.#series.dataLength;
    }
    get timestamps(): Float64Array {
        return this.#series.timestamps;
    }
    get baseBarPixelWidth(): number {
        return this.#state.baseBarPixelWidth;
    }
    get zoom(): ZoomState {
        return this.#state.zoom;
    }
    get pan(): PanState {
        return this.#state.pan;
    }
    get scale(): Scale {
        return this.#state.scale;
    }
    get crosshair(): CrosshairState {
        return this.#interaction.crosshair;
    }
    get visibleRange(): VisibleRange {
        return this.#state.visibleRange;
    }
    get suspendIntentRecording(): boolean {
        return this.#state.suspendIntentRecording;
    }
    set suspendIntentRecording(value: boolean) {
        this.#state.suspendIntentRecording = value;
    }
    get viewportIntent(): ViewportIntent | null {
        return this.#state.viewportIntent;
    }
    set viewportIntent(value: ViewportIntent | null) {
        this.#state.viewportIntent = value;
    }
    get pendingViewportIntent(): ViewportIntent | null {
        return this.#state.pendingViewportIntent;
    }
    set pendingViewportIntent(value: ViewportIntent | null) {
        this.#state.pendingViewportIntent = value;
    }
    get isHistoricalDataLoading(): boolean {
        return this.#state.isHistoricalDataLoading;
    }
    set isHistoricalDataLoading(value: boolean) {
        this.#state.isHistoricalDataLoading = value;
    }
    get lastHistoricalRequestTimestamp(): number | null {
        return this.#state.lastHistoricalRequestTimestamp;
    }
    set lastHistoricalRequestTimestamp(value: number | null) {
        this.#state.lastHistoricalRequestTimestamp = value;
    }
}

export { ChartViewport };
export type { ChartViewportDependencies, ChartViewportSeriesPort };
