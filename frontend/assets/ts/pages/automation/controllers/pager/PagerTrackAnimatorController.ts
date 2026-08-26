/* SoAI - Automation page pager track animator controller [frontend/assets/ts/pages/automation/controllers/pager/PagerTrackAnimatorController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createDeferred } from '@core/runtime/deferred.ts';

interface PagerTrackAnimatorControllerDependencies {
    resolveTrack: () => HTMLElement | null;
    requestAnimationFrame: (callback: () => void) => number;
    setTimeout: (callback: () => void, delay: number) => number | null;
    clearTimer: (timerId: number | null | undefined) => void;
}

interface ActiveTrackAnimation {
    track: HTMLElement;
    onEnd: (transitionEvent: TransitionEvent) => void;
    timerId: number | null;
    resolve: (completed: boolean) => void;
}

const ANIMATION_SAFETY_TIMEOUT_MS = 360;

const isReducedMotion = (): boolean => window.matchMedia('(prefers-reduced-motion: reduce)').matches;

const buildTransform = (targetOffsetPx: number, viewportHeight: number): string => `translate3d(0, ${-viewportHeight + targetOffsetPx}px, 0)`;

class PagerTrackAnimatorController {
    readonly #dependencies: PagerTrackAnimatorControllerDependencies;
    #activeAnimation: ActiveTrackAnimation | null = null;
    #currentOffsetPx = 0;

    constructor(dependencies: PagerTrackAnimatorControllerDependencies) {
        this.#dependencies = dependencies;
    }

    disconnect(): void {
        this.#cancelActiveAnimation();
        const track = this.#dependencies.resolveTrack();
        if (track) {
            track.classList.remove('is-animating');
            track.classList.remove('is-dragging');
            track.style.removeProperty('transform');
        }
        this.#currentOffsetPx = 0;
    }

    beginDrag(): void {
        this.#cancelActiveAnimation();
        const track = this.#dependencies.resolveTrack();
        if (!track) {
            return;
        }
        track.classList.remove('is-animating');
        track.classList.add('is-dragging');
    }

    updateDrag(deltaPx: number, viewportHeight: number): void {
        this.#cancelActiveAnimation();
        const track = this.#dependencies.resolveTrack();
        if (!track) {
            return;
        }
        this.#currentOffsetPx = deltaPx;
        track.style.setProperty('transform', buildTransform(deltaPx, viewportHeight));
    }

    resetInstant(): void {
        this.#cancelActiveAnimation();
        const track = this.#dependencies.resolveTrack();
        if (!track) {
            this.#currentOffsetPx = 0;
            return;
        }
        track.classList.remove('is-animating');
        track.classList.remove('is-dragging');
        track.style.removeProperty('transform');
        this.#currentOffsetPx = 0;
    }

    animateTo(targetOffsetPx: number, viewportHeight: number): Promise<boolean> {
        this.#cancelActiveAnimation();
        const deferred = createDeferred<boolean>();
        const track = this.#dependencies.resolveTrack();
        if (!track) {
            this.#currentOffsetPx = targetOffsetPx;
            deferred.resolve(true);
            return deferred.promise;
        }
        const applyFinal = (): void => {
            track.style.setProperty('transform', buildTransform(targetOffsetPx, viewportHeight));
            this.#currentOffsetPx = targetOffsetPx;
        };
        if (isReducedMotion()) {
            track.classList.remove('is-animating');
            track.classList.remove('is-dragging');
            applyFinal();
            deferred.resolve(true);
            return deferred.promise;
        }
        if (this.#currentOffsetPx === targetOffsetPx) {
            deferred.resolve(true);
            return deferred.promise;
        }
        track.classList.remove('is-dragging');
        track.classList.add('is-animating');
        let animation: ActiveTrackAnimation | null = null;
        const done = (): void => {
            if (!animation) {
                return;
            }
            this.#currentOffsetPx = targetOffsetPx;
            this.#finishAnimation(animation, true);
        };
        const onEnd = (transitionEvent: TransitionEvent): void => {
            if (transitionEvent.target !== track || transitionEvent.propertyName !== 'transform') {
                return;
            }
            done();
        };
        animation = {
            track,
            onEnd,
            timerId: null,
            resolve: (completed) => deferred.resolve(completed)
        };
        this.#activeAnimation = animation;
        track.addEventListener('transitionend', onEnd);
        this.#dependencies.requestAnimationFrame(() => {
            if (this.#activeAnimation === animation) {
                applyFinal();
            }
        });
        animation.timerId = this.#dependencies.setTimeout(done, ANIMATION_SAFETY_TIMEOUT_MS);
        return deferred.promise;
    }

    #cancelActiveAnimation(): void {
        const animation = this.#activeAnimation;
        if (!animation) {
            return;
        }
        this.#finishAnimation(animation, false);
    }

    #finishAnimation(animation: ActiveTrackAnimation, completed: boolean): void {
        if (this.#activeAnimation !== animation) {
            return;
        }
        this.#activeAnimation = null;
        animation.track.removeEventListener('transitionend', animation.onEnd);
        animation.track.classList.remove('is-animating');
        if (animation.timerId !== null) {
            this.#dependencies.clearTimer(animation.timerId);
        }
        animation.resolve(completed);
    }
}

export { PagerTrackAnimatorController };
