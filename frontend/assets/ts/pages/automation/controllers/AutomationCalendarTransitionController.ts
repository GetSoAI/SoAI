/* SoAI - Automation page calendar transition controller [frontend/assets/ts/pages/automation/controllers/AutomationCalendarTransitionController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { isReduceMotionsEnabled, waitForElementAnimations } from '@core/pageTransitions.ts';
import { optionalAutomationCalendarStage, requireAutomationCalendarStage } from '@pages/automation/dom.ts';

type PendingTransition = {
    direction: 'detail-forward' | 'detail-backward';
    variant: 'standard' | 'slow';
    windowSignature: string;
};

const CALENDAR_TRANSITION_PRIMED_CLASS = 'is-view-transition-primed';
const CALENDAR_TRANSITIONING_IN_CLASS = 'automation-calendar-transitioning-in';

class AutomationCalendarTransitionController {
    readonly #calendarRoot: HTMLElement;
    readonly #requestAnimationFrame: (callback: () => void) => number;
    #transitionToken = 0;
    #pendingTransition: PendingTransition | null = null;
    #disposed = false;

    constructor(dependencies: { calendarRoot: HTMLElement; requestAnimationFrame: (callback: () => void) => number }) {
        this.#calendarRoot = dependencies.calendarRoot;
        this.#requestAnimationFrame = dependencies.requestAnimationFrame;
    }

    stage(direction: 'detail-forward' | 'detail-backward', windowSignature: string, variant: 'standard' | 'slow' = 'standard'): void {
        this.#pendingTransition = { direction, windowSignature, variant };
        this.#transitionToken += 1;
        this.#resetDomState();
    }

    playPending(renderedWindowSignature: string): void {
        const pendingTransition = this.#pendingTransition;
        if (!pendingTransition || this.#disposed) {
            return;
        }
        if (pendingTransition.windowSignature !== renderedWindowSignature) {
            return;
        }
        const animatedChild = requireAutomationCalendarStage(this.#calendarRoot);
        if (isReduceMotionsEnabled()) {
            this.#resetDomState();
            this.#pendingTransition = null;
            return;
        }
        this.#pendingTransition = null;
        this.#transitionToken += 1;
        const token = this.#transitionToken;
        this.#calendarRoot.dataset['viewTransition'] = pendingTransition.direction;
        if (pendingTransition.variant !== 'standard') {
            this.#calendarRoot.dataset['viewTransitionVariant'] = pendingTransition.variant;
        }
        animatedChild.classList.add(CALENDAR_TRANSITION_PRIMED_CLASS);
        this.#requestAnimationFrame(() => {
            if (this.#disposed || this.#transitionToken !== token) {
                return;
            }
            if (!animatedChild.isConnected) {
                this.#resetDomState(animatedChild);
                return;
            }
            animatedChild.classList.remove(CALENDAR_TRANSITIONING_IN_CLASS);
            void animatedChild.offsetWidth;
            animatedChild.classList.add(CALENDAR_TRANSITIONING_IN_CLASS);
            animatedChild.classList.remove(CALENDAR_TRANSITION_PRIMED_CLASS);
            this.#requestAnimationFrame(() => {
                if (this.#disposed || this.#transitionToken !== token) {
                    return;
                }
                void waitForElementAnimations(animatedChild, { ensureStarted: false })
                    .catch((error) => {
                        errorHandler.debug('AutomationCalendarTransitionController', 'Calendar transition animation wait failed', ensureError(error));
                    })
                    .finally(() => {
                        if (this.#disposed || this.#transitionToken !== token) {
                            return;
                        }
                        this.#resetDomState(animatedChild);
                    });
            });
        });
    }

    dispose(): void {
        this.#disposed = true;
        this.#pendingTransition = null;
        this.#transitionToken += 1;
        this.#resetDomStateIfPresent();
    }

    #resetDomState(animatedChild?: HTMLElement): void {
        delete this.#calendarRoot.dataset['viewTransition'];
        delete this.#calendarRoot.dataset['viewTransitionVariant'];
        const stage = animatedChild ?? requireAutomationCalendarStage(this.#calendarRoot);
        stage.classList.remove(CALENDAR_TRANSITIONING_IN_CLASS);
        stage.classList.remove(CALENDAR_TRANSITION_PRIMED_CLASS);
    }

    #resetDomStateIfPresent(): void {
        delete this.#calendarRoot.dataset['viewTransition'];
        delete this.#calendarRoot.dataset['viewTransitionVariant'];
        const stage = optionalAutomationCalendarStage(this.#calendarRoot);
        if (!stage) {
            return;
        }
        stage.classList.remove(CALENDAR_TRANSITIONING_IN_CLASS);
        stage.classList.remove(CALENDAR_TRANSITION_PRIMED_CLASS);
    }
}

export { AutomationCalendarTransitionController };
