/* SoAI - Chart rendering capability graph composition [frontend/assets/ts/features/charts/session/createChartRenderingScene.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ChartRenderingScene } from '@features/charts/rendering/chartRenderingHost.ts';
import type { ChartFormatting } from '@features/charts/session/ChartFormatting.ts';
import type { ChartHistoryPreview } from '@features/charts/session/ChartHistoryPreview.ts';
import type { ChartSeriesMorph } from '@features/charts/session/ChartSeriesMorph.ts';
import type { ChartRedrawQueue } from '@features/charts/session/ChartRedrawQueue.ts';
import type { ChartSeriesStore } from '@features/charts/session/ChartSeriesStore.ts';
import type { ChartSurface } from '@features/charts/session/ChartSurface.ts';
import type { ChartTheme } from '@features/charts/session/ChartTheme.ts';
import type { ChartViewport } from '@features/charts/session/ChartViewport.ts';
import type { ChartState } from '@features/charts/session/chartState.ts';

interface ChartRenderingOwners {
    state: ChartState;
    surface: Pick<ChartSurface, 'element' | 'contexts' | 'offscreenCanvas' | 'offscreenContext' | 'canvasBaseBackground' | 'getCanvasSize' | 'resolveBackground'>;
    store: Pick<ChartSeriesStore, 'dataLength' | 'datasets' | 'values' | 'timestamps' | 'ensureRenderCapacity' | 'isOhlcType' | 'renderableOhlc'>;
    viewport: Pick<ChartViewport, 'getChartDimensions' | 'getRenderGeometry'>;
    formatting: Pick<ChartFormatting, 'getVisibleTimeSpan' | 'valueToPixel' | 'formatValue' | 'formatTimestamp' | 'formatAxisTimestamp' | 'formatDetailedTimestamp'>;
    theme: Pick<ChartTheme, 'getStyles' | 'applyAlpha' | 'resolveDynamicPrimaryColor'>;
    redraw: Pick<ChartRedrawQueue, 'visiblePoints' | 'axis' | 'legend' | 'request'>;
    preview: Pick<ChartHistoryPreview, 'frame'>;
    morph: Pick<ChartSeriesMorph, 'values'>;
}

const createChartRenderingScene = ({ state, surface, store, viewport, formatting, theme, redraw, preview, morph }: ChartRenderingOwners): ChartRenderingScene => ({
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
        }
    },
    geometry: {
        getChartDimensions: () => viewport.getChartDimensions(),
        getCanvasSize: () => surface.getCanvasSize(),
        getThemeStyles: () => theme.getStyles(),
        applyAlphaToColor: (color, alpha) => theme.applyAlpha(color, alpha),
        getRenderGeometry: (dims) => viewport.getRenderGeometry(dims),
        getVisibleTimeSpan: () => formatting.getVisibleTimeSpan()
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
        getValueBufferForRendering: () => morph.values()
    },
    preview: {
        frame: (now) => preview.frame(now)
    }
});

export { createChartRenderingScene };
export type { ChartRenderingOwners };
