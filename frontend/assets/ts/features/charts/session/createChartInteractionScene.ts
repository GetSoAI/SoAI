/* SoAI - Chart interaction capability graph composition [frontend/assets/ts/features/charts/session/createChartInteractionScene.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getXForVisibleIndex, getRenderGeometry } from '@features/charts/layout/geometry.ts';
import { getValueViewport } from '@features/charts/rendering/axes.ts';
import type { ChartRenderingScene } from '@features/charts/rendering/chartRenderingHost.ts';
import type { ChartDimensions } from '@features/charts/rendering/renderingModels.ts';
import type { ChartInteractionScene } from '@features/charts/interaction/chartInteractionScene.ts';
import type { ChartEvents } from '@features/charts/session/ChartEvents.ts';
import type { ChartFormatting } from '@features/charts/session/ChartFormatting.ts';
import type { ChartRedrawQueue } from '@features/charts/session/ChartRedrawQueue.ts';
import type { ChartRenderer } from '@features/charts/session/ChartRenderer.ts';
import type { ChartSeriesStore } from '@features/charts/session/ChartSeriesStore.ts';
import type { ChartSurface } from '@features/charts/session/ChartSurface.ts';
import type { ChartViewport } from '@features/charts/session/ChartViewport.ts';
import type { ChartState } from '@features/charts/session/chartState.ts';

interface ChartInteractionOwners {
    state: ChartState;
    surface: Pick<ChartSurface, 'element' | 'layers' | 'resize'>;
    store: Pick<ChartSeriesStore, 'dataLength' | 'datasets' | 'timestamps' | 'ohlcScratch' | 'findFirstTimestamp' | 'findLastTimestamp' | 'closeValue' | 'ohlcAt' | 'renderableOhlc' | 'hasOhlc' | 'isOhlcType' | 'interpolate'>;
    viewport: Pick<ChartViewport, 'getChartDimensions' | 'getPixelsPerBar' | 'getSlotMetrics' | 'getSlotMetricsForLevel' | 'getMaxOffsetForMetrics' | 'clampPanOffset' | 'enforceScaleBounds' | 'panVertical' | 'markManual' | 'setAutoScale' | 'resetZoom' | 'alignToLatest'>;
    formatting: Pick<ChartFormatting, 'valueToPixel'>;
    redraw: Pick<ChartRedrawQueue, 'request'>;
    renderer: Pick<ChartRenderer, 'schedule'>;
    events: Pick<ChartEvents, 'emit'>;
    renderingScene: Pick<ChartRenderingScene, 'state' | 'geometry'>;
}

const createChartInteractionScene = ({ state, surface, store, viewport, formatting, redraw, renderer, events, renderingScene }: ChartInteractionOwners): ChartInteractionScene => ({
    configuration: { options: state.configuration.options },
    interaction: {
        get pointer() {
            return state.interaction.pointer;
        },
        get crosshair() {
            return state.interaction.crosshair;
        },
        set crosshair(value) {
            state.interaction.crosshair = value;
        },
        get wheelPayload() {
            return state.interaction.wheelPayload;
        },
        set wheelPayload(value) {
            state.interaction.wheelPayload = value;
        },
        get wheelPending() {
            return state.interaction.wheelPending;
        },
        set wheelPending(value) {
            state.interaction.wheelPending = value;
        },
        get yAxisDrag() {
            return state.viewport.yAxisDrag;
        },
        set yAxisDrag(value) {
            state.viewport.yAxisDrag = value;
        },
        get xAxisDrag() {
            return state.viewport.xAxisDrag;
        },
        set xAxisDrag(value) {
            state.viewport.xAxisDrag = value;
        }
    },
    viewportState: state.viewport,
    surface: {
        element: surface.element,
        get canvasLayers() {
            return surface.layers;
        },
        resize: () => {
            surface.resize();
        }
    },
    viewport: {
        getChartDimensions: () => viewport.getChartDimensions(),
        getPixelsPerBar: () => viewport.getPixelsPerBar(),
        getSlotMetrics: () => viewport.getSlotMetrics(),
        getSlotMetricsForLevel: (level) => viewport.getSlotMetricsForLevel(level),
        getMaxOffsetForMetrics: (metrics) => viewport.getMaxOffsetForMetrics(metrics),
        clampPanOffset: () => viewport.clampPanOffset(),
        enforceScaleBounds: () => viewport.enforceScaleBounds(),
        panVertical: (delta) => viewport.panVertical(delta),
        markManual: (source) => viewport.markManual(source),
        setAutoScale: (enabled) => viewport.setAutoScale(Boolean(enabled)),
        resetZoom: (options) => viewport.resetZoom(options),
        alignToLatest: () => viewport.alignToLatest()
    },
    data: {
        get dataLength() {
            return store.dataLength;
        },
        get datasets() {
            return store.datasets;
        },
        get timestamps() {
            return store.timestamps;
        },
        get ohlcScratch() {
            return store.ohlcScratch;
        },
        findFirstTimestamp: (timestamp) => store.findFirstTimestamp(timestamp),
        findLastTimestamp: (timestamp) => store.findLastTimestamp(timestamp),
        closeValue: (index) => store.closeValue(index),
        ohlcAt: (index, target) => store.ohlcAt(index, target),
        renderableOhlc: () => store.renderableOhlc(),
        hasOhlc: () => store.hasOhlc(),
        isOhlcType: (type) => store.isOhlcType(type),
        interpolate: (rawIndex, start, end) => store.interpolate(rawIndex, start, end)
    },
    geometry: {
        renderGeometry: (dimensions) => getRenderGeometry(renderingScene.state, renderingScene.geometry, dimensions),
        valueViewport: () => getValueViewport(renderingScene),
        xForVisibleIndex: (index) => resolveVisibleX(renderingScene, index)
    },
    presentation: { valueToPixel: (value, height, top) => formatting.valueToPixel(value, height, top) },
    effects: { requestRedraw: (request) => redraw.request(request), scheduleFrame: () => renderer.schedule(), emit: (event, detail) => events.emit(event, detail) }
});

const resolveVisibleX = (scene: Pick<ChartRenderingScene, 'state' | 'geometry'>, index: number): number => {
    const dimensions: ChartDimensions = scene.geometry.getChartDimensions();
    const geometry = getRenderGeometry(scene.state, scene.geometry, dimensions);
    const displayCount = Number(scene.state.visibleRange.displayCount) || 0;
    const spacing = geometry.spacing;
    const origin = geometry.baseLeft - spacing * scene.state.visibleRange.offsetFraction;
    return getXForVisibleIndex(scene.state, index, displayCount, origin, spacing, geometry, dimensions);
};

export { createChartInteractionScene };
export type { ChartInteractionOwners };
