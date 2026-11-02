/* SoAI - Bounded live log entrance and tail-follow motion [frontend/assets/ts/features/logging/logStreamMotion.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { parseMaxCssDurationMs } from '@core/animations/parseMaxCssDurationMs.ts';
import { isReducedAnimationScope, scaleAnimationDurationMs } from '@core/animations/speed.ts';
import { getComputedStyleStrict, getPerformance } from '@core/environment/public.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { measureLayoutRectangles, measureViewportBox } from '@core/layout/elementGeometry.ts';

const LOG_MOTION_WINDOW_MS = 1000;
const LOG_MOTION_WINDOW_LIMIT = 6;
const LOG_MOTION_BATCH_LIMIT = 3;

class LogStreamMotion {
    #pendingEntries = 0;
    #suppressed = false;
    #windowStartedAt = -Infinity;
    #windowEntries = 0;
    #resumeAfter = -Infinity;
    readonly #animations: Animation[] = [];
    #animationFailed = false;

    recordEntry(): void {
        this.#pendingEntries += 1;
    }

    suppress(): void {
        this.#suppressed = true;
        this.#pendingEntries = 0;
        this.#cancel();
    }

    prepare(output: Element, following: boolean): (() => void) | null {
        const count = this.#pendingEntries;
        const suppressed = this.#suppressed;
        this.#pendingEntries = 0;
        this.#suppressed = false;
        const now = getPerformance().now();
        if (now - this.#windowStartedAt >= LOG_MOTION_WINDOW_MS) {
            this.#windowStartedAt = now;
            this.#windowEntries = 0;
        }
        this.#windowEntries += count;
        if (count > LOG_MOTION_BATCH_LIMIT || this.#windowEntries > LOG_MOTION_WINDOW_LIMIT || (count > 0 && now < this.#resumeAfter)) this.#resumeAfter = now + LOG_MOTION_WINDOW_MS;
        if (count === 0 || suppressed || !following || now < this.#resumeAfter || this.#animationFailed || !(output instanceof HTMLElement) || !output.isConnected || output.ownerDocument.visibilityState === 'hidden' || isReducedAnimationScope(output)) {
            this.#cancel();
            return null;
        }
        const style = getComputedStyleStrict(output);
        const duration = scaleAnimationDurationMs(parseMaxCssDurationMs(style.getPropertyValue('--motion-log-duration')), output);
        if (duration === 0 || typeof output.animate !== 'function' || measureLayoutRectangles(output).length === 0) {
            this.#cancel();
            return null;
        }
        if (!output.parentElement?.classList.contains('log-stream-viewport')) {
            const viewport = output.ownerDocument.createElement('div');
            viewport.className = 'log-stream-viewport';
            output.before(viewport);
            viewport.append(output);
        }
        const anchor = output.lastElementChild;
        const previousTop = anchor === null ? null : measureViewportBox(anchor).top;
        this.#cancel();
        const offset = style.getPropertyValue('--motion-log-entry-offset').trim();
        const timing: KeyframeAnimationOptions = { duration, easing: style.getPropertyValue('--motion-log-ease').trim() };
        return (): void => {
            if (!output.isConnected) return;
            try {
                let delta = 0;
                if (previousTop !== null && anchor instanceof HTMLElement && anchor.parentElement === output) {
                    const box = measureViewportBox(anchor);
                    if (box.height > 0) delta = ((previousTop - box.top) * anchor.offsetHeight) / box.height;
                }
                if (delta > 0.5) {
                    this.#animations.push(output.animate({ translate: [`0px ${delta}px`, '0px 0px'] }, timing));
                    return;
                }
                let entry = anchor?.parentElement === output ? anchor.nextElementSibling : output.firstElementChild;
                for (let index = 0; entry instanceof HTMLElement && index < count; index += 1) {
                    this.#animations.push(entry.animate({ translate: [`0px ${offset}`, '0px 0px'] }, timing));
                    entry = entry.nextElementSibling;
                }
            } catch (error) {
                this.#animationFailed = true;
                this.#cancel();
                errorHandler.warn('LogStreamMotion', 'Live log animation is unavailable', ensureError(error));
            }
        };
    }

    reset(): void {
        this.#pendingEntries = 0;
        this.#suppressed = false;
        this.#windowStartedAt = -Infinity;
        this.#windowEntries = 0;
        this.#resumeAfter = -Infinity;
        this.#cancel();
    }

    #cancel(): void {
        for (const animation of this.#animations) animation.cancel();
        this.#animations.length = 0;
    }
}

export { LogStreamMotion };
