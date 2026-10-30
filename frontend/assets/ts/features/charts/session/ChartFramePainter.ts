/* SoAI - Chart frame painting ownership [frontend/assets/ts/features/charts/session/ChartFramePainter.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { generateYAxisTicks } from '@features/charts/rendering/axisrendering/service.ts';
import { getValueViewport } from '@features/charts/rendering/axes.ts';
import type { ChartTheme } from '@features/charts/session/ChartTheme.ts';
import { i18n } from '@core/i18n/index.ts';
import type { ChartRenderingScene } from '@features/charts/rendering/chartRenderingHost.ts';
import { renderDataLayer, renderInteractionLayer, renderStaticLayer } from '@features/charts/rendering/layers.ts';
import type { ChartRedrawQueue } from '@features/charts/session/ChartRedrawQueue.ts';

interface ChartRenderModelUpdater {
    update(): void;
}

interface ChartPaintSurface {
    ensureSize(): boolean;
    fitYAxisLabels(labels: readonly string[], autoScale: boolean): boolean;
}

interface ChartFramePainterDependencies {
    scene: ChartRenderingScene;
    redraw: ChartRedrawQueue;
    surface: ChartPaintSurface;
    model: ChartRenderModelUpdater;
    theme: Pick<ChartTheme, 'beginFrame' | 'endFrame'>;
}

class ChartFramePainter {
    readonly #scene: ChartRenderingScene;
    readonly #redraw: ChartRedrawQueue;
    readonly #surface: ChartPaintSurface;
    readonly #model: ChartRenderModelUpdater;
    readonly #theme: ChartFramePainterDependencies['theme'];

    constructor({ scene, redraw, surface, model, theme }: ChartFramePainterDependencies) {
        this.#scene = scene;
        this.#redraw = redraw;
        this.#surface = surface;
        this.#model = model;
        this.#theme = theme;
    }

    paint(): void {
        if (this.#scene.state.element && !this.#scene.state.element.isConnected) return;
        this.#theme.beginFrame();
        try {
            if (this.#surface.ensureSize()) this.#redraw.request({ static: true, data: true, interaction: true });
            if (this.#redraw.isPending('data') && !this.#redraw.isPending('static')) this.#redraw.request({ static: true });
            if (this.#redraw.isPending('static') || this.#redraw.isPending('data')) this.#model.update();
            if (this.#redraw.isPending('static')) {
                const dimensions = this.#scene.geometry.getChartDimensions();
                const labels = generateYAxisTicks(this.#scene, dimensions, getValueViewport(this.#scene, dimensions)).map((tick) => tick.label);
                if (!this.#scene.state.scale.auto) labels.push(i18n.t('charts.manualScaleLabel'));
                if (this.#surface.fitYAxisLabels(labels, this.#scene.state.scale.auto)) {
                    this.#redraw.request({ static: true, data: true, interaction: true });
                    this.#model.update();
                }
                renderStaticLayer(this.#scene);
                this.#redraw.complete('static');
            }
            if (this.#redraw.isPending('data')) {
                renderDataLayer(this.#scene);
                this.#redraw.complete('data');
            }
            if (this.#redraw.isPending('interaction')) {
                renderInteractionLayer(this.#scene);
                this.#redraw.complete('interaction');
            }
        } finally {
            this.#theme.endFrame();
        }
    }
}

export { ChartFramePainter };
export type { ChartFramePainterDependencies, ChartPaintSurface, ChartRenderModelUpdater };
