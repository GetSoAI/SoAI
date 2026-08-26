/* SoAI - Chart rendering capability graph composition [frontend/assets/ts/features/charts/session/createChartRenderingScene.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ChartRenderingScene } from '@features/charts/rendering/chartRenderingHost.ts';
import type { ChartFormatting } from '@features/charts/session/ChartFormatting.ts';
import type { ChartLoadingIndicator } from '@features/charts/session/ChartLoadingIndicator.ts';
import type { ChartRedrawQueue } from '@features/charts/session/ChartRedrawQueue.ts';
import type { ChartSeriesStore } from '@features/charts/session/ChartSeriesStore.ts';
import type { ChartSurface } from '@features/charts/session/ChartSurface.ts';
import type { ChartTheme } from '@features/charts/session/ChartTheme.ts';
import type { ChartViewport } from '@features/charts/session/ChartViewport.ts';
import type { ChartState } from '@features/charts/session/chartState.ts';

interface ChartRenderingOwners {
    state: ChartState;
    surface: Pick<ChartSurface, 'element' | 'contexts' | 'offscreenCanvas' | 'offscreenContext' | 'canvasBaseBackground' | 'getCanvasSize' | 'resolveBackground'>;
    store: Pick<ChartSeriesStore, 'dataLength' | 'datasets' | 'values' | 'timestamps' | 'effectiveLength' | 'ensureRenderCapacity' | 'isOhlcType' | 'renderableOhlc' | 'renderableValues'>;
    viewport: Pick<ChartViewport, 'getChartDimensions' | 'getPixelsPerBar' | 'getSlotMetrics' | 'getMaxOffsetForMetrics'>;
    formatting: Pick<ChartFormatting, 'getVisibleTimeSpan' | 'getVisibleTimeWindow' | 'valueToPixel' | 'formatValue' | 'formatTimestamp' | 'formatAxisTimestamp' | 'formatDetailedTimestamp'>;
    theme: Pick<ChartTheme, 'getStyles' | 'applyAlpha' | 'resolveDynamicPrimaryColor'>;
    redraw: Pick<ChartRedrawQueue, 'visiblePoints' | 'axis' | 'legend' | 'request'>;
    loading: Pick<ChartLoadingIndicator, 'active' | 'scheduleRedraw'>;
}

const createChartRenderingScene = ({ state, surface, store, viewport, formatting, theme, redraw, loading }: ChartRenderingOwners): ChartRenderingScene => ({
    state: {
        element: surface.element,
        get options() {
            return state.configuration.options;
        },
        get chartOptions() {
            return state.configuration.options;
        },
        get dataLength() {
            return store.dataLength;
        },
        get datasets() {
            return store.datasets;
        },
        get values() {
            return store.values;
        },
        get timestamps() {
            return store.timestamps;
        },
        get scale() {
            return state.viewport.scale;
        },
        get visibleRange() {
            return state.viewport.visibleRange;
        },
        set visibleRange(value) {
            state.viewport.visibleRange = value;
        },
        get visibleRangeStats() {
            return state.viewport.visibleRangeStats;
        },
        set visibleRangeStats(value) {
            state.viewport.visibleRangeStats = value;
        },
        get pan() {
            return state.viewport.pan;
        },
        get visiblePointsCache() {
            return redraw.visiblePoints;
        },
        set visiblePointsCache(value) {
            redraw.visiblePoints = value;
        },
        get axisCache() {
            return redraw.axis;
        },
        set axisCache(value) {
            redraw.axis = value;
        },
        get legendData() {
            return redraw.legend;
        },
        set legendData(value) {
            redraw.legend = value;
        },
        get padding() {
            return state.configuration.padding;
        },
        get crosshair() {
            return state.interaction.crosshair;
        }
    },
    surface: {
        get contexts() {
            return surface.contexts;
        },
        get offscreenCanvas() {
            return surface.offscreenCanvas;
        },
        get offscreenContext() {
            return surface.offscreenContext;
        },
        get canvasBaseBackground() {
            return surface.canvasBaseBackground;
        },
        get isHistoricalDataLoading() {
            return loading.active;
        },
        scheduleLoadingRedraw: () => loading.scheduleRedraw()
    },
    geometry: {
        getChartDimensions: () => viewport.getChartDimensions(),
        getCanvasSize: () => surface.getCanvasSize(),
        getThemeStyles: () => theme.getStyles(),
        applyAlphaToColor: (color, alpha) => theme.applyAlpha(color, alpha),
        getPixelsPerBar: () => viewport.getPixelsPerBar(),
        getEffectiveDataLength: () => store.effectiveLength(),
        getSlotMetrics: () => viewport.getSlotMetrics(),
        getMaxOffsetForMetrics: (metrics) => viewport.getMaxOffsetForMetrics(metrics),
        getVisibleTimeSpan: () => formatting.getVisibleTimeSpan(),
        getVisibleTimeWindow: () => formatting.getVisibleTimeWindow()
    },
    format: {
        valueToPixel: (value, height, top) => formatting.valueToPixel(value, height, top),
        formatValue: (value) => formatting.formatValue(value),
        formatTimestamp: (timestamp, mode) => formatting.formatTimestamp(timestamp, mode),
        formatAxisTimestamp: (timestamp, span) => formatting.formatAxisTimestamp(timestamp, span),
        formatDetailedTimestamp: (timestamp, options) => formatting.formatDetailedTimestamp(timestamp, options)
    },
    buffers: {
        ensureRenderBufferCapacity: (minimum) => {
            const result = store.ensureRenderCapacity(minimum);
            if (result.resized) redraw.visiblePoints = null;
            return result.buffers;
        },
        requestRedraw: (request) => redraw.request(request),
        resolveDynamicPrimaryColor: () => theme.resolveDynamicPrimaryColor(),
        resolveCanvasBaseBackground: () => surface.resolveBackground(),
        isOhlcRenderingType: (type) => store.isOhlcType(type),
        getRenderableOhlcBuffers: () => store.renderableOhlc(),
        getValueBufferForRendering: () => store.renderableValues()
    }
});

export { createChartRenderingScene };
export type { ChartRenderingOwners };
