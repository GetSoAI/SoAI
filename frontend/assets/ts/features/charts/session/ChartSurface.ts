/* SoAI - Chart canvas surface ownership [frontend/assets/ts/features/charts/session/ChartSurface.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { getCancelAnimationFrame } from '@core/environment/public.ts';
import { resolveCanvasRenderPixelRatio } from '@core/layout/canvasGeometry.ts';
import { EMPTY_UI_HTML } from '@core/security/uiHtml.ts';
import { resolveCanvasBaseBackground } from '@features/charts/component/state/effects.ts';
import { createChartLayerPool } from '@features/charts/Runtime.ts';
import type { ChartConfigurationState, ChartSurfaceState } from '@features/charts/session/chartState.ts';
import { resizeChartSurface } from '@features/charts/session/chartSurfaceResize.ts';
type ChartSurfaceResizeListener = () => void;

class ChartSurface {
    readonly #state: ChartSurfaceState;
    readonly #configuration: ChartConfigurationState;
    readonly #resizeListeners = new Set<ChartSurfaceResizeListener>();

    constructor(state: ChartSurfaceState, configuration: ChartConfigurationState) {
        this.#state = state;
        this.#configuration = configuration;
    }

    get element(): HTMLElement {
        return this.#state.element;
    }

    get dimensions(): Readonly<ChartSurfaceState['canvasDimensions']> {
        return this.#state.canvasDimensions;
    }

    get layers(): Readonly<ChartSurfaceState['canvasLayers']> {
        return this.#state.canvasLayers;
    }

    get contexts(): Readonly<ChartSurfaceState['contexts']> {
        return this.#state.contexts;
    }

    get offscreenCanvas(): OffscreenCanvas | null {
        return this.#state.offscreenCanvas;
    }

    get offscreenContext(): OffscreenCanvasRenderingContext2D | null {
        return this.#state.offscreenContext;
    }

    get canvasBaseBackground(): string | null {
        return this.#state.canvasBaseBackground;
    }

    getCanvasSize(): { width: number; height: number } {
        const { width, height, dpr } = this.#state.canvasDimensions;
        return dpr > 0 ? { width: Math.max(0, width / dpr), height: Math.max(0, height / dpr) } : { width: 0, height: 0 };
    }

    subscribeResize(listener: ChartSurfaceResizeListener): () => void {
        this.#resizeListeners.add(listener);
        return () => this.#resizeListeners.delete(listener);
    }

    initialize(signal: AbortSignal): void {
        signal.throwIfAborted();
        try {
            this.#prepareContainer();
            this.#acquireLayers();
            this.#observeSize();
            this.resize();
            this.#createOffscreenSurface();
            signal.throwIfAborted();
        } catch (error) {
            this.destroy();
            throw error;
        }
    }

    resize(): boolean {
        return resizeChartSurface(this.#state, { afterResize: () => this.#notifyResize() }, () => this.resize());
    }

    ensureSize(): boolean {
        const layer = this.#state.canvasLayers.static;
        if (!layer) return false;
        const { width, height } = this.getCanvasSize();
        if (width <= 0 || height <= 0) return false;
        const renderPixelRatio = resolveCanvasRenderPixelRatio(layer);
        const expectedWidth = Math.round(width * renderPixelRatio);
        const expectedHeight = Math.round(height * renderPixelRatio);
        const interactionWidth = this.#state.interactionCanvasDimensions.width;
        const interactionHeight = this.#state.interactionCanvasDimensions.height;
        const dimensions = this.#state.canvasDimensions;
        const fullSurfaceMismatch = [layer, this.#state.canvasLayers.data, this.#state.offscreenCanvas].some((canvas) => canvas !== null && (canvas.width !== expectedWidth || canvas.height !== expectedHeight));
        const interaction = this.#state.canvasLayers.interaction;
        const interactionMismatch = interaction !== null && (interaction.width !== interactionWidth || interaction.height !== interactionHeight);
        const requiresResize = dimensions.width !== expectedWidth || dimensions.height !== expectedHeight || dimensions.dpr !== renderPixelRatio || fullSurfaceMismatch || interactionMismatch;
        if (requiresResize) this.resize();
        return requiresResize;
    }

    syncInteractionBounds(): void {
        const padding = this.#configuration.padding;
        dom.setStyle(this.#state.element, '--chart-interaction-top', `${Math.max(0, padding.top)}px`);
        dom.setStyle(this.#state.element, '--chart-interaction-right', `${Math.max(0, padding.right)}px`);
        dom.setStyle(this.#state.element, '--chart-interaction-bottom', `${Math.max(0, padding.bottom + this.#configuration.options.bottomAxisPadding)}px`);
        dom.setStyle(this.#state.element, '--chart-interaction-left', `${Math.max(0, padding.left)}px`);
    }

    applyMinimumHeight(): void {
        dom.setStyle(this.#state.element, 'minHeight', `${this.#configuration.options.minHeight}px`);
    }

    applyBackground(): void {
        const background = this.resolveBackground();
        for (const canvas of Object.values(this.#state.canvasLayers)) {
            if (canvas) dom.setStyle(canvas, 'backgroundColor', canvas === this.#state.canvasLayers.static ? background : 'transparent');
        }
    }

    resolveBackground(): string {
        const background = resolveCanvasBaseBackground(this.#state.element, this.#configuration.options.colors);
        this.#state.canvasBaseBackground = background;
        return background;
    }

    destroy(): void {
        if (this.#state.pendingResizeFrame !== null) getCancelAnimationFrame()(this.#state.pendingResizeFrame);
        this.#state.pendingResizeFrame = null;
        this.#state.resizeObserver?.disconnect();
        this.#state.resizeObserver = null;
        if (this.#state.chartRuntime && this.#state.runtimeLayers) this.#state.chartRuntime.releaseLayers(this.#state.runtimeLayers);
        this.#state.runtimeLayers = null;
        this.#state.chartRuntime = null;
        dom.setHTML(this.#state.element, EMPTY_UI_HTML, { escape: false });
        this.#state.offscreenCanvas = null;
        this.#state.offscreenContext = null;
        this.#state.canvasLayers = { static: null, data: null, interaction: null };
        this.#state.contexts = { static: null, data: null, interaction: null };
        this.#state.canvasDimensions = { width: 0, height: 0, dpr: 0 };
        this.#state.interactionCanvasDimensions = { width: 0, height: 0, dpr: 0 };
        this.#state.canvasBaseBackground = null;
        this.#resizeListeners.clear();
    }

    #prepareContainer(): void {
        const element = this.#state.element;
        const inlineMinimumHeight = element.style.getPropertyValue('min-height').trim();
        const computedMinimumHeight = dom.getStyleValue(element, 'minHeight').trim();
        const preservesMinimumHeight = inlineMinimumHeight !== '' || (computedMinimumHeight !== '' && computedMinimumHeight !== 'auto' && computedMinimumHeight !== '0px');
        dom.addClass(element, 'chart-container');
        if (!dom.getStyleValue(element, 'position') || dom.getStyleValue(element, 'position') === 'static') dom.setStyle(element, 'position', 'relative');
        const win = element.ownerDocument.defaultView;
        if (!win || typeof win.getComputedStyle !== 'function') throw new Error('Chart requires window.getComputedStyle');
        if (!dom.getStyleValue(element, 'display')) {
            const display = win.getComputedStyle(element).display;
            if (!display || ['inline', 'inline-block', 'contents', 'initial'].includes(display)) dom.setStyle(element, 'display', 'block');
        }
        if (!preservesMinimumHeight) dom.setStyle(element, 'minHeight', `${this.#configuration.options.minHeight}px`);
        this.syncInteractionBounds();
    }

    #acquireLayers(): void {
        const runtime = createChartLayerPool(this.#state.element.ownerDocument);
        const layers = runtime.acquireLayers(['static', 'data', 'interaction']);
        this.#state.chartRuntime = runtime;
        this.#state.runtimeLayers = layers;
        for (const layer of layers) {
            dom.appendChild(this.#state.element, layer.canvas);
            this.#state.canvasLayers[layer.name] = layer.canvas;
            this.#state.contexts[layer.name] = layer.context;
        }
        this.applyBackground();
    }

    #createOffscreenSurface(): void {
        const OffscreenCanvasConstructor = this.#state.element.ownerDocument.defaultView?.OffscreenCanvas;
        if (typeof OffscreenCanvasConstructor !== 'function') return;
        const dimensions = this.#state.canvasDimensions;
        this.#state.offscreenCanvas = new OffscreenCanvasConstructor(dimensions.width, dimensions.height);
        this.#state.offscreenContext = this.#state.offscreenCanvas.getContext('2d', { desynchronized: true, alpha: true }) || this.#state.offscreenCanvas.getContext('2d');
        this.#state.offscreenContext?.setTransform(dimensions.dpr, 0, 0, dimensions.dpr, 0, 0);
    }

    #observeSize(): void {
        const ResizeObserverConstructor = this.#state.element.ownerDocument.defaultView?.ResizeObserver;
        if (typeof ResizeObserverConstructor !== 'function') throw new Error('Chart requires ResizeObserver');
        this.#state.resizeObserver = new ResizeObserverConstructor((entries) => {
            if (entries.some((entry) => entry.target === this.#state.element)) this.resize();
        });
        this.#state.resizeObserver.observe(this.#state.element);
    }

    #notifyResize(): void {
        for (const listener of [...this.#resizeListeners]) listener();
    }
}

export { ChartSurface };
export type { ChartSurfaceResizeListener };
