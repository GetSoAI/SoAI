/* SoAI - Chat feature loading activity toggle registry [frontend/assets/ts/features/chat/message/loadingActivityToggleRegistry.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

interface LoadingActivityAnimationState {
    sequence: number;
    animations: Animation[];
}

const toggleSequenceByDocument = new WeakMap<Document, Map<string, number>>();
const loadingActivityAnimationsByDocument = new WeakMap<Document, Map<string, LoadingActivityAnimationState>>();
const transitionCleanupByElement = new WeakMap<HTMLElement, () => void>();

const getToggleSequenceMap = (documentRef: Document): Map<string, number> => {
    const existing = toggleSequenceByDocument.get(documentRef);
    if (existing) {
        return existing;
    }
    const created = new Map<string, number>();
    toggleSequenceByDocument.set(documentRef, created);
    return created;
};

const getLoadingActivityAnimationMap = (documentRef: Document): Map<string, LoadingActivityAnimationState> => {
    const existing = loadingActivityAnimationsByDocument.get(documentRef);
    if (existing) {
        return existing;
    }
    const created = new Map<string, LoadingActivityAnimationState>();
    loadingActivityAnimationsByDocument.set(documentRef, created);
    return created;
};

const beginLoadingActivityToggleSequence = (documentRef: Document, messageId: string): number => {
    const sequenceMap = getToggleSequenceMap(documentRef);
    const nextSequence = (sequenceMap.get(messageId) ?? 0) + 1;
    sequenceMap.set(messageId, nextSequence);
    return nextSequence;
};

const isLatestLoadingActivityToggleSequence = (documentRef: Document, messageId: string, sequence: number): boolean => {
    return getToggleSequenceMap(documentRef).get(messageId) === sequence;
};

const beginLoadingActivityAnimations = (documentRef: Document, messageId: string, sequence: number): LoadingActivityAnimationState => {
    const animationMap = getLoadingActivityAnimationMap(documentRef);
    const previous = animationMap.get(messageId);
    if (previous) {
        for (const animation of previous.animations) {
            animation.cancel();
        }
    }
    const current: LoadingActivityAnimationState = {
        sequence,
        animations: []
    };
    animationMap.set(messageId, current);
    return current;
};

const recordLoadingActivityAnimation = (documentRef: Document, messageId: string, sequence: number, animation: Animation): void => {
    const animationMap = getLoadingActivityAnimationMap(documentRef);
    const current = animationMap.get(messageId);
    if (!current || current.sequence !== sequence) {
        animation.cancel();
        return;
    }
    current.animations.push(animation);
};

const clearLoadingActivityAnimations = (documentRef: Document, messageId: string, sequence: number): void => {
    const animationMap = getLoadingActivityAnimationMap(documentRef);
    const current = animationMap.get(messageId);
    if (!current || current.sequence !== sequence) {
        return;
    }
    for (const animation of current.animations) {
        animation.cancel();
    }
    animationMap.delete(messageId);
};

const cancelLoadingActivityTransition = (element: HTMLElement): void => {
    const cleanup = transitionCleanupByElement.get(element);
    if (!cleanup) {
        return;
    }
    transitionCleanupByElement.delete(element);
    cleanup();
};

const setLoadingActivityTransitionCleanup = (element: HTMLElement, cleanup: () => void): void => {
    transitionCleanupByElement.set(element, cleanup);
};

const clearLoadingActivityTransitionCleanup = (element: HTMLElement): void => {
    transitionCleanupByElement.delete(element);
};

const isRegisteredLoadingActivityTransitionCleanup = (element: HTMLElement, cleanup: () => void): boolean => {
    return transitionCleanupByElement.get(element) === cleanup;
};

export { beginLoadingActivityAnimations, beginLoadingActivityToggleSequence, cancelLoadingActivityTransition, clearLoadingActivityAnimations, clearLoadingActivityTransitionCleanup, isLatestLoadingActivityToggleSequence, isRegisteredLoadingActivityTransitionCleanup, recordLoadingActivityAnimation, setLoadingActivityTransitionCleanup };
export type { LoadingActivityAnimationState };
