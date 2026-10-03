/* SoAI - Chart frame scheduling ownership [frontend/assets/ts/features/charts/session/ChartRenderer.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getCancelAnimationFrame, getRequestAnimationFrame } from '@core/environment/public.ts';
import { monotonicMs } from '@core/time/clock.ts';
import type { RedrawRequest } from '@features/charts/component/chartComponentTypes.ts';
import type { ChartRedrawQueue } from '@features/charts/session/ChartRedrawQueue.ts';

interface ChartRendererDependencies {
    redraw: ChartRedrawQueue;
    viewport: ChartAnimationPort;
    painter: { paint(): void };
    preview: { isAnimating(now: number): boolean };
    morph: { advance(now: number): boolean };
}

interface ChartAnimationPort {
    readonly status: Readonly<{ isAnimating: boolean }>;
    advanceAnimation(now: number): boolean;
}

const ANIMATION_REDRAW: RedrawRequest = { static: true, data: true, interaction: true };
const PREVIEW_REDRAW: RedrawRequest = { data: true };

class ChartRenderer {
    readonly #redraw: ChartRedrawQueue;
    readonly #viewport: ChartAnimationPort;
    readonly #painter: ChartRendererDependencies['painter'];
    readonly #preview: ChartRendererDependencies['preview'];
    readonly #morph: ChartRendererDependencies['morph'];
    #animationFrame: number | null = null;
    #animationCallback: (() => void) | null = null;
    #themeFrame: number | null = null;
    #unsubscribeRedraw: (() => void) | null = null;
    #active = false;

    constructor({ redraw, viewport, painter, preview, morph }: ChartRendererDependencies) {
        this.#redraw = redraw;
        this.#viewport = viewport;
        this.#painter = painter;
        this.#preview = preview;
        this.#morph = morph;
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
    }

    #runFrame(): void {
        this.#animationFrame = null;
        if (!this.#active) return;
        const now = monotonicMs();
        this.#viewport.advanceAnimation(now);
        if (this.#morph.advance(now)) this.#redraw.request(PREVIEW_REDRAW);
        if (this.#redraw.hasPending) this.#painter.paint();
        if (this.#viewport.status.isAnimating) this.#redraw.request(ANIMATION_REDRAW);
        else if (this.#preview.isAnimating(now)) this.#redraw.request(PREVIEW_REDRAW);
    }
}

export { ChartRenderer };
export type { ChartAnimationPort, ChartRendererDependencies };
