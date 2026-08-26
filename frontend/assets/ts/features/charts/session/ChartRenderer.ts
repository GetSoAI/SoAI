/* SoAI - Chart frame scheduling ownership [frontend/assets/ts/features/charts/session/ChartRenderer.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getCancelAnimationFrame, getRequestAnimationFrame } from '@core/environment/public.ts';
import { LifecycleResources } from '@core/lifecyclemodel/LifecycleResources.ts';
import type { RedrawRequest, PanState, ZoomState } from '@features/charts/component/chartComponentTypes.ts';
import type { ChartRedrawQueue } from '@features/charts/session/ChartRedrawQueue.ts';

interface ChartRendererDependencies {
    configuration: { readonly options: { enableInertialPanning: boolean; enableSmoothZoom: boolean } };
    redraw: ChartRedrawQueue;
    viewport: ChartAnimationPort;
    painter: { paint(): void };
}

interface ChartAnimationPort {
    readonly pan: PanState;
    readonly zoom: ZoomState;
    advanceInertialPanning(): void;
    advanceSmoothZoom(): void;
}

class ChartRenderer {
    readonly #configuration: ChartRendererDependencies['configuration'];
    readonly #redraw: ChartRedrawQueue;
    readonly #viewport: ChartAnimationPort;
    readonly #painter: ChartRendererDependencies['painter'];
    readonly #resources = new LifecycleResources();
    #animationFrame: number | null = null;
    #animationCallback: (() => void) | null = null;
    #themeFrame: number | null = null;
    #loadingRedrawTimer: number | null = null;
    #unsubscribeRedraw: (() => void) | null = null;
    #active = false;

    constructor({ configuration, redraw, viewport, painter }: ChartRendererDependencies) {
        this.#configuration = configuration;
        this.#redraw = redraw;
        this.#viewport = viewport;
        this.#painter = painter;
    }

    initialize(signal: AbortSignal): void {
        signal.throwIfAborted();
        if (this.#active) return;
        this.#active = true;
        this.#animationCallback = () => this.#runFrame();
        this.#unsubscribeRedraw = this.#redraw.subscribe(() => this.schedule());
        this.schedule();
    }

    request(requirements: RedrawRequest = { data: true, interaction: true }): void {
        this.#redraw.request(requirements);
    }

    schedule(): void {
        if (!this.#active || this.#animationFrame !== null || !this.#animationCallback) return;
        this.#animationFrame = getRequestAnimationFrame()(this.#animationCallback);
    }

    scheduleThemeUpdate(callback: () => void): void {
        if (!this.#active || this.#themeFrame !== null) return;
        this.#themeFrame = getRequestAnimationFrame()(() => {
            this.#themeFrame = null;
            if (this.#active) callback();
        });
    }

    scheduleLoadingRedraw(callback: () => void, delay: number): void {
        if (this.#loadingRedrawTimer !== null) this.#resources.clearTimer(this.#loadingRedrawTimer);
        this.#loadingRedrawTimer = this.#resources.setTimer(() => {
            this.#loadingRedrawTimer = null;
            if (this.#active) callback();
        }, delay);
    }

    async destroy(): Promise<void> {
        this.#active = false;
        this.#unsubscribeRedraw?.();
        this.#unsubscribeRedraw = null;
        const cancelAnimationFrame = getCancelAnimationFrame();
        if (this.#animationFrame !== null) cancelAnimationFrame(this.#animationFrame);
        if (this.#themeFrame !== null) cancelAnimationFrame(this.#themeFrame);
        this.#animationFrame = null;
        this.#themeFrame = null;
        this.#animationCallback = null;
        this.#loadingRedrawTimer = null;
        await this.#resources.cleanup();
    }

    #runFrame(): void {
        this.#animationFrame = null;
        if (!this.#active) return;
        let continueRendering = false;
        if (this.#configuration.options.enableInertialPanning && this.#viewport.pan.velocity !== 0) {
            this.#viewport.advanceInertialPanning();
            continueRendering = true;
        }
        if (this.#configuration.options.enableSmoothZoom && this.#viewport.zoom.isAnimating) {
            this.#viewport.advanceSmoothZoom();
            continueRendering = true;
        }
        if (this.#redraw.hasPending) {
            this.#painter.paint();
            continueRendering = true;
        }
        if (continueRendering) this.schedule();
    }
}

export { ChartRenderer };
export type { ChartAnimationPort, ChartRendererDependencies };
