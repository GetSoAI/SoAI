/* SoAI - Sequenced content fade transitions [frontend/assets/ts/core/animations/contentFadeTransition.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { scaleAnimationDurationMs } from '@core/animations/speed.ts';
import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { waitForElementAnimations } from '@core/pageTransitions.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { isAbortError } from '@core/errors/abort.ts';
import { ensureError } from '@core/errors/coerce.ts';

const CONTENT_FADE_TRANSITION_DURATION_MS = 240;
const contentTransitionSequences = new WeakMap<HTMLElement, number>();

interface ContentFadeTransitionOptions {
    elements: readonly HTMLElement[];
    render: () => void;
}

const nextContentTransitionSequence = (elements: readonly HTMLElement[]): number => {
    const sequence = elements.reduce((highest, element) => Math.max(highest, contentTransitionSequences.get(element) ?? 0), 0) + 1;
    elements.forEach((element) => {
        contentTransitionSequences.set(element, sequence);
    });
    return sequence;
};

const cancelContentAnimations = (elements: readonly HTMLElement[], options: { preserveOpacity?: boolean } = {}): void => {
    elements.forEach((element) => {
        if (options.preserveOpacity === true) {
            element.style.opacity = getComputedStyle(element).opacity;
        }
        element.getAnimations({ subtree: true }).forEach((animation) => animation.cancel());
    });
};

const isContentTransitionCurrent = (elements: readonly HTMLElement[], sequence: number): boolean => {
    return elements.every((element) => element.isConnected && contentTransitionSequences.get(element) === sequence);
};

const cancelAnimationGroup = (animations: readonly Animation[]): void => {
    animations.forEach((animation) => animation.cancel());
};

const clearContentOpacity = (elements: readonly HTMLElement[]): void => {
    elements.forEach((element) => {
        element.style.opacity = '';
    });
};

const waitForContentAnimations = async (elements: readonly HTMLElement[], animations: readonly Animation[]): Promise<void> => {
    const element = elements[0];
    if (!element) throw new Error('Content fade requires an animation owner');
    try {
        await waitForElementAnimations(element, { ensureStarted: false, animations });
    } catch (error) {
        if (!isAbortError(error)) errorHandler.warn('ContentFadeTransition', 'Content animation did not complete', ensureError(error));
    } finally {
        cancelAnimationGroup(animations);
    }
};

const finishContentFadeIn = (elements: readonly HTMLElement[], sequence: number): void => {
    if (!isContentTransitionCurrent(elements, sequence)) {
        return;
    }
    clearContentOpacity(elements);
};

const createContentFadeInAnimations = (elements: readonly HTMLElement[]): Animation[] => {
    elements.forEach((element) => {
        element.style.opacity = '1';
    });
    return elements.map((element) =>
        element.animate([{ opacity: 0 }, { opacity: 1 }], {
            duration: scaleAnimationDurationMs(CONTENT_FADE_TRANSITION_DURATION_MS, element),
            easing: 'ease'
        })
    );
};

const finishContentFadeOut = (options: ContentFadeTransitionOptions, sequence: number): void => {
    if (!isContentTransitionCurrent(options.elements, sequence)) {
        return;
    }
    options.elements.forEach((element) => {
        element.style.opacity = '0';
    });
    options.render();
    for (const element of options.elements) {
        for (const animation of element.getAnimations({ subtree: true })) {
            if (animation instanceof CSSTransition) animation.finish();
        }
    }
    if (options.elements.some((element) => element.ownerDocument.visibilityState === 'hidden')) {
        clearContentOpacity(options.elements);
        return;
    }
    const fadeInAnimations = createContentFadeInAnimations(options.elements);
    terminateHandledPromise(waitForContentAnimations(options.elements, fadeInAnimations).then(() => finishContentFadeIn(options.elements, sequence)));
};

const createContentFadeOutAnimations = (elements: readonly HTMLElement[]): Animation[] => {
    return elements.map((element) => {
        const startOpacity = element.style.opacity || getComputedStyle(element).opacity;
        element.style.opacity = '0';
        return element.animate([{ opacity: startOpacity }, { opacity: 0 }], {
            duration: scaleAnimationDurationMs(CONTENT_FADE_TRANSITION_DURATION_MS, element),
            easing: 'ease'
        });
    });
};

const renderContentImmediately = (options: ContentFadeTransitionOptions): void => {
    nextContentTransitionSequence(options.elements);
    cancelContentAnimations(options.elements);
    clearContentOpacity(options.elements);
    options.render();
};

const transitionContentElements = (options: ContentFadeTransitionOptions): void => {
    const elements = options.elements.filter((element) => element.isConnected);
    const sequence = nextContentTransitionSequence(elements);
    cancelContentAnimations(elements, { preserveOpacity: true });
    if (!elements.length || !elements.some((element) => element.hasChildNodes()) || elements.some((element) => element.ownerDocument.visibilityState === 'hidden')) {
        options.render();
        clearContentOpacity(elements);
        return;
    }
    const fadeOutAnimations = createContentFadeOutAnimations(elements);
    terminateHandledPromise(waitForContentAnimations(elements, fadeOutAnimations).then(() => finishContentFadeOut({ elements, render: options.render }, sequence)));
};

export { renderContentImmediately, transitionContentElements };
