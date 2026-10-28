/* SoAI - Chart viewport ownership [frontend/assets/ts/features/charts/session/ChartViewport.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { clampNumber } from '@core/primitives/clampNumber.ts';
import { monotonicMs } from '@core/time/clock.ts';
import { minutesToMs } from '@core/time/durations.ts';
import type { ChartOptions } from '@features/charts/chartTypes.ts';
import type { RedrawRequest, Scale } from '@features/charts/component/chartComponentTypes.ts';
import type { ChartEventDetail } from '@features/charts/component/effects.ts';
import { createRenderGeometry } from '@features/charts/layout/geometry.ts';
import type { ChartDimensions, RenderGeometry } from '@features/charts/rendering/renderingModels.ts';
import { enforceScaleBounds, panVertical } from '@features/charts/scales/scaleBounds.ts';
import type { ChartConfigurationState, ChartViewportState } from '@features/charts/session/chartState.ts';
import type { ChartEvents } from '@features/charts/session/ChartEvents.ts';
import type { ChartRedrawQueue } from '@features/charts/session/ChartRedrawQueue.ts';
import { isUsableViewport, panByPixels, plotRight, xToTime, type TimeAxisFrame } from '@features/charts/viewport/timeViewport.ts';
import { scaleChartAnimationDurationMs, SERIES_TRANSITION_MS } from '@core/animations/chartMotion.ts';
import { cancelViewportAnimation, shiftViewportAnimation, startViewportAnimation, stepViewportAnimation } from '@features/charts/viewport/viewportAnimation.ts';
import { clampTimeViewport, clampViewportRightEdge, clampViewportScale, resolveSeriesIntervalMs, type ViewportBoundsInput } from '@features/charts/viewport/viewportBounds.ts';
import { alignViewportToNewest, applyViewportFit, DATA_FIT, isNewestVisible, type ViewportFit } from '@features/charts/viewport/viewportFit.ts';

interface ChartViewportSeriesPort {
    readonly dataLength: number;
    readonly timestamps: Float64Array;
}

interface ChartViewportDependencies {
    configuration: ChartConfigurationState;
    state: ChartViewportState;
    series: ChartViewportSeriesPort;
    surface: { readonly element: HTMLElement; getCanvasSize(): { width: number; height: number }; resize(): boolean };
    redraw: ChartRedrawQueue;
    events: ChartEvents;
}

const ZOOM_EPSILON_RATIO = 1e-6;
const FULL_REDRAW: RedrawRequest = { static: true, data: true, interaction: true };

class ChartViewport {
    readonly #configuration: ChartConfigurationState;
    readonly #state: ChartViewportState;
    readonly #series: ChartViewportSeriesPort;
    readonly #surface: ChartViewportDependencies['surface'];
    readonly #redraw: ChartRedrawQueue;
    readonly #events: ChartEvents;

    constructor({ configuration, state, series, surface, redraw, events }: ChartViewportDependencies) {
        this.#configuration = configuration;
        this.#state = state;
        this.#series = series;
        this.#surface = surface;
        this.#redraw = redraw;
        this.#events = events;
    }

    get status(): Readonly<{ isAnimating: boolean; isDragging: boolean; isAtTail: boolean }> {
        return Object.freeze({ isAnimating: this.#state.animation.active || this.#state.scaleGlide.active, isDragging: this.#state.pan.isDragging, isAtTail: this.#state.time.followLive });
    }

    get intervalMs(): number {
        return resolveSeriesIntervalMs(this.#configuration.options.expectedSampleIntervalMs, this.#series.timestamps, this.#series.dataLength);
    }

    get element(): HTMLElement {
        return this.#surface.element;
    }

    get chartOptions(): ChartOptions {
        return this.#configuration.options;
    }

    get scale(): Scale {
        return this.#state.scale;
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

    getRenderGeometry(dimensions: ChartDimensions = this.getChartDimensions()): RenderGeometry | null {
        return createRenderGeometry(dimensions, this.#state.time, this.intervalMs);
    }

    panByPixels(deltaPx: number): boolean {
        const input = this.#boundsInput();
        const time = this.#state.time;
        if (!input || !isUsableViewport(time) || !Number.isFinite(deltaPx) || deltaPx === 0) return false;
        cancelViewportAnimation(this.#state.animation);
        const previousRightEdgeTs = time.rightEdgeTs;
        panByPixels(time, deltaPx);
        const requestedRightEdgeTs = time.rightEdgeTs;
        clampTimeViewport(time, input);
        if (deltaPx > 0 && input.oldestNavigableTs !== null && time.rightEdgeTs > requestedRightEdgeTs) {
            this.#state.historyBoundaryHitAt = monotonicMs();
            this.#redraw.request({ data: true });
        }
        return this.#commit(input, time.rightEdgeTs !== previousRightEdgeTs);
    }

    zoomBy(anchorX: number, factor: number, animate: boolean): boolean {
        const target = this.#targetFrame();
        return target !== null && Number.isFinite(factor) && factor > 0 && this.#zoomAround(target, anchorX, target.msPerPx * factor, animate);
    }

    zoomTo(anchorX: number, msPerPx: number): boolean {
        const dimensions = this.getChartDimensions();
        const time = this.#state.time;
        cancelViewportAnimation(this.#state.animation);
        return isUsableViewport(time) && this.#zoomAround({ plotLeft: dimensions.left, plotWidth: dimensions.chartWidth, rightEdgeTs: time.rightEdgeTs, msPerPx: time.msPerPx }, anchorX, msPerPx, false);
    }

    fitTimeRange(minutes: number): boolean {
        const durationMs = minutesToMs(Number(minutes));
        if (!Number.isFinite(durationMs) || durationMs <= 0) return false;
        return this.#requestFit({ mode: 'duration', durationMs });
    }

    resetZoom(): boolean {
        return this.#requestFit(DATA_FIT);
    }

    requestDataFit(): void {
        this.#state.pendingFit ??= DATA_FIT;
        this.syncToSeries();
    }

    alignToLatest(): void {
        const input = this.#boundsInput();
        const time = this.#state.time;
        if (!input || !isUsableViewport(time)) return;
        cancelViewportAnimation(this.#state.animation);
        alignViewportToNewest(time, input);
        this.#commit(input, true);
    }

    syncToSeries(previousNewestTs: number = Number.NaN): void {
        const input = this.#boundsInput();
        const { time, animation } = this.#state;
        if (!input) {
            this.#redraw.request(FULL_REDRAW);
            return;
        }
        if (this.#state.pendingFit || !isUsableViewport(time)) {
            if (applyViewportFit(time, this.#state.pendingFit ?? DATA_FIT, input)) {
                this.#state.pendingFit = null;
                cancelViewportAnimation(animation);
            }
        } else {
            const deltaTs = input.newestTs - previousNewestTs;
            if (time.followLive && Number.isFinite(deltaTs) && deltaTs !== 0) this.#followNewest(deltaTs);
            if (!animation.active) clampTimeViewport(time, input);
        }
        this.#commit(input, true);
    }

    advanceAnimation(now: number): boolean {
        const { time, animation } = this.#state;
        if (!animation.active) return false;
        const animationTime = scaleChartAnimationDurationMs(animation.durationMs, this.#surface.element) === 0 ? Math.max(now, animation.startTime + animation.durationMs) : now;
        const running = stepViewportAnimation(animation, time, animationTime);
        const input = this.#boundsInput();
        if (input) clampTimeViewport(time, input);
        this.#redraw.request(FULL_REDRAW);
        return running;
    }

    setAutoScale(enabled: boolean): void {
        this.#state.scale.auto = enabled;
        this.#configuration.options.autoScale = enabled;
    }

    enforceScaleBounds(options: { preserveRange?: boolean } = {}): void {
        enforceScaleBounds(this, options);
    }

    panVertical(deltaY: number): boolean {
        return panVertical(this, deltaY);
    }

    requestRedraw(requirements?: RedrawRequest): void {
        this.#redraw.request(requirements);
    }

    chartEmit(event: string, detail: ChartEventDetail): void {
        this.#events.emit(event, detail);
    }

    #requestFit(fit: ViewportFit): boolean {
        this.#state.pendingFit = fit;
        this.syncToSeries();
        return this.#state.pendingFit === null;
    }

    #targetFrame(): TimeAxisFrame | null {
        const { time, animation } = this.#state;
        if (!isUsableViewport(time)) return null;
        const { left, chartWidth } = this.getChartDimensions();
        if (!animation.active) return { plotLeft: left, plotWidth: chartWidth, rightEdgeTs: time.rightEdgeTs, msPerPx: time.msPerPx };
        return { plotLeft: left, plotWidth: chartWidth, rightEdgeTs: animation.toAnchorTs + animation.anchorOffsetPx * animation.toMsPerPx, msPerPx: animation.toMsPerPx };
    }

    #followNewest(deltaTs: number): void {
        const { time, animation } = this.#state;
        if ((animation.active && animation.fromMsPerPx !== animation.toMsPerPx) || Math.abs(deltaTs) < time.msPerPx) {
            time.rightEdgeTs += deltaTs;
            shiftViewportAnimation(animation, deltaTs);
            return;
        }
        const rightEdgeTs = (animation.active ? animation.toAnchorTs + animation.anchorOffsetPx * animation.toMsPerPx : time.rightEdgeTs) + deltaTs;
        startViewportAnimation(animation, time, { msPerPx: time.msPerPx, anchorTs: rightEdgeTs, anchorOffsetPx: 0 }, scaleChartAnimationDurationMs(SERIES_TRANSITION_MS, this.#surface.element), monotonicMs());
    }

    #zoomAround(frame: TimeAxisFrame, anchorX: number, requestedMsPerPx: number, animate: boolean): boolean {
        const input = this.#boundsInput();
        if (!input || !Number.isFinite(requestedMsPerPx) || requestedMsPerPx <= 0) return false;
        const anchorOffsetPx = plotRight(frame) - clampNumber(anchorX, frame.plotLeft, plotRight(frame));
        const anchorTs = xToTime(frame, plotRight(frame) - anchorOffsetPx);
        const msPerPx = clampViewportScale(requestedMsPerPx, input);
        if (Math.abs(msPerPx / frame.msPerPx - 1) < ZOOM_EPSILON_RATIO) return false;
        const rightEdgeTs = clampViewportRightEdge(anchorTs + anchorOffsetPx * msPerPx, msPerPx, input);
        const target = { msPerPx, anchorTs: rightEdgeTs - anchorOffsetPx * msPerPx, anchorOffsetPx };
        const durationMs = animate && this.#configuration.options.enableSmoothZoom ? scaleChartAnimationDurationMs(this.#configuration.options.zoomEasingMs, this.#surface.element) : 0;
        startViewportAnimation(this.#state.animation, this.#state.time, target, durationMs, monotonicMs());
        this.#state.time.followLive = isNewestVisible({ rightEdgeTs, msPerPx, followLive: false }, input.newestTs);
        this.#redraw.request(FULL_REDRAW);
        return true;
    }

    #commit(input: ViewportBoundsInput, changed: boolean): boolean {
        if (!this.#state.animation.active) this.#state.time.followLive = isNewestVisible(this.#state.time, input.newestTs);
        if (changed) this.#redraw.request(FULL_REDRAW);
        return changed;
    }

    #boundsInput(): ViewportBoundsInput | null {
        const { dataLength, timestamps } = this.#series;
        const plotWidth = this.getChartDimensions().chartWidth;
        const oldestLoadedTs = timestamps[0] ?? Number.NaN;
        const newestTs = timestamps[dataLength - 1] ?? Number.NaN;
        if (dataLength === 0 || plotWidth <= 0 || !Number.isFinite(oldestLoadedTs) || !Number.isFinite(newestTs)) return null;
        const options = this.#configuration.options;
        const navigableTs = options.history ? options.history.oldestNavigableTs : oldestLoadedTs;
        return {
            plotWidth,
            intervalMs: this.intervalMs,
            newestTs,
            oldestLoadedTs,
            oldestNavigableTs: navigableTs === null ? null : Math.max(navigableTs, oldestLoadedTs),
            maxDataPoints: options.maxDataPoints
        };
    }
}

export { ChartViewport };
export type { ChartViewportDependencies, ChartViewportSeriesPort };
