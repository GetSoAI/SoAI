/* SoAI - Charts feature viewport intent [frontend/assets/ts/features/charts/component/interactions/viewportIntent.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { clampNumber } from '@core/primitives/clampNumber.ts';
import { monotonicMs } from '@core/time/clock.ts';
import { isString } from '@core/typeGuards.ts';
import type { ChartOptions } from '@features/charts/chartTypes.ts';
import { isFin, normalizeAlignOption } from '@features/charts/component/chartComponentStatics.ts';
import type { PanState, SlotMetrics, ViewportIntent, ZoomState } from '@features/charts/component/chartComponentTypes.ts';
import { findFirstIndexAtOrAfter, findLastIndexAtOrBefore } from '@features/charts/component/data/timestampIndex.ts';

interface ViewportHost {
    element: HTMLElement | null;
    chartOptions: ChartOptions;
    dataLength: number;
    timestamps: Float64Array;
    baseBarPixelWidth: number;
    zoom: ZoomState;
    pan: PanState;
    suspendIntentRecording: boolean;
    viewportIntent: ViewportIntent | null;
    pendingViewportIntent: ViewportIntent | null;

    clampPanOffset: () => void;
    getChartDimensions: () => { chartWidth: number };
    getEffectiveDataLength: () => number;
    getMaxOffsetForMetrics: (metrics: SlotMetrics | null | undefined) => number;
    getSlotMetricsForLevel: (level: number | null | undefined) => SlotMetrics;
    requestRedraw: (request?: { static?: boolean; data?: boolean; interaction?: boolean }) => void;
}

interface FitViewportMetrics {
    level: number;
    metrics: SlotMetrics;
}

const resolveFitViewportMetrics = (chart: ViewportHost, visiblePointCount: number, displayMargin: number): FitViewportMetrics | null => {
    const { chartWidth = 0 } = chart.getChartDimensions();
    if (chartWidth <= 0) return null;
    const displayedPointCount = Math.max(1, visiblePointCount + displayMargin);
    let zoomLevel = chartWidth / (chart.baseBarPixelWidth * displayedPointCount);
    if (!isFin(zoomLevel) || zoomLevel <= 0) return null;
    zoomLevel = clampNumber(zoomLevel, chart.zoom.minLevel, chart.zoom.maxLevel);
    let metrics = chart.getSlotMetricsForLevel(zoomLevel);
    if (metrics.dataSlots < visiblePointCount && zoomLevel > chart.zoom.minLevel) {
        const pointOverflowRatio = visiblePointCount / Math.max(1, metrics.dataSlots);
        if (pointOverflowRatio > 1.01) {
            zoomLevel = Math.max(chart.zoom.minLevel, zoomLevel / (pointOverflowRatio * 1.02));
            metrics = chart.getSlotMetricsForLevel(zoomLevel);
        }
    }
    return { level: zoomLevel, metrics };
};

const applyFitViewportState = (chart: ViewportHost, fit: FitViewportMetrics, offset: number, maxOffset: number): void => {
    chart.zoom.level = chart.zoom.targetLevel = fit.level;
    chart.zoom.isAnimating = false;
    chart.pan.offset = chart.pan.targetOffset = chart.pan.startOffset = clampNumber(offset, 0, maxOffset);
    chart.pan.velocity = 0;
    chart.pan.isZooming = false;
    chart.pan.isAtTail = Math.abs(chart.pan.offset - maxOffset) < 1e-3;
    chart.clampPanOffset();
};

const setViewportIntent = (chart: ViewportHost, intent: ViewportIntent | null, options: { pending?: boolean } = {}): void => {
    if (chart.suspendIntentRecording) return;
    const pending = options.pending === true;
    if (!intent) {
        chart.viewportIntent = null;
        if (!pending) chart.pendingViewportIntent = null;
        return;
    }
    const timestampedIntent: ViewportIntent = { ...intent, timestamp: monotonicMs() };
    chart.viewportIntent = timestampedIntent;
    chart.pendingViewportIntent = pending ? { ...timestampedIntent } : null;
};

const queueViewportIntent = (chart: ViewportHost, intent: ViewportIntent | null): void => {
    if (!intent) return;
    const timestampedIntent: ViewportIntent = { ...intent, timestamp: monotonicMs() };
    chart.viewportIntent = timestampedIntent;
    chart.pendingViewportIntent = { ...timestampedIntent };
};

const markViewportManual = (chart: ViewportHost, source: string = 'manual'): void => {
    chart.viewportIntent = { mode: 'manual', source, timestamp: monotonicMs() };
    chart.pendingViewportIntent = null;
};

const fitToIndexWindow = (chart: ViewportHost, first: number, last: number, options: { align?: string } = {}): boolean => {
    if (!chart.element || chart.getEffectiveDataLength() <= 0) return false;
    const alignment = options.align ?? 'tail';
    const pointCount = Math.max(1, last - first + 1);
    const displayMargin = alignment === 'tail' ? Math.min(chart.chartOptions.rightMarginBars || 0, Math.ceil(Math.sqrt(chart.dataLength)) - 1) : 0;
    const fit = resolveFitViewportMetrics(chart, pointCount, displayMargin);
    if (fit === null) return false;
    const normalizedAlignment = normalizeAlignOption(alignment);
    const offset = normalizedAlignment === 'head' ? first : normalizedAlignment === 'center' ? Math.max(0, Math.round((first + last) / 2 - fit.metrics.dataSlots / 2)) : Math.max(0, last - fit.metrics.dataSlots + 1);
    const maximumOffset = chart.getMaxOffsetForMetrics(fit.metrics);
    applyFitViewportState(chart, fit, offset, maximumOffset);
    chart.requestRedraw();
    return true;
};

const fitViewToData = (chart: ViewportHost, options: { alignToTail?: boolean } = {}): boolean => {
    const alignToTail = options.alignToTail !== false;
    if (!chart.element || chart.getEffectiveDataLength() <= 0) return false;
    const baseLength = chart.getEffectiveDataLength();
    const displayMargin = alignToTail ? Math.min(chart.chartOptions.rightMarginBars || 0, Math.ceil(Math.sqrt(baseLength)) - 1) : 0;
    const fit = resolveFitViewportMetrics(chart, baseLength, displayMargin);
    if (fit === null) return false;
    const maximumOffset = chart.getMaxOffsetForMetrics(fit.metrics);
    applyFitViewportState(chart, fit, alignToTail ? maximumOffset : 0, maximumOffset);
    return true;
};

const applyFitToTimeRangeInternal = (chart: ViewportHost, intent: ViewportIntent): boolean => {
    const durationMs = Number(intent['durationMs'] ?? 0);
    if (!durationMs || durationMs <= 0 || chart.dataLength <= 0) return false;
    const endTimestamp = Number(chart.timestamps[chart.dataLength - 1]);
    if (!isFin(endTimestamp)) return false;
    const startIndex = findFirstIndexAtOrAfter(chart.timestamps, chart.dataLength, endTimestamp - durationMs);
    const alignRaw = intent['align'];
    const align = isString(alignRaw) ? alignRaw : 'tail';
    return startIndex === -1 ? false : fitToIndexWindow(chart, startIndex, chart.dataLength - 1, { align });
};

const applyFitToWindowInternal = (chart: ViewportHost, intent: ViewportIntent): boolean => {
    const startTimestamp = Number(intent['startTimestamp']);
    const endTimestamp = Number(intent['endTimestamp']);
    if (!isFin(startTimestamp) || !isFin(endTimestamp) || chart.dataLength <= 0) return false;
    const startIndex = findFirstIndexAtOrAfter(chart.timestamps, chart.dataLength, Math.min(startTimestamp, endTimestamp));
    const endIndex = findLastIndexAtOrBefore(chart.timestamps, chart.dataLength, Math.max(startTimestamp, endTimestamp));
    const alignRaw = intent['align'];
    const align = isString(alignRaw) ? alignRaw : 'tail';
    return startIndex === -1 || endIndex === -1 || endIndex < startIndex ? false : fitToIndexWindow(chart, startIndex, endIndex, { align });
};

const executeViewportIntent = (chart: ViewportHost, intent: ViewportIntent | null): boolean => {
    if (!intent) return false;
    const alignToTail = intent['alignToTail'] !== false;
    return intent.mode === 'timeRange' ? applyFitToTimeRangeInternal(chart, intent) : intent.mode === 'window' ? applyFitToWindowInternal(chart, intent) : intent.mode === 'fitData' ? fitViewToData(chart, { alignToTail }) : false;
};

const applyViewportIntent = (chart: ViewportHost): boolean => {
    const intent = chart.pendingViewportIntent || chart.viewportIntent;
    if (!intent || intent.mode === 'manual') return false;
    chart.suspendIntentRecording = true;
    let applied = false;
    try {
        applied = executeViewportIntent(chart, intent);
    } finally {
        chart.suspendIntentRecording = false;
    }
    if (applied) chart.pendingViewportIntent = null;
    else if (!chart.pendingViewportIntent && intent.mode !== 'manual') chart.pendingViewportIntent = { ...intent, timestamp: monotonicMs() };
    return applied;
};

const resetZoom = (chart: ViewportHost, options: { alignToTail?: boolean } = {}): void => {
    const alignToTail = options.alignToTail !== false;
    const intent: ViewportIntent = { mode: 'fitData', alignToTail };
    const applied = fitViewToData(chart, { alignToTail });
    if (!applied) {
        const resetLevel = clampNumber(1, chart.zoom.minLevel, chart.zoom.maxLevel);
        chart.zoom.level = chart.zoom.targetLevel = resetLevel;
        chart.zoom.isAnimating = false;
        chart.pan.offset = alignToTail ? chart.getMaxOffsetForMetrics(chart.getSlotMetricsForLevel(resetLevel)) : 0;
        chart.pan.startOffset = chart.pan.targetOffset = chart.pan.offset;
        chart.pan.isZooming = false;
        chart.pan.velocity = 0;
        chart.clampPanOffset();
    }
    if (!chart.suspendIntentRecording) {
        if (applied) setViewportIntent(chart, intent);
        else queueViewportIntent(chart, intent);
    }
    chart.requestRedraw();
};

const fitToWindow = (chart: ViewportHost, startTimestampInput: number, endTimestampInput: number, options: { align?: string } = {}): boolean => {
    const alignment = options.align ?? 'tail';
    const startTimestamp = Number(startTimestampInput);
    const endTimestamp = Number(endTimestampInput);
    const hasValidRange = isFin(startTimestamp) && isFin(endTimestamp);
    const intent: ViewportIntent = { mode: 'window', startTimestamp, endTimestamp, align: normalizeAlignOption(alignment) };
    const applied = hasValidRange ? applyFitToWindowInternal(chart, intent) : false;
    if (!chart.suspendIntentRecording && hasValidRange) {
        if (applied) setViewportIntent(chart, intent);
        else queueViewportIntent(chart, intent);
    }
    return applied;
};

const fitToTimeRangeMs = (chart: ViewportHost, durationInputMs: number, options: { align?: string } = {}): boolean => {
    const alignment = options.align ?? 'tail';
    const durationMs = Number(durationInputMs);
    const hasValidDuration = isFin(durationMs) && durationMs > 0;
    const intent: ViewportIntent = { mode: 'timeRange', durationMs, align: normalizeAlignOption(alignment) };
    const applied = hasValidDuration ? applyFitToTimeRangeInternal(chart, intent) : false;
    if (!chart.suspendIntentRecording && hasValidDuration) {
        if (applied) setViewportIntent(chart, intent);
        else queueViewportIntent(chart, intent);
    }
    return applied;
};

const fitToTimeRangeMinutes = (chart: ViewportHost, durationMinutes: number, options: { align?: string } = {}): boolean => fitToTimeRangeMs(chart, Number(durationMinutes) * 60000, options);

const alignToLatest = (chart: ViewportHost): void => {
    chart.pan.offset = chart.pan.targetOffset = chart.pan.startOffset = chart.getMaxOffsetForMetrics(null);
    chart.pan.isZooming = false;
    chart.pan.velocity = 0;
    chart.clampPanOffset();
    chart.requestRedraw();
};

export { alignToLatest, applyFitToTimeRangeInternal, applyFitToWindowInternal, applyViewportIntent, executeViewportIntent, fitToIndexWindow, fitToTimeRangeMinutes, fitToTimeRangeMs, fitToWindow, fitViewToData, markViewportManual, queueViewportIntent, resetZoom, setViewportIntent };
