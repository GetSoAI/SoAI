/* SoAI - Chart frame scheduling ownership [frontend/assets/ts/features/charts/session/ChartRenderer.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { requireDocument } from '@core/environment/public.ts';
import { ResourceTracker } from '@core/resourcetracker/service.ts';
import { scheduleRequiredRender, type PresentationFrameOutcome } from '@core/runtime/animationFrames.ts';
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
    readonly #resources = new ResourceTracker();
    #cancelRender: (() => void) | null = null;
    #cancelTheme: (() => void) | null = null;
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
        this.#unsubscribeRedraw = this.#redraw.subscribe(() => this.schedule());
        this.#resources.addEventListener(requireDocument(), 'visibilitychange', () => this.request(ANIMATION_REDRAW));
        this.schedule();
    }

    request(requirements: RedrawRequest = { data: true, interaction: true }): void {
        this.#redraw.request(requirements);
    }

    schedule(): void {
        if (!this.#active || this.#cancelRender !== null) return;
        this.#cancelRender = scheduleRequiredRender((outcome) => this.#runFrame(outcome));
    }

    scheduleThemeUpdate(callback: () => void): void {
        if (!this.#active || this.#cancelTheme !== null) return;
        this.#cancelTheme = scheduleRequiredRender(() => {
            this.#cancelTheme = null;
            if (this.#active) callback();
        });
    }

    async destroy(): Promise<void> {
        this.#active = false;
        this.#unsubscribeRedraw?.();
        this.#unsubscribeRedraw = null;
        this.#cancelRender?.();
        this.#cancelTheme?.();
        this.#cancelRender = null;
        this.#cancelTheme = null;
        this.#resources.cleanup();
    }

    #runFrame(outcome: PresentationFrameOutcome): void {
        this.#cancelRender = null;
        if (!this.#active) return;
        const now = monotonicMs();
        this.#viewport.advanceAnimation(now);
        if (this.#morph.advance(now)) this.#redraw.request(PREVIEW_REDRAW);
        if (this.#redraw.hasPending) this.#painter.paint();
        if (outcome === 'hidden') return;
        if (this.#viewport.status.isAnimating) this.#redraw.request(ANIMATION_REDRAW);
        else if (this.#preview.isAnimating(now)) this.#redraw.request(PREVIEW_REDRAW);
    }
}

export { ChartRenderer };
export type { ChartAnimationPort, ChartRendererDependencies };
