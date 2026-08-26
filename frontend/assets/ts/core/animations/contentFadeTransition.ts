/* SoAI - Sequenced content fade transitions [frontend/assets/ts/core/animations/contentFadeTransition.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { scaleAnimationDurationMs } from '@core/animations/speed.ts';
import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';

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

const finishContentFadeIn = (elements: readonly HTMLElement[], sequence: number, animations: readonly Animation[]): void => {
    cancelAnimationGroup(animations);
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

const finishContentFadeOut = (options: ContentFadeTransitionOptions, sequence: number, animations: readonly Animation[]): void => {
    cancelAnimationGroup(animations);
    if (!isContentTransitionCurrent(options.elements, sequence)) {
        return;
    }
    options.elements.forEach((element) => {
        element.style.opacity = '0';
    });
    options.render();
    const fadeInAnimations = createContentFadeInAnimations(options.elements);
    terminateHandledPromise(Promise.allSettled(fadeInAnimations.map((animation) => animation.finished)).then(() => finishContentFadeIn(options.elements, sequence, fadeInAnimations)));
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
    if (!elements.length || !elements.some((element) => element.hasChildNodes())) {
        options.render();
        clearContentOpacity(elements);
        return;
    }
    const fadeOutAnimations = createContentFadeOutAnimations(elements);
    terminateHandledPromise(Promise.allSettled(fadeOutAnimations.map((animation) => animation.finished)).then(() => finishContentFadeOut({ elements, render: options.render }, sequence, fadeOutAnimations)));
};

export { renderContentImmediately, transitionContentElements };
