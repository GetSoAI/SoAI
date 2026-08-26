/* SoAI - Automation calendar bounded touch momentum ownership [frontend/assets/ts/pages/automation/controllers/pager/AutomationCalendarMomentumController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { clampNumber } from '@core/primitives/clampNumber.ts';

interface AutomationCalendarMomentumControllerDependencies {
    setTimeout: (callback: () => void, delay: number) => number | null;
    clearTimer: (timerId: number | null | undefined) => void;
}

const MOMENTUM_FRAME_MS = 16;
const MOMENTUM_MAX_FRAME_MS = 40;
const MOMENTUM_DECELERATION_PX_MS_SQUARED = 0.0032;
const MOMENTUM_MIN_VELOCITY_PX_MS = 0.025;

class AutomationCalendarMomentumController {
    readonly #dependencies: AutomationCalendarMomentumControllerDependencies;
    #element: HTMLElement | null = null;
    #timerId: number | null = null;
    #velocityPxMs = 0;
    #lastFrameAtMs = 0;

    constructor(dependencies: AutomationCalendarMomentumControllerDependencies) {
        this.#dependencies = dependencies;
    }

    start(element: HTMLElement, velocityPxMs: number): void {
        this.cancel();
        if (!Number.isFinite(velocityPxMs) || Math.abs(velocityPxMs) < MOMENTUM_MIN_VELOCITY_PX_MS) {
            return;
        }
        this.#element = element;
        this.#velocityPxMs = velocityPxMs;
        this.#lastFrameAtMs = performance.now();
        this.#scheduleFrame();
    }

    cancel(): void {
        this.#dependencies.clearTimer(this.#timerId);
        this.#timerId = null;
        this.#element = null;
        this.#velocityPxMs = 0;
        this.#lastFrameAtMs = 0;
    }

    #scheduleFrame(): void {
        this.#timerId = this.#dependencies.setTimeout(() => this.#advance(), MOMENTUM_FRAME_MS);
        if (this.#timerId === null) {
            this.cancel();
        }
    }

    #advance(): void {
        this.#timerId = null;
        const element = this.#element;
        if (!element) {
            return;
        }
        const now = performance.now();
        const elapsedMs = clampNumber(now - this.#lastFrameAtMs, 1, MOMENTUM_MAX_FRAME_MS);
        this.#lastFrameAtMs = now;
        const maximumScrollTop = Math.max(0, element.scrollHeight - element.clientHeight);
        const previousScrollTop = element.scrollTop;
        const nextScrollTop = clampNumber(previousScrollTop + this.#velocityPxMs * elapsedMs, 0, maximumScrollTop);
        element.scrollTop = nextScrollTop;
        if (Math.abs(element.scrollTop - previousScrollTop) < 0.5) {
            this.cancel();
            return;
        }
        const speed = Math.max(0, Math.abs(this.#velocityPxMs) - MOMENTUM_DECELERATION_PX_MS_SQUARED * elapsedMs);
        if (speed < MOMENTUM_MIN_VELOCITY_PX_MS) {
            this.cancel();
            return;
        }
        this.#velocityPxMs = Math.sign(this.#velocityPxMs) * speed;
        this.#scheduleFrame();
    }
}

export { AutomationCalendarMomentumController };
