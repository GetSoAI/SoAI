/* SoAI - Presence enter/exit orchestration with exit holds [frontend/assets/ts/core/animations/presence/presenceTransitions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { animatePresenceExit, preparePresenceEnter, stopPresenceAnimation } from '@core/animations/presence/presenceMotion.ts';

const PRESENCE_STATE_ATTRIBUTE = 'data-presence-state';
const PRESENCE_EXITING_STATE = 'exiting';
const PRESENCE_EXITING_SELECTOR = `[${PRESENCE_STATE_ATTRIBUTE}='${PRESENCE_EXITING_STATE}']`;
type PresenceCompletion = (element: HTMLElement) => void;

interface PresenceHold {
    heldDisplay: string | null;
    inlineDisplay: string;
    inlineDisplayPriority: string;
    wasInert: boolean;
    completions: Set<PresenceCompletion>;
}

const presenceHolds = new WeakMap<Element, PresenceHold>();
const presenceEnterRequests = new WeakMap<Element, boolean>();
const requestPresenceEnter = (element: Element, animate = true): void => {
    presenceEnterRequests.set(element, animate);
};

const consumePresenceEnterRequest = (element: Element): boolean | undefined => {
    const requested = presenceEnterRequests.get(element);
    presenceEnterRequests.delete(element);
    return requested;
};

const isPresenceExiting = (element: Element): boolean => presenceHolds.has(element);

const findExitingAncestor = (element: HTMLElement): HTMLElement | null => {
    const ancestor = element.parentElement?.closest(PRESENCE_EXITING_SELECTOR) ?? null;
    return ancestor instanceof HTMLElement && presenceHolds.has(ancestor) ? ancestor : null;
};

const applyPresenceHold = (element: HTMLElement, heldDisplay: string | null): PresenceHold => {
    const hold: PresenceHold = {
        heldDisplay,
        inlineDisplay: element.style.getPropertyValue('display'),
        inlineDisplayPriority: element.style.getPropertyPriority('display'),
        wasInert: element.inert,
        completions: new Set()
    };
    if (heldDisplay) {
        element.style.setProperty('display', heldDisplay, 'important');
    }
    element.inert = true;
    element.setAttribute(PRESENCE_STATE_ATTRIBUTE, PRESENCE_EXITING_STATE);
    presenceHolds.set(element, hold);
    return hold;
};

const releasePresenceHold = (element: HTMLElement, hold: PresenceHold): void => {
    presenceHolds.delete(element);
    if (hold.heldDisplay) {
        if (hold.inlineDisplay) {
            element.style.setProperty('display', hold.inlineDisplay, hold.inlineDisplayPriority);
        } else {
            element.style.removeProperty('display');
        }
    }
    element.inert = hold.wasInert;
    element.removeAttribute(PRESENCE_STATE_ATTRIBUTE);
};

const settlePresenceExit = (element: HTMLElement, hold: PresenceHold): void => {
    if (presenceHolds.get(element) !== hold) {
        return;
    }
    releasePresenceHold(element, hold);
    hold.completions.forEach((complete) => complete(element));
};

const runPresenceExitAnimation = (element: HTMLElement, hold: PresenceHold): void => {
    const animation = animatePresenceExit(element);
    if (!animation) {
        settlePresenceExit(element, hold);
        return;
    }
    const settleCancelledExit = (): void => {
        settlePresenceExit(element, hold);
    };
    animation.addEventListener('cancel', settleCancelledExit, { once: true });
    animation.addEventListener(
        'finish',
        () => {
            settlePresenceExit(element, hold);
            animation.cancel();
        },
        { once: true }
    );
};

const exitWithPresence = (element: HTMLElement, heldDisplay: string | null, complete: PresenceCompletion | null): void => {
    const existing = presenceHolds.get(element);
    if (existing) {
        if (complete) {
            existing.completions.add(complete);
        }
        return;
    }
    const hold = applyPresenceHold(element, heldDisplay);
    if (complete) {
        hold.completions.add(complete);
    }
    runPresenceExitAnimation(element, hold);
};
const revivePresence = (element: HTMLElement): void => {
    const hold = presenceHolds.get(element);
    if (!hold) {
        return;
    }
    releasePresenceHold(element, hold);
};

const prepareEnterWithPresence = (element: HTMLElement, animate: boolean, visualOnly = false): (() => void) => {
    revivePresence(element);
    if (animate && !findExitingAncestor(element)) {
        const start = preparePresenceEnter(element, visualOnly);
        return () => {
            start();
        };
    }
    return () => stopPresenceAnimation(element);
};

export { PRESENCE_EXITING_SELECTOR, consumePresenceEnterRequest, exitWithPresence, isPresenceExiting, prepareEnterWithPresence, requestPresenceEnter };
