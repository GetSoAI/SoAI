/* SoAI - Chart owner graph composition root [frontend/assets/ts/features/charts/session/createChartSession.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { resolveContainer } from '@core/dom/dom.ts';
import { isString } from '@core/typeGuards.ts';
import type { ChartOptions } from '@features/charts/chartTypes.ts';
import { ChartDataCommands } from '@features/charts/session/ChartDataCommands.ts';
import { ChartEvents } from '@features/charts/session/ChartEvents.ts';
import { ChartFormatting } from '@features/charts/session/ChartFormatting.ts';
import { ChartFramePainter } from '@features/charts/session/ChartFramePainter.ts';
import { ChartInteraction } from '@features/charts/session/ChartInteraction.ts';
import { ChartLoadingIndicator } from '@features/charts/session/ChartLoadingIndicator.ts';
import { ChartRedrawQueue } from '@features/charts/session/ChartRedrawQueue.ts';
import { ChartRenderer } from '@features/charts/session/ChartRenderer.ts';
import { ChartRenderModelUpdater } from '@features/charts/session/ChartRenderModelUpdater.ts';
import { ChartSeriesStore } from '@features/charts/session/ChartSeriesStore.ts';
import { ChartSessionLifecycle } from '@features/charts/session/ChartSessionLifecycle.ts';
import { ChartSettings } from '@features/charts/session/ChartSettings.ts';
import { ChartSurface } from '@features/charts/session/ChartSurface.ts';
import { ChartTheme } from '@features/charts/session/ChartTheme.ts';
import { ChartViewport } from '@features/charts/session/ChartViewport.ts';
import { ChartViewportResize } from '@features/charts/session/ChartViewportResize.ts';
import { createChartInteractionScene } from '@features/charts/session/createChartInteractionScene.ts';
import { createChartRenderingScene } from '@features/charts/session/createChartRenderingScene.ts';
import { createChartState } from '@features/charts/session/chartState.ts';

interface ChartSession {
    settings: ChartSettings;
    data: ChartDataCommands;
    view: ChartViewport;
    lifecycle: ChartSessionLifecycle;
}

const createChartSession = (container: HTMLElement | string | null, options: Partial<ChartOptions> = {}): ChartSession => {
    const element = resolveContainer(container);
    if (!element) {
        if (isString(container)) throw new Error(`Chart container not found: ${container}`);
        throw new Error('Chart container element is required');
    }
    const state = createChartState(element, options);
    const redraw = new ChartRedrawQueue();
    const events = new ChartEvents(element);
    const surface = new ChartSurface(state.surface, state.configuration);
    const store = new ChartSeriesStore({ configuration: state.configuration, series: state.series });
    const viewport = new ChartViewport({ configuration: state.configuration, state: state.viewport, interaction: state.interaction, series: store, surface, redraw, events });
    const data = new ChartDataCommands({ store, viewportState: state.viewport, interaction: state.interaction, viewport, redraw });
    const settings = new ChartSettings({ configuration: state.configuration, series: data, viewport, redraw, surface });
    const formatting = new ChartFormatting(state.configuration, store, state.viewport, redraw);
    const theme = new ChartTheme({ configuration: state.configuration, surface, settings });
    const loading = new ChartLoadingIndicator({ state: viewport, redraw });
    const renderingScene = createChartRenderingScene({ state, surface, store, viewport, formatting, theme, redraw, loading });
    const model = new ChartRenderModelUpdater({
        configuration: state.configuration,
        viewport: state.viewport,
        interaction: state.interaction,
        series: store,
        redraw,
        calculations: {
            chartEmit: (event, detail) => viewport.chartEmit(event, detail),
            enforceScaleBounds: () => viewport.enforceScaleBounds(),
            getChartDimensions: () => viewport.getChartDimensions(),
            getEffectiveDataLength: () => store.effectiveLength(),
            getRenderableOhlcBuffers: () => store.renderableOhlc(),
            getCloseValue: (index) => store.closeValue(index),
            getOhlcForIndex: (index, target) => store.ohlcAt(index, target)
        }
    });
    const painter = new ChartFramePainter({ scene: renderingScene, redraw, surface, model });
    const renderer = new ChartRenderer({ configuration: state.configuration, redraw, viewport, painter });
    const interactionScene = createChartInteractionScene({ state, surface, store, viewport, formatting, redraw, renderer, events, renderingScene });
    const interaction = new ChartInteraction(interactionScene);
    const viewportResize = new ChartViewportResize({ surface, viewport, redraw });
    const lifecycle = new ChartSessionLifecycle({ events, redraw, surface, theme, loading, viewportResize, renderer, interaction });
    return Object.freeze({ settings, data, view: viewport, lifecycle });
};

export { createChartSession };
export type { ChartSession };
