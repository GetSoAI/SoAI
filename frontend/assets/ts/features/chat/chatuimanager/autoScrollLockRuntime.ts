/* SoAI - Chat feature auto scroll lock runtime [frontend/assets/ts/features/chat/chatuimanager/autoScrollLockRuntime.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isNamedFormField } from '@core/dom/formFields.ts';
import { measureViewportTouchPoint } from '@core/layout/elementGeometry.ts';
import { CHAT_SELECTORS } from '@features/chat/chatConstants.ts';
import type { ChatUIManagerContext } from '@features/chat/chatuimanager/types.ts';
import { acquireMainTimelineCoordinator } from '@features/chat/mainTimelineCoordinator.ts';
import { MAIN_TIMELINE_AUTO_SCROLL_LOCK_ATTRIBUTE } from '@features/chat/mainTimelineScroll.ts';

const USER_SCROLL_KEYS: ReadonlySet<string> = new Set<string>(['ArrowDown', 'ArrowUp', 'End', 'Home', 'PageDown', 'PageUp', ' ']);
const USER_SCROLL_LOCK_RELEASE_KEYS: ReadonlySet<string> = new Set<string>(['ArrowUp', 'Home', 'PageUp']);
const SCROLL_RELEVANT_TRANSITION_PROPERTIES: ReadonlySet<string> = new Set<string>(['all', 'height', 'margin', 'margin-bottom', 'margin-top', 'max-height', 'min-height', 'padding', 'padding-bottom', 'padding-top', 'transform']);

const markUserScrollIntent = (context: ChatUIManagerContext): void => {
    context.state.autoScrollUserIntentActive = true;
};

const releaseAutoScrollLockFromUserIntent = (context: ChatUIManagerContext, messagesArea: HTMLElement): void => {
    markUserScrollIntent(context);
    if (!context.state.autoScrollEnabled) {
        return;
    }
    context.state.autoScrollEnabled = false;
    syncAutoScrollLockAttribute(context, messagesArea);
};

const isEditableKeyTarget = (target: EventTarget | null): boolean => {
    if (!(target instanceof Element)) {
        return false;
    }
    if (isNamedFormField(target)) {
        return true;
    }
    return target.closest('[contenteditable]') !== null;
};

const isMainTimelineUserScrollIntent = (event: Event, messagesArea: HTMLElement): boolean => {
    if (event.type === 'wheel' || event.type === 'touchstart') return true;
    if (event.type === 'pointerdown') return event.target === messagesArea;
    return event instanceof KeyboardEvent && USER_SCROLL_KEYS.has(event.key) && !isEditableKeyTarget(event.target);
};

const handleScrollIntentKey = (context: ChatUIManagerContext, messagesArea: HTMLElement, event: Event): void => {
    if (!(event instanceof KeyboardEvent) || !USER_SCROLL_KEYS.has(event.key) || isEditableKeyTarget(event.target)) {
        return;
    }
    markUserScrollIntent(context);
    if (USER_SCROLL_LOCK_RELEASE_KEYS.has(event.key) || (event.key === ' ' && event.shiftKey)) {
        releaseAutoScrollLockFromUserIntent(context, messagesArea);
    }
};

const handleScrollbarPointerIntent = (context: ChatUIManagerContext, messagesArea: HTMLElement, event: Event): void => {
    if (event instanceof PointerEvent && event.target === messagesArea) {
        releaseAutoScrollLockFromUserIntent(context, messagesArea);
    }
};

const handleWheelIntent = (context: ChatUIManagerContext, messagesArea: HTMLElement, event: Event): void => {
    if (!(event instanceof WheelEvent)) {
        markUserScrollIntent(context);
        return;
    }
    if (event.deltaY < 0) {
        releaseAutoScrollLockFromUserIntent(context, messagesArea);
        return;
    }
    markUserScrollIntent(context);
};

const disposeAutoScrollIntentListeners = (context: ChatUIManagerContext): void => {
    for (const dispose of context.state.autoScrollIntentDisposers) {
        dispose();
    }
    context.state.autoScrollIntentDisposers = [];
    context.state.autoScrollUserIntentActive = false;
};

const setupAutoScrollIntentListeners = (context: ChatUIManagerContext, messagesArea: HTMLElement): void => {
    disposeAutoScrollIntentListeners(context);
    const documentRef = context.dependencies.dom.getDocument();
    let lastTouchClientY: number | null = null;
    const handleTouchStart = (event: Event): void => {
        if (!(event instanceof TouchEvent) || event.touches.length === 0) {
            lastTouchClientY = null;
            markUserScrollIntent(context);
            return;
        }
        const firstTouch = event.touches[0] ?? null;
        lastTouchClientY = firstTouch ? measureViewportTouchPoint(firstTouch).y : null;
        markUserScrollIntent(context);
    };
    const handleTouchMove = (event: Event): void => {
        if (!(event instanceof TouchEvent) || event.touches.length === 0) {
            markUserScrollIntent(context);
            return;
        }
        const firstTouch = event.touches[0] ?? null;
        const touchClientY = firstTouch ? measureViewportTouchPoint(firstTouch).y : null;
        if (lastTouchClientY !== null && touchClientY !== null && touchClientY > lastTouchClientY) {
            releaseAutoScrollLockFromUserIntent(context, messagesArea);
        } else {
            markUserScrollIntent(context);
        }
        lastTouchClientY = touchClientY;
    };
    context.state.autoScrollIntentDisposers = [context.dependencies.runtime.on(messagesArea, 'wheel', (event) => handleWheelIntent(context, messagesArea, event), { passive: true }), context.dependencies.runtime.on(messagesArea, 'touchstart', handleTouchStart, { passive: true }), context.dependencies.runtime.on(messagesArea, 'touchmove', handleTouchMove, { passive: true }), context.dependencies.runtime.on(messagesArea, 'pointerdown', (event) => handleScrollbarPointerIntent(context, messagesArea, event), { passive: true }), context.dependencies.runtime.on(documentRef, 'keydown', (event) => handleScrollIntentKey(context, messagesArea, event), { passive: true })];
};

const disposeAutoScrollLockObserver = (context: ChatUIManagerContext): void => {
    context.state.messagesAutoScrollLockDisposer?.();
    context.state.messagesAutoScrollLockDisposer = null;
    context.state.messagesAutoScrollLockArea = null;
};

const disposeAutoScrollLockRuntime = (context: ChatUIManagerContext): void => {
    disposeAutoScrollLockObserver(context);
    disposeAutoScrollIntentListeners(context);
};

const syncAutoScrollLockAttribute = (context: ChatUIManagerContext, messagesArea: HTMLElement | null): void => {
    if (messagesArea instanceof HTMLElement) {
        context.dependencies.updateAttribute(messagesArea, MAIN_TIMELINE_AUTO_SCROLL_LOCK_ATTRIBUTE, context.state.autoScrollEnabled ? 'true' : null);
    }
};

const isScrollRelevantTransitionProperty = (propertyName: string): boolean => SCROLL_RELEVANT_TRANSITION_PROPERTIES.has(propertyName.trim());

const setupAutoScrollLockRuntime = (context: ChatUIManagerContext, messagesArea: HTMLElement, messagesRoot: HTMLElement, scrollToBottom: () => void): void => {
    if (context.state.messagesAutoScrollLockDisposer && context.state.messagesAutoScrollLockArea === messagesArea && messagesArea.isConnected) {
        return;
    }
    disposeAutoScrollLockRuntime(context);
    const messagesContainer = context.dependencies.optionalUI(CHAT_SELECTORS.MESSAGES_CONTAINER);
    if (!(messagesContainer instanceof HTMLElement)) {
        throw new Error('Chat messages container is required for auto-scroll lock');
    }
    const coordinator = acquireMainTimelineCoordinator(messagesArea, messagesRoot);
    const activeTransitionPropertiesByElement = new Map<Element, Set<string>>();
    const pruneInactiveTransitions = (): void => {
        for (const [element, properties] of activeTransitionPropertiesByElement.entries()) {
            if (!element.isConnected || properties.size === 0) {
                activeTransitionPropertiesByElement.delete(element);
            }
        }
    };
    const hasActiveTransition = (): boolean => {
        pruneInactiveTransitions();
        return activeTransitionPropertiesByElement.size > 0;
    };
    const clearTransitionProperty = (event: Event): void => {
        if (!(event instanceof TransitionEvent) || !(event.target instanceof Element)) {
            return;
        }
        const properties = activeTransitionPropertiesByElement.get(event.target) ?? null;
        if (properties === null) {
            return;
        }
        properties.delete(event.propertyName);
        if (properties.size === 0) {
            activeTransitionPropertiesByElement.delete(event.target);
        }
    };
    const syncLockedScrollPosition = (): void => {
        if (!context.state.autoScrollEnabled || !messagesArea.isConnected) {
            return;
        }
        scrollToBottom();
    };
    const scheduleLockedScrollPositionSync = (): void => {
        coordinator.scheduleFrame('auto-scroll-lock', () => {
            if (!context.state.autoScrollEnabled || !messagesArea.isConnected) {
                return null;
            }
            return () => {
                syncLockedScrollPosition();
                if (context.state.autoScrollEnabled && hasActiveTransition()) {
                    scheduleLockedScrollPositionSync();
                }
            };
        });
    };
    const recordTransitionProperty = (event: Event): void => {
        if (!(event instanceof TransitionEvent) || !(event.target instanceof Element)) {
            return;
        }
        if (!isScrollRelevantTransitionProperty(event.propertyName)) {
            return;
        }
        const existing = activeTransitionPropertiesByElement.get(event.target) ?? new Set<string>();
        existing.add(event.propertyName);
        activeTransitionPropertiesByElement.set(event.target, existing);
        if (context.state.autoScrollEnabled) {
            scheduleLockedScrollPositionSync();
        }
    };
    const resizeDisposer = coordinator.subscribeResize(() => {
        if (context.state.autoScrollEnabled) {
            scheduleLockedScrollPositionSync();
        }
    });
    const messagesAreaResizeDisposer = coordinator.observeResize(messagesArea);
    const messagesResizeDisposer = coordinator.observeResize(messagesContainer);
    const mutationDisposer = coordinator.subscribeMutations(() => {
        if (context.state.autoScrollEnabled) {
            scheduleLockedScrollPositionSync();
        }
    });
    const transitionRunDisposer = context.dependencies.runtime.on(messagesContainer, 'transitionrun', recordTransitionProperty);
    const transitionStartDisposer = context.dependencies.runtime.on(messagesContainer, 'transitionstart', recordTransitionProperty);
    const transitionEndDisposer = context.dependencies.runtime.on(messagesContainer, 'transitionend', clearTransitionProperty);
    const transitionCancelDisposer = context.dependencies.runtime.on(messagesContainer, 'transitioncancel', clearTransitionProperty);
    context.state.messagesAutoScrollLockDisposer = () => {
        transitionRunDisposer();
        transitionStartDisposer();
        transitionEndDisposer();
        transitionCancelDisposer();
        mutationDisposer();
        messagesResizeDisposer();
        messagesAreaResizeDisposer();
        resizeDisposer();
        activeTransitionPropertiesByElement.clear();
        coordinator.cancelFrame('auto-scroll-lock');
        coordinator.release();
    };
    context.state.messagesAutoScrollLockArea = messagesArea;
    setupAutoScrollIntentListeners(context, messagesArea);
};

const syncAutoScrollStateFromScroll = (context: ChatUIManagerContext, messagesArea: HTMLElement, atBottom: boolean, restoreLockedScrollPosition: () => void): void => {
    if (atBottom) {
        context.state.autoScrollEnabled = true;
    } else if (context.state.autoScrollUserIntentActive) {
        context.state.autoScrollEnabled = false;
    } else if (context.state.autoScrollEnabled) {
        restoreLockedScrollPosition();
    }
    context.state.autoScrollUserIntentActive = false;
    syncAutoScrollLockAttribute(context, messagesArea);
};

export { disposeAutoScrollLockRuntime, isMainTimelineUserScrollIntent, setupAutoScrollLockRuntime, syncAutoScrollLockAttribute, syncAutoScrollStateFromScroll };
