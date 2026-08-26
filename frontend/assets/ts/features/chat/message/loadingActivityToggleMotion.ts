/* SoAI - Chat feature loading activity toggle motion [frontend/assets/ts/features/chat/message/loadingActivityToggleMotion.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { measureLayoutBox, type GeometryBox } from '@core/layout/elementGeometry.ts';
import { prefersReducedMotion } from '@core/animations/prefersReducedMotion.ts';
import { scaleAnimationDurationMs } from '@core/animations/speed.ts';
import { dom } from '@core/dom/dom.ts';
import { cancelLoadingActivityTransition, clearLoadingActivityTransitionCleanup, clearLoadingActivityAnimations, isLatestLoadingActivityToggleSequence, isRegisteredLoadingActivityTransitionCleanup, recordLoadingActivityAnimation, scheduleLoadingActivityAnimationCleanup, setLoadingActivityTransitionCleanup, type LoadingActivityAnimationState } from '@features/chat/message/loadingActivityToggleRegistry.ts';
import { waitForAnimationFrame, waitForDuration } from '@features/chat/message/loadingActivityToggleTiming.ts';
import { COLLAPSED_LOADING_CONTENT_SELECTOR } from '@features/chat/message/messageview/loadingActivityCollapsePolicy.ts';

const TOGGLE_DURATION_MS = 180;
const TOGGLE_DURATION_FALLBACK_BUFFER_MS = 40;
const TOGGLE_HOVER_ATTRIBUTE = 'data-loading-toggle-hover';
const LOADING_HEADER_SELECTOR = '.inline-activity.inline-activity-type-loading > .inline-activity-header[aria-disabled="false"]';
const COLLAPSIBLE_ACTIVITY_SELECTOR = '.inline-activity:not(.inline-activity-type-loading)';
const MESSAGE_RESPONSE_SELECTOR = '.message-response';

const cleanupAnimatedStyles = (element: HTMLElement): void => {
    element.style.removeProperty('height');
    element.style.removeProperty('overflow');
    element.style.removeProperty('transition');
};

const resolveAnimatedActivityNodes = (element: HTMLElement): HTMLElement[] => {
    return dom.resolveAll(COLLAPSIBLE_ACTIVITY_SELECTOR, element).filter((candidate): candidate is HTMLElement => candidate instanceof HTMLElement);
};

const isPersistedContentNode = (element: HTMLElement): boolean => {
    return !element.classList.contains('inline-action-update') && !element.matches(COLLAPSIBLE_ACTIVITY_SELECTOR) && !element.classList.contains('inline-activity-type-loading');
};

const resolveFirstPersistedContentNode = (element: HTMLElement): HTMLElement | null => {
    const collapsedContent = dom.resolve(COLLAPSED_LOADING_CONTENT_SELECTOR, element);
    if (collapsedContent instanceof HTMLElement) {
        return collapsedContent;
    }
    const responseRoot = dom.resolve(MESSAGE_RESPONSE_SELECTOR, element);
    if (!(responseRoot instanceof HTMLElement)) {
        return null;
    }
    for (const child of Array.from(responseRoot.children)) {
        if (child instanceof HTMLElement && isPersistedContentNode(child)) {
            return child;
        }
    }
    return null;
};

const resolvePersistedContentMotionSnapshot = (element: HTMLElement): GeometryBox | null => {
    const content = resolveFirstPersistedContentNode(element);
    return content instanceof HTMLElement ? measureLayoutBox(content) : null;
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

const resolveLoadingHeader = (element: HTMLElement): HTMLElement | null => {
    const header = dom.resolve(LOADING_HEADER_SELECTOR, element);
    return header instanceof HTMLElement ? header : null;
};

const resolveHoveredLoadingHeaderState = (element: HTMLElement): boolean => {
    const header = resolveLoadingHeader(element);
    return header instanceof HTMLElement && header.matches(':hover');
};

const preserveLoadingHeaderHoverState = (element: HTMLElement, hovered: boolean, documentRef: Document, messageId: string, sequence: number): void => {
    if (!hovered) {
        return;
    }
    const header = resolveLoadingHeader(element);
    if (!(header instanceof HTMLElement)) {
        return;
    }
    header.setAttribute(TOGGLE_HOVER_ATTRIBUTE, 'true');
    const clear = (): void => {
        if (!isLatestLoadingActivityToggleSequence(documentRef, messageId, sequence)) {
            return;
        }
        header.removeAttribute(TOGGLE_HOVER_ATTRIBUTE);
    };
    const view = element.ownerDocument.defaultView;
    if (view && typeof view.setTimeout === 'function') {
        view.setTimeout(clear, resolveLoadingActivityToggleFallbackDurationMs(element));
        return;
    }
    clear();
};

const animateCollapseNodes = async (element: HTMLElement, documentRef: Document, messageId: string, sequence: number, animationState: LoadingActivityAnimationState): Promise<void> => {
    if (prefersReducedMotion(element)) {
        return;
    }
    const animatedNodes = resolveAnimatedActivityNodes(element);
    if (animatedNodes.length === 0) {
        return;
    }
    for (const animatedNode of animatedNodes) {
        const animation = runNodeAnimation(animatedNode, [
            { opacity: 1, transform: 'translateY(0)' },
            { opacity: 0, transform: 'translateY(-8px)' }
        ]);
        if (animation) {
            recordLoadingActivityAnimation(documentRef, messageId, sequence, animation);
            animationState.animations.push(animation);
        }
    }
    await waitForDuration(element, resolveLoadingActivityToggleDurationMs(element));
    scheduleLoadingActivityAnimationCleanup(documentRef, messageId, sequence, element.ownerDocument.defaultView, resolveLoadingActivityToggleFallbackDurationMs(element));
};

const animateExpandedNodes = (element: HTMLElement, documentRef: Document, messageId: string, sequence: number, animationState: LoadingActivityAnimationState): void => {
    for (const animatedNode of resolveAnimatedActivityNodes(element)) {
        const animation = runNodeAnimation(animatedNode, [
            { opacity: 0, transform: 'translateY(-8px)' },
            { opacity: 1, transform: 'translateY(0)' }
        ]);
        if (animation) {
            recordLoadingActivityAnimation(documentRef, messageId, sequence, animation);
            animationState.animations.push(animation);
        }
    }
    scheduleLoadingActivityAnimationCleanup(documentRef, messageId, sequence, element.ownerDocument.defaultView, resolveLoadingActivityToggleFallbackDurationMs(element));
};

const animatePersistedContentNode = (element: HTMLElement, documentRef: Document, messageId: string, sequence: number, previousRect: GeometryBox | null, animationState: LoadingActivityAnimationState): boolean => {
    if (previousRect === null) {
        return false;
    }
    const content = resolveFirstPersistedContentNode(element);
    if (!(content instanceof HTMLElement)) {
        return false;
    }
    const nextRect = measureLayoutBox(content);
    const deltaY = previousRect.top - nextRect.top;
    if (Math.abs(deltaY) < 1) {
        return false;
    }
    const animation = runNodeAnimation(content, [{ transform: `translateY(${deltaY}px)` }, { transform: 'translateY(0)' }]);
    if (!animation) {
        return false;
    }
    recordLoadingActivityAnimation(documentRef, messageId, sequence, animation);
    animationState.animations.push(animation);
    return true;
};

const animateMessageTextTransition = (element: HTMLElement, documentRef: Document, messageId: string, sequence: number, startHeight: number, collapsed: boolean, animationState: LoadingActivityAnimationState, persistedContentRect: GeometryBox | null): void => {
    cancelLoadingActivityTransition(element);
    if (prefersReducedMotion(element)) {
        cleanupAnimatedStyles(element);
        clearLoadingActivityAnimations(documentRef, messageId, sequence);
        return;
    }
    const endHeight = element.scrollHeight;
    const delta = Math.abs(endHeight - startHeight);
    const animatedNodes = collapsed ? [] : resolveAnimatedActivityNodes(element);
    const contentAnimated = animatePersistedContentNode(element, documentRef, messageId, sequence, persistedContentRect, animationState);
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
        element.style.setProperty('height', `${Math.max(endHeight, 0)}px`);
    });
    if (!collapsed) {
        animateExpandedNodes(element, documentRef, messageId, sequence, animationState);
    }
};

export { animateCollapseNodes, animateMessageTextTransition, preserveLoadingHeaderHoverState, resolveHoveredLoadingHeaderState, resolveLoadingActivityToggleFallbackDurationMs, resolvePersistedContentMotionSnapshot };
