/* SoAI - Charts feature history chart presentation [frontend/assets/ts/features/charts/presentation/historyChartPresentation.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { scaleAnimationDurationMs } from '@core/animations/speed.ts';
import { dom } from '@core/dom/dom.ts';
import { getRequestAnimationFrame } from '@core/environment/public.ts';

const CHART_LOADING_CLASS = 'chart-container--loading';
const CHART_READY_CLASS = 'chart-container--ready';
const CHART_TRANSITION_LAYER_CLASS = 'chart-transition-layer';
const CHART_TRANSITION_DURATION_MS = 240;

type ChartLayerSnapshotSource = {
    layers: HTMLCanvasElement[];
    width: number;
    height: number;
};

class HistoryChartPresentation {
    readonly #host: HTMLElement;
    #loadSequence = 0;
    #readySequence = 0;

    constructor(host: HTMLElement) {
        this.#host = host;
    }

    reset(): void {
        this.#loadSequence += 1;
        this.#readySequence = 0;
        this.#clearTransitionLayers();
        this.#setLoading(true);
    }

    begin(): number {
        this.#loadSequence += 1;
        this.#readySequence = 0;
        const hasVisibleChart = this.#host.classList.contains(CHART_READY_CLASS);
        this.#setLoading(true);
        if (hasVisibleChart && !this.#activeTransitionLayer()) {
            const outgoing = this.#createOutgoingLayer();
            if (outgoing) {
                this.#startOutgoingFade(outgoing);
            }
        }
        return this.#loadSequence;
    }

    current(): number {
        return this.#loadSequence;
    }

    complete(sequence: number): void {
        if (this.#loadSequence !== sequence) {
            return;
        }
        this.#readySequence = sequence;
        this.#revealIfReady(sequence);
    }

    destroy(): void {
        this.#loadSequence += 1;
        this.#readySequence = 0;
        this.#clearTransitionLayers();
        this.#setLoading(true);
    }

    #setLoading(loading: boolean): void {
        this.#host.classList.toggle(CHART_LOADING_CLASS, loading);
        this.#host.classList.toggle(CHART_READY_CLASS, !loading);
    }

    #clearTransitionLayers(): void {
        dom.resolveAll(`.${CHART_TRANSITION_LAYER_CLASS}`, this.#host).forEach((layer) => layer.remove());
    }

    #resolveSnapshotSource(): ChartLayerSnapshotSource | null {
        const layers = dom.resolveAll('.chart-layer', this.#host).filter((element): element is HTMLCanvasElement => element instanceof HTMLCanvasElement);
        if (!layers.length) {
            return null;
        }
        const first = layers[0];
        if (!first || first.width <= 0 || first.height <= 0) {
            return null;
        }
        const mismatchedLayer = layers.find((layer) => layer.width !== first.width || layer.height !== first.height);
        if (mismatchedLayer) {
            return null;
        }
        return { layers, width: first.width, height: first.height };
    }

    #activeTransitionLayer(): Element | null {
        return dom.resolve(`.${CHART_TRANSITION_LAYER_CLASS}`, this.#host);
    }

    #createOutgoingLayer(): HTMLCanvasElement | null {
        const source = this.#resolveSnapshotSource();
        if (!source) {
            return null;
        }
        const overlay = this.#host.ownerDocument.createElement('canvas');
        overlay.className = CHART_TRANSITION_LAYER_CLASS;
        overlay.width = source.width;
        overlay.height = source.height;
        const context = overlay.getContext('2d');
        if (!context) {
            throw new Error('History chart transition requires a 2D canvas context');
        }
        source.layers.forEach((layer) => context.drawImage(layer, 0, 0));
        this.#host.appendChild(overlay);
        return overlay;
    }

    #startOutgoingFade(overlay: HTMLCanvasElement): void {
        const animation = overlay.animate([{ opacity: 1 }, { opacity: 0 }], {
            duration: scaleAnimationDurationMs(CHART_TRANSITION_DURATION_MS, overlay),
            easing: 'ease',
            fill: 'forwards'
        });
        void animation.finished.then(
            () => this.#finishOutgoingLayer(overlay),
            () => this.#finishOutgoingLayer(overlay)
        );
    }

    #finishOutgoingLayer(overlay: HTMLCanvasElement): void {
        if (!overlay.isConnected) {
            return;
        }
        overlay.remove();
        this.#revealIfReady(this.#loadSequence);
    }

    #revealIfReady(sequence: number): void {
        if (this.#loadSequence !== sequence || this.#readySequence !== sequence) {
            return;
        }
        if (this.#activeTransitionLayer()) {
            return;
        }
        const scheduleAnimationFrame = getRequestAnimationFrame();
        scheduleAnimationFrame(() => {
            if (this.#loadSequence === sequence && this.#readySequence === sequence) {
                this.#setLoading(false);
            }
        });
    }
}

const createHistoryChartPresentation = (host: HTMLElement): HistoryChartPresentation => new HistoryChartPresentation(host);

export { createHistoryChartPresentation, HistoryChartPresentation };
