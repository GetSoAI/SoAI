/* SoAI - Chart viewport resize coordination [frontend/assets/ts/features/charts/session/ChartViewportResize.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

interface ChartViewportResizeDependencies {
    surface: { subscribeResize(listener: () => void): () => void };
    viewport: { syncToSeries(): void };
}

class ChartViewportResize {
    readonly #surface: ChartViewportResizeDependencies['surface'];
    readonly #viewport: ChartViewportResizeDependencies['viewport'];
    #unsubscribe: (() => void) | null = null;

    constructor({ surface, viewport }: ChartViewportResizeDependencies) {
        this.#surface = surface;
        this.#viewport = viewport;
    }

    initialize(signal: AbortSignal): void {
        signal.throwIfAborted();
        if (this.#unsubscribe) return;
        this.#unsubscribe = this.#surface.subscribeResize(() => this.#viewport.syncToSeries());
    }

    destroy(): void {
        this.#unsubscribe?.();
        this.#unsubscribe = null;
    }
}

export { ChartViewportResize };
export type { ChartViewportResizeDependencies };
