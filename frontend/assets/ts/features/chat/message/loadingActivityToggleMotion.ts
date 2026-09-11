/* SoAI - Chat feature loading activity toggle motion [frontend/assets/ts/features/chat/message/loadingActivityToggleMotion.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { resolveAssistantMessageResponseRoot } from '@features/chat/message/assistantMessageMarkupParts.ts';
import { resolveDirectStreamSegments } from '@features/chat/stream/streamSegmentsMarker.ts';
import { measureLayoutBox, type GeometryBox } from '@core/layout/elementGeometry.ts';
import { isReducedAnimationScope, scaleAnimationDurationMs } from '@core/animations/speed.ts';
import { dom } from '@core/dom/dom.ts';
import { cancelLoadingActivityTransition, clearLoadingActivityTransitionCleanup, clearLoadingActivityAnimations, isLatestLoadingActivityToggleSequence, isRegisteredLoadingActivityTransitionCleanup, recordLoadingActivityAnimation, setLoadingActivityTransitionCleanup } from '@features/chat/message/loadingActivityToggleRegistry.ts';
import { waitForAnimationFrame } from '@features/chat/message/loadingActivityToggleTiming.ts';
import { isRetainedLoadingContentElement, resolveDirectCollapsedLoadingContent } from '@features/chat/message/messageview/loadingActivityCollapsePolicy.ts';

const TOGGLE_DURATION_MS = 180;
const TOGGLE_DURATION_FALLBACK_BUFFER_MS = 40;
const COLLAPSIBLE_ACTIVITY_SELECTOR = '.inline-activity:not(.inline-activity-type-loading)';
interface PersistedContentMotionSnapshot {
    element: HTMLElement;
    rectangle: GeometryBox;
}

const cleanupAnimatedStyles = (element: HTMLElement): void => {
    element.style.removeProperty('height');
    element.style.removeProperty('overflow');
    element.style.removeProperty('transition');
};

const resolveAnimatedActivityNodes = (element: HTMLElement): HTMLElement[] => {
    return dom.resolveAll(COLLAPSIBLE_ACTIVITY_SELECTOR, element).filter((candidate): candidate is HTMLElement => candidate instanceof HTMLElement);
};

const resolvePersistedContentMotionSnapshot = (element: HTMLElement): PersistedContentMotionSnapshot | null => {
    const response = resolveAssistantMessageResponseRoot(element);
    if (response === null) {
        return null;
    }
    const collapsedContent = resolveDirectCollapsedLoadingContent(response);
    const contentRoot = collapsedContent instanceof HTMLElement ? collapsedContent : response;
    const timeline = resolveDirectStreamSegments(contentRoot) ?? contentRoot;
    for (const child of Array.from(timeline.children)) {
        if (child instanceof HTMLElement && isRetainedLoadingContentElement(child)) {
            return { element: child, rectangle: measureLayoutBox(child) };
        }
    }
    return null;
};

const runNodeAnimation = (element: HTMLElement, keyframes: Keyframe[]): Animation | null => {
    if (typeof element.animate !== 'function') {
        return null;
    }
    return element.animate(keyframes, {
        duration: scaleAnimationDurationMs(TOGGLE_DURATION_MS, element),
        easing: 'ease'
    });
};

const resolveLoadingActivityToggleDurationMs = (element: HTMLElement): number => scaleAnimationDurationMs(TOGGLE_DURATION_MS, element);

const resolveLoadingActivityToggleFallbackDurationMs = (element: HTMLElement): number => scaleAnimationDurationMs(TOGGLE_DURATION_MS + TOGGLE_DURATION_FALLBACK_BUFFER_MS, element);

const animateExpandedNodes = (element: HTMLElement, documentRef: Document, messageId: string, sequence: number): void => {
    for (const animatedNode of resolveAnimatedActivityNodes(element)) {
        const animation = runNodeAnimation(animatedNode, [
            { opacity: 0, transform: 'translateY(-8px)' },
            { opacity: 1, transform: 'translateY(0)' }
        ]);
        if (animation) {
            recordLoadingActivityAnimation(documentRef, messageId, sequence, animation);
        }
    }
};

const animatePersistedContentNode = (element: HTMLElement, documentRef: Document, messageId: string, sequence: number, snapshot: PersistedContentMotionSnapshot | null): boolean => {
    if (snapshot === null) {
        return false;
    }
    const content = snapshot.element;
    if (!content.isConnected || !element.contains(content)) {
        return false;
    }
    const nextRect = measureLayoutBox(content);
    const deltaY = snapshot.rectangle.top - nextRect.top;
    if (Math.abs(deltaY) < 1) {
        return false;
    }
    const animation = runNodeAnimation(content, [{ transform: `translateY(${deltaY}px)` }, { transform: 'translateY(0)' }]);
    if (!animation) {
        return false;
    }
    recordLoadingActivityAnimation(documentRef, messageId, sequence, animation);
    return true;
};

const animateMessageTextTransition = (element: HTMLElement, documentRef: Document, messageId: string, sequence: number, startHeight: number, collapsed: boolean, persistedContent: PersistedContentMotionSnapshot | null): void => {
    cancelLoadingActivityTransition(element);
    if (isReducedAnimationScope(element)) {
        cleanupAnimatedStyles(element);
        clearLoadingActivityAnimations(documentRef, messageId, sequence);
        return;
    }
    const endHeight = element.scrollHeight;
    const delta = Math.abs(endHeight - startHeight);
    const animatedNodes = collapsed ? [] : resolveAnimatedActivityNodes(element);
    const contentAnimated = animatePersistedContentNode(element, documentRef, messageId, sequence, persistedContent);
    if (delta < 1 && animatedNodes.length === 0 && !contentAnimated) {
        cleanupAnimatedStyles(element);
        clearLoadingActivityAnimations(documentRef, messageId, sequence);
        return;
    }
    element.style.setProperty('height', `${Math.max(startHeight, 0)}px`);
    element.style.setProperty('overflow', 'hidden');
    element.style.setProperty('transition', `height ${resolveLoadingActivityToggleDurationMs(element)}ms ease`);
    let timeoutId: number | null = null;
    let settled = false;
    const cleanup = (): void => {
        if (settled) {
            return;
        }
        settled = true;
        if (timeoutId !== null) {
            element.ownerDocument.defaultView?.clearTimeout(timeoutId);
            timeoutId = null;
        }
        element.removeEventListener('transitionend', onEnd);
        cleanupAnimatedStyles(element);
        clearLoadingActivityTransitionCleanup(element);
        clearLoadingActivityAnimations(documentRef, messageId, sequence);
    };
    const onEnd = (event: TransitionEvent): void => {
        if (event.target !== element || event.propertyName !== 'height') {
            return;
        }
        cleanup();
    };
    setLoadingActivityTransitionCleanup(element, cleanup);
    element.addEventListener('transitionend', onEnd);
    const view = element.ownerDocument.defaultView;
    if (view && typeof view.setTimeout === 'function') {
        timeoutId = view.setTimeout(() => {
            if (isRegisteredLoadingActivityTransitionCleanup(element, cleanup)) {
                cleanup();
            }
        }, resolveLoadingActivityToggleFallbackDurationMs(element));
    }
    waitForAnimationFrame(element, () => {
        if (!element.isConnected || !isLatestLoadingActivityToggleSequence(documentRef, messageId, sequence) || !isRegisteredLoadingActivityTransitionCleanup(element, cleanup)) {
            return;
        }
        element.style.setProperty('height', `${Math.max(endHeight, 0)}px`);
    });
    if (!collapsed) {
        animateExpandedNodes(element, documentRef, messageId, sequence);
    }
};

export { animateMessageTextTransition, resolvePersistedContentMotionSnapshot };
