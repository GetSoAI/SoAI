/* SoAI - Chart frame painting ownership [frontend/assets/ts/features/charts/session/ChartFramePainter.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ChartRenderingScene } from '@features/charts/rendering/chartRenderingHost.ts';
import { renderDataLayer, renderInteractionLayer, renderStaticLayer } from '@features/charts/rendering/layers.ts';
import type { ChartRedrawQueue } from '@features/charts/session/ChartRedrawQueue.ts';

interface ChartRenderModelUpdater {
    update(): void;
}

interface ChartPaintSurface {
    ensureSize(): boolean;
}

interface ChartFramePainterDependencies {
    scene: ChartRenderingScene;
    redraw: ChartRedrawQueue;
    surface: ChartPaintSurface;
    model: ChartRenderModelUpdater;
}

class ChartFramePainter {
    readonly #scene: ChartRenderingScene;
    readonly #redraw: ChartRedrawQueue;
    readonly #surface: ChartPaintSurface;
    readonly #model: ChartRenderModelUpdater;

    constructor({ scene, redraw, surface, model }: ChartFramePainterDependencies) {
        this.#scene = scene;
        this.#redraw = redraw;
        this.#surface = surface;
        this.#model = model;
    }

    paint(): void {
        if (this.#surface.ensureSize()) this.#redraw.request({ static: true, data: true, interaction: true });
        if (this.#redraw.isPending('data') && !this.#redraw.isPending('static')) this.#redraw.request({ static: true });
        if (this.#redraw.isPending('static') || this.#redraw.isPending('data')) this.#model.update();
        if (this.#redraw.isPending('static')) {
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
    }
}

export { ChartFramePainter };
export type { ChartFramePainterDependencies, ChartPaintSurface, ChartRenderModelUpdater };
