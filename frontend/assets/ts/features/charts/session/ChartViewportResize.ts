/* SoAI - Chart viewport resize coordination [frontend/assets/ts/features/charts/session/ChartViewportResize.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { RedrawRequest } from '@features/charts/component/chartComponentTypes.ts';

interface ChartViewportResizeRedrawPort {
    request(request: RedrawRequest): void;
}

interface ChartViewportResizeDependencies {
    surface: { subscribeResize(listener: () => void): () => void };
    viewport: { recalculateZoomBounds(): void; clampPanOffset(): void };
    redraw: ChartViewportResizeRedrawPort;
}

class ChartViewportResize {
    readonly #surface: ChartViewportResizeDependencies['surface'];
    readonly #viewport: ChartViewportResizeDependencies['viewport'];
    readonly #redraw: ChartViewportResizeRedrawPort;
    #unsubscribe: (() => void) | null = null;

    constructor({ surface, viewport, redraw }: ChartViewportResizeDependencies) {
        this.#surface = surface;
        this.#viewport = viewport;
        this.#redraw = redraw;
    }

    initialize(signal: AbortSignal): void {
        signal.throwIfAborted();
        if (this.#unsubscribe) return;
        this.#unsubscribe = this.#surface.subscribeResize(() => {
            this.#viewport.recalculateZoomBounds();
            this.#viewport.clampPanOffset();
            this.#redraw.request({ static: true, data: true, interaction: true });
        });
    }

    destroy(): void {
        this.#unsubscribe?.();
        this.#unsubscribe = null;
    }
}

export { ChartViewportResize };
export type { ChartViewportResizeDependencies };
