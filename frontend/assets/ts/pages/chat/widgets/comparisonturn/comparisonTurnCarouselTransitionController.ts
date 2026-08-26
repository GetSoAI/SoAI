/* SoAI - Unified comparison-turn carousel movement and viewport transition ownership [frontend/assets/ts/pages/chat/widgets/comparisonturn/comparisonTurnCarouselTransitionController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { measureLayoutBox } from '@core/layout/elementGeometry.ts';
import { resolveTrackTransformTransitionTotalMs } from '@pages/chat/widgets/comparisonturn/comparisonTurnTrackTransitionTimingController.ts';

type ComparisonTurnTimerHost = {
    setTimer: (functionValue: () => void, delayMs: number) => number;
    clearTimer: (timerId: number) => void;
};

type CarouselTransitionState = {
    track: HTMLElement;
    activeIndex: number;
    transitioningToIndex: number | null;
    settleViewportHeight: () => void;
    onTransitionEnd: ((event: TransitionEvent) => void) | null;
    onTransitionCancel: ((event: TransitionEvent) => void) | null;
    settleTimerId: number | null;
    transitionToken: number;
};

type CarouselTransitionSyncArguments = {
    root: HTMLElement;
    track: HTMLElement;
    activeIndex: number;
    resolveSlideHeight: (index: number) => number;
    resolveCachedHeight: (index: number) => number;
    setViewportHeight: (height: number) => void;
    settleViewportHeight: () => void;
};

class ComparisonTurnCarouselTransitionController {
    readonly #stateByRoot = new Map<HTMLElement, CarouselTransitionState>();
    readonly #timers: ComparisonTurnTimerHost;
    #nextTransitionToken = 1;

    constructor(timers: ComparisonTurnTimerHost) {
        this.#timers = timers;
    }

    dispose(): void {
        for (const state of this.#stateByRoot.values()) this.#clearTransitionTracking(state);
        this.#stateByRoot.clear();
    }

    pruneKnownRoots(knownRoots: ReadonlySet<HTMLElement>): void {
        for (const [root, state] of this.#stateByRoot.entries()) {
            if (!root.isConnected || !knownRoots.has(root)) {
                this.#clearTransitionTracking(state);
                this.#stateByRoot.delete(root);
            }
        }
    }

    isLocked(root: HTMLElement): boolean {
        const state = this.#stateByRoot.get(root) ?? null;
        return state !== null && state.transitioningToIndex !== null;
    }

    sync(inputArguments: CarouselTransitionSyncArguments): void {
        const existing = this.#stateByRoot.get(inputArguments.root) ?? null;
        if (!existing || existing.track !== inputArguments.track || inputArguments.root.getAttribute('data-comparison-mounted') !== 'true') {
            if (existing) this.#clearTransitionTracking(existing);
            this.#setSettledPosition(inputArguments.track, inputArguments.activeIndex);
            this.#stateByRoot.set(inputArguments.root, this.#createSettledState(inputArguments));
            inputArguments.settleViewportHeight();
            return;
        }
        const previousIndex = existing.activeIndex;
        existing.activeIndex = inputArguments.activeIndex;
        existing.settleViewportHeight = inputArguments.settleViewportHeight;
        if (previousIndex === inputArguments.activeIndex) {
            if (existing.transitioningToIndex === null) inputArguments.settleViewportHeight();
            return;
        }

        const fromHeight = Math.max(inputArguments.resolveCachedHeight(previousIndex), inputArguments.resolveSlideHeight(previousIndex));
        const toHeight = Math.max(inputArguments.resolveCachedHeight(inputArguments.activeIndex), inputArguments.resolveSlideHeight(inputArguments.activeIndex));
        const lockedHeight = Math.max(fromHeight, toHeight);
        if (lockedHeight > 0) inputArguments.setViewportHeight(lockedHeight);

        const totalMs = resolveTrackTransformTransitionTotalMs(inputArguments.track);
        const previousLeft = measureLayoutBox(inputArguments.track).left;
        this.#clearTransitionTracking(existing);
        inputArguments.track.style.setProperty('transition', 'none');
        this.#setSettledPosition(inputArguments.track, inputArguments.activeIndex);
        const nextLeft = measureLayoutBox(inputArguments.track).left;
        const offsetPx = previousLeft - nextLeft;
        if (totalMs <= 0) {
            inputArguments.track.style.removeProperty('transition');
            existing.settleViewportHeight();
            return;
        }
        if (Math.abs(offsetPx) >= 0.5) {
            inputArguments.track.style.setProperty('transform', `translateX(${String(offsetPx)}px)`);
            measureLayoutBox(inputArguments.track);
        }
        inputArguments.track.style.removeProperty('transition');
        if (Math.abs(offsetPx) >= 0.5) inputArguments.track.style.setProperty('transform', 'translateX(0px)');
        this.#trackTransition(inputArguments.root, existing, inputArguments.activeIndex, totalMs);
    }

    #createSettledState(inputArguments: CarouselTransitionSyncArguments): CarouselTransitionState {
        return {
            track: inputArguments.track,
            activeIndex: inputArguments.activeIndex,
            transitioningToIndex: null,
            settleViewportHeight: inputArguments.settleViewportHeight,
            onTransitionEnd: null,
            onTransitionCancel: null,
            settleTimerId: null,
            transitionToken: 0
        };
    }

    #setSettledPosition(track: HTMLElement, activeIndex: number): void {
        track.style.setProperty('margin-left', `-${String(activeIndex * 100)}%`);
        track.style.removeProperty('transform');
    }

    #trackTransition(root: HTMLElement, state: CarouselTransitionState, activeIndex: number, totalMs: number): void {
        const token = this.#nextTransitionToken;
        this.#nextTransitionToken += 1;
        state.transitioningToIndex = activeIndex;
        state.transitionToken = token;
        const settle = (): void => {
            const latest = this.#stateByRoot.get(root) ?? null;
            if (!latest || latest.transitionToken !== token || latest.transitioningToIndex !== latest.activeIndex) return;
            this.#clearTransitionTracking(latest);
            latest.track.style.removeProperty('transform');
            latest.settleViewportHeight();
        };
        state.onTransitionEnd = (event): void => {
            if (event.target === state.track && event.propertyName === 'transform') settle();
        };
        state.onTransitionCancel = (event): void => {
            if (event.target === state.track && event.propertyName === 'transform') settle();
        };
        state.track.addEventListener('transitionend', state.onTransitionEnd);
        state.track.addEventListener('transitioncancel', state.onTransitionCancel);
        state.settleTimerId = this.#timers.setTimer(settle, totalMs + 60);
    }

    #clearTransitionTracking(state: CarouselTransitionState): void {
        if (state.onTransitionEnd) state.track.removeEventListener('transitionend', state.onTransitionEnd);
        if (state.onTransitionCancel) state.track.removeEventListener('transitioncancel', state.onTransitionCancel);
        if (state.settleTimerId !== null) this.#timers.clearTimer(state.settleTimerId);
        state.onTransitionEnd = null;
        state.onTransitionCancel = null;
        state.settleTimerId = null;
        state.transitioningToIndex = null;
        state.transitionToken = 0;
    }
}

export { ComparisonTurnCarouselTransitionController };
