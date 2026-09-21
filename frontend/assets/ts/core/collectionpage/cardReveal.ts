/* SoAI - Shared collection page card reveal [frontend/assets/ts/core/collectionpage/cardReveal.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isReducedAnimationScope } from '@core/animations/speed.ts';
import { dom } from '@core/dom/dom.ts';
import { signalAborted } from '@core/lifecycle/abortSignals.ts';

const COLLECTION_CARD_REVEAL_READY_CLASS = 'is-collection-card-reveal-ready';
const COLLECTION_CARD_ENTERING_CLASS = 'entering';
const COLLECTION_CARD_HYDRATING_CLASS = 'is-hydrating';
const COLLECTION_CARD_ENTER_ANIMATION_NAME = 'card-enter';
const COLLECTION_CARD_REVEAL_LIMIT = 24;
const COLLECTION_CARD_REVEAL_STEP_MS = 18;
const COLLECTION_CARD_REVEAL_TARGET_SELECTOR = '.ui-collection-card, .model-card, .plugin-card, .prompt-card, .models-list-row, .plugins-list-row, .prompts-list-row, .os-network-device-list-row';

const requireCollectionRevealSection = (section: HTMLElement | null): HTMLElement => {
    if (!section) {
        throw new Error('Collection card reveal requires a page section');
    }
    return section;
};

const areCollectionCardRevealAnimationsDisabled = (scope: Document | Element): boolean => {
    return isReducedAnimationScope(scope);
};

const formatCollectionCardRevealDelay = (index: number): string => `${index * COLLECTION_CARD_REVEAL_STEP_MS}ms`;

const resolveCollectionCardRevealTargets = (node: HTMLElement): HTMLElement[] => {
    const view = node.ownerDocument.defaultView;
    if (view?.getComputedStyle(node).display !== 'contents') {
        return [node];
    }
    const cards = dom.resolveAll(COLLECTION_CARD_REVEAL_TARGET_SELECTOR, node).filter((element): element is HTMLElement => element instanceof HTMLElement);
    if (cards.length) {
        return cards;
    }
    throw new Error('Collection display-contents item requires explicit card reveal targets');
};

const clearCollectionCardRevealTarget = (node: HTMLElement): void => {
    node.classList.remove(COLLECTION_CARD_ENTERING_CLASS);
    node.style.removeProperty('--collection-enter-delay');
};

const readCollectionCardRevealDelay = (node: HTMLElement): string | null => {
    for (const target of resolveCollectionCardRevealTargets(node)) {
        if (target.classList.contains(COLLECTION_CARD_ENTERING_CLASS)) {
            return target.style.getPropertyValue('--collection-enter-delay');
        }
    }
    return null;
};

const armCollectionCardRevealTarget = (node: HTMLElement, delay: string): void => {
    if (delay) {
        node.style.setProperty('--collection-enter-delay', delay);
    } else {
        node.style.removeProperty('--collection-enter-delay');
    }
    if (node.classList.contains(COLLECTION_CARD_ENTERING_CLASS)) {
        return;
    }
    node.classList.add(COLLECTION_CARD_ENTERING_CLASS);
    const cleanup = (event: Event): void => {
        if (!(event instanceof AnimationEvent) || event.target !== node || event.animationName !== COLLECTION_CARD_ENTER_ANIMATION_NAME) {
            return;
        }
        node.removeEventListener('animationend', cleanup);
        node.removeEventListener('animationcancel', cleanup);
        clearCollectionCardRevealTarget(node);
    };
    node.addEventListener('animationend', cleanup);
    node.addEventListener('animationcancel', cleanup);
};

const armCollectionCardRevealTargets = (node: HTMLElement, delay: string): void => {
    for (const target of resolveCollectionCardRevealTargets(node)) {
        armCollectionCardRevealTarget(target, delay);
    }
};

const armCollectionCardRevealTargetsAtIndex = (node: HTMLElement, index: number): void => {
    armCollectionCardRevealTargets(node, formatCollectionCardRevealDelay(index));
};

const hasCollectionCardRevealTargetArmed = (node: HTMLElement): boolean => {
    const targets = resolveCollectionCardRevealTargets(node);
    if (!targets.length) {
        return false;
    }
    for (const target of targets) {
        if (!target.classList.contains(COLLECTION_CARD_ENTERING_CLASS)) {
            return false;
        }
    }
    return true;
};

const isCollectionCardRevealHydrating = (grid: HTMLElement): boolean => grid.classList.contains(COLLECTION_CARD_HYDRATING_CLASS);

const markCollectionCardRevealHydrating = (grid: HTMLElement): void => {
    grid.classList.add(COLLECTION_CARD_HYDRATING_CLASS);
};

const clearCollectionCardRevealHydrating = (grid: HTMLElement): void => {
    grid.classList.remove(COLLECTION_CARD_HYDRATING_CLASS);
};

const stageCollectionCardReveal = (section: HTMLElement | null, signal: AbortSignal | null): void => {
    if (signalAborted(signal)) {
        return;
    }
    requireCollectionRevealSection(section).classList.remove(COLLECTION_CARD_REVEAL_READY_CLASS);
};

const releaseCollectionCardReveal = (section: HTMLElement | null, signal: AbortSignal | null): void => {
    if (signalAborted(signal)) {
        return;
    }
    requireCollectionRevealSection(section).classList.add(COLLECTION_CARD_REVEAL_READY_CLASS);
};

const stageCollectionGridCardReveal = (section: HTMLElement | null, grid: HTMLElement, signal: AbortSignal | null): void => {
    stageCollectionCardReveal(section, signal);
    if (signalAborted(signal)) {
        return;
    }
    markCollectionCardRevealHydrating(grid);
    try {
        if (areCollectionCardRevealAnimationsDisabled(grid)) {
            return;
        }
        let index = 0;
        for (const child of Array.from(grid.children)) {
            if (index >= COLLECTION_CARD_REVEAL_LIMIT) {
                break;
            }
            if (!(child instanceof HTMLElement)) {
                continue;
            }
            armCollectionCardRevealTargetsAtIndex(child, index);
            index += 1;
        }
    } finally {
        clearCollectionCardRevealHydrating(grid);
    }
};

const armCollectionCardRevealTargetsForCommit = (nodes: readonly HTMLElement[]): void => {
    const document = nodes[0]?.ownerDocument;
    if (document === undefined || nodes.length === 0 || areCollectionCardRevealAnimationsDisabled(document)) return;
    const targetsByNode = nodes.map(resolveCollectionCardRevealTargets);
    targetsByNode.forEach((targets, index) => {
        const delay = formatCollectionCardRevealDelay(index);
        targets.forEach((target) => armCollectionCardRevealTarget(target, delay));
    });
};

export { COLLECTION_CARD_REVEAL_LIMIT, areCollectionCardRevealAnimationsDisabled, armCollectionCardRevealTargets, armCollectionCardRevealTargetsAtIndex, armCollectionCardRevealTargetsForCommit, clearCollectionCardRevealHydrating, hasCollectionCardRevealTargetArmed, isCollectionCardRevealHydrating, markCollectionCardRevealHydrating, readCollectionCardRevealDelay, releaseCollectionCardReveal, stageCollectionCardReveal, stageCollectionGridCardReveal };
