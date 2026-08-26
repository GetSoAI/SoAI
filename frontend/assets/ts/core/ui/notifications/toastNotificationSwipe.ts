/* SoAI - Shared UI toast notification swipe [frontend/assets/ts/core/ui/notifications/toastNotificationSwipe.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { NOTIFICATION_DISMISS_FADE_MS } from '@core/ui/notifications/constants.ts';
import { isNotificationPointerEventForGesture, isSupportedNotificationPointerStart } from '@core/ui/notifications/toastNotificationPointerEvents.ts';
import { findTouchByIdentifier, preventCancelableEventDefault } from '@core/ui/notifications/toastNotificationTouchEvents.ts';
import type { ToastNotificationGestureStart, ToastNotificationGestureState, ToastNotificationSwipeOptions } from '@core/ui/notifications/types.ts';
import { measureLayoutPoint, measureLayoutTouchPoint } from '@core/layout/elementGeometry.ts';

const NOTIFICATION_SWIPE_MIN_DRAG_PX = 8;
const NOTIFICATION_SWIPE_MIN_DISMISS_PX = 96;
const NOTIFICATION_SWIPE_WIDTH_RATIO = 0.35;

const resolveSwipeThreshold = (notification: HTMLElement): number => Math.max(NOTIFICATION_SWIPE_MIN_DISMISS_PX, notification.clientWidth * NOTIFICATION_SWIPE_WIDTH_RATIO);

const resolveSwipeOpacity = (notification: HTMLElement, deltaX: number): string => {
    const width = Math.max(notification.clientWidth, NOTIFICATION_SWIPE_MIN_DISMISS_PX);
    return Math.max(0.35, 1 - deltaX / width).toFixed(2);
};

const setSwipeOffset = (notification: HTMLElement, deltaX: number): void => {
    notification.style.setProperty('--ui-notification-swipe-x', `${deltaX}px`);
    notification.style.setProperty('--ui-notification-swipe-opacity', resolveSwipeOpacity(notification, deltaX));
};

const clearSwipeOffset = (notification: HTMLElement): void => {
    notification.style.removeProperty('--ui-notification-swipe-x');
    notification.style.removeProperty('--ui-notification-swipe-opacity');
};

const bindToastNotificationSwipeDismissal = (options: ToastNotificationSwipeOptions): void => {
    const { notification, lifecycle } = options;
    let gestureState: ToastNotificationGestureState | null = null;
    let gestureAbortController: AbortController | null = null;

    const shouldTrackMovement = (state: ToastNotificationGestureState, deltaX: number, deltaY: number): boolean => {
        if (deltaX <= 0 || deltaX < deltaY) {
            return false;
        }
        if (state.pointerType === 'touch' || state.pointerType === 'pen') {
            return true;
        }
        return deltaX >= NOTIFICATION_SWIPE_MIN_DRAG_PX;
    };

    const restoreSwipeState = (): void => {
        dom.removeClass(notification, ['ui-notification--swipe-active', 'ui-notification--swipe-dragging']);
        clearSwipeOffset(notification);
    };

    const dismissBySwipe = (deltaX: number): void => {
        lifecycle.pauseAutoDismiss();
        dom.removeClass(notification, 'ui-notification--swipe-dragging');
        dom.addClass(notification, 'ui-notification--swipe-dismissed');
        setSwipeOffset(notification, Math.max(deltaX, resolveSwipeThreshold(notification)));
        setTimeout(lifecycle.dismiss, NOTIFICATION_DISMISS_FADE_MS);
    };

    const stopGestureListeners = (): void => {
        gestureAbortController?.abort();
        gestureAbortController = null;
    };

    const clearGestureTransport = (state: ToastNotificationGestureState): void => {
        if (notification.hasPointerCapture(state.pointerId)) {
            notification.releasePointerCapture(state.pointerId);
        }
        stopGestureListeners();
    };

    const updateGesture = (state: ToastNotificationGestureState, clientX: number, clientY: number): boolean => {
        state.currentX = clientX;
        state.currentY = clientY;
        const deltaX = Math.max(0, state.currentX - state.startX);
        const deltaY = Math.abs(state.currentY - state.startY);
        if (!shouldTrackMovement(state, deltaX, deltaY)) {
            return false;
        }
        state.dragging = true;
        dom.addClass(notification, 'ui-notification--swipe-dragging');
        setSwipeOffset(notification, deltaX);
        return true;
    };

    const completeGesture = (state: ToastNotificationGestureState): void => {
        const deltaX = Math.max(0, state.currentX - state.startX);
        const deltaY = Math.abs(state.currentY - state.startY);
        const shouldDismiss = state.dragging && deltaX >= resolveSwipeThreshold(notification) && deltaX >= deltaY;
        gestureState = null;
        clearGestureTransport(state);
        if (shouldDismiss) {
            options.suppressUpcomingClick();
            dismissBySwipe(deltaX);
            return;
        }
        if (state.dragging) {
            options.suppressUpcomingClick();
        }
        restoreSwipeState();
        if (!options.isExpanded()) {
            lifecycle.resumeAutoDismiss();
        }
    };

    const cancelGesture = (state: ToastNotificationGestureState): void => {
        gestureState = null;
        clearGestureTransport(state);
        if (state.dragging) {
            options.suppressUpcomingClick();
        }
        restoreSwipeState();
        if (!options.isExpanded()) {
            lifecycle.resumeAutoDismiss();
        }
    };

    const handlePointerMove = (event: PointerEvent): void => {
        const state = gestureState;
        if (!state || !isNotificationPointerEventForGesture(event, state.source, state.pointerId)) {
            return;
        }
        const point = measureLayoutPoint(event, notification);
        if (updateGesture(state, point.x, point.y)) {
            event.preventDefault();
        }
    };

    const completePointerGesture = (event: PointerEvent): void => {
        const state = gestureState;
        if (!state || !isNotificationPointerEventForGesture(event, state.source, state.pointerId)) {
            return;
        }
        completeGesture(state);
    };

    const cancelPointerGesture = (event: PointerEvent): void => {
        const state = gestureState;
        if (!state || !isNotificationPointerEventForGesture(event, state.source, state.pointerId)) {
            return;
        }
        cancelGesture(state);
    };

    const handleLostPointerCapture = (event: PointerEvent): void => {
        const state = gestureState;
        if (!state || state.source !== 'pointer' || state.pointerId !== event.pointerId) {
            return;
        }
        cancelGesture(state);
    };

    const handleTouchMove = (event: TouchEvent): void => {
        const state = gestureState;
        if (!state || state.source !== 'touch' || state.touchIdentifier === null) {
            return;
        }
        const touch = findTouchByIdentifier(event.changedTouches, state.touchIdentifier) ?? findTouchByIdentifier(event.touches, state.touchIdentifier);
        if (!touch) {
            return;
        }
        const point = measureLayoutTouchPoint(touch, notification);
        if (updateGesture(state, point.x, point.y)) {
            preventCancelableEventDefault(event);
        }
    };

    const completeTouchGesture = (event: TouchEvent): void => {
        const state = gestureState;
        if (!state || state.source !== 'touch' || state.touchIdentifier === null || !findTouchByIdentifier(event.changedTouches, state.touchIdentifier)) {
            return;
        }
        completeGesture(state);
    };

    const cancelTouchGesture = (event: TouchEvent): void => {
        const state = gestureState;
        if (!state || state.source !== 'touch' || state.touchIdentifier === null || !findTouchByIdentifier(event.changedTouches, state.touchIdentifier)) {
            return;
        }
        cancelGesture(state);
    };

    const startPointerGestureListeners = (): void => {
        stopGestureListeners();
        gestureAbortController = new AbortController();
        const documentRef = dom.getDocument();
        documentRef.addEventListener('pointermove', handlePointerMove, { signal: gestureAbortController.signal, passive: false });
        documentRef.addEventListener('pointerup', completePointerGesture, { signal: gestureAbortController.signal });
        documentRef.addEventListener('pointercancel', cancelPointerGesture, { signal: gestureAbortController.signal });
    };

    const startTouchGestureListeners = (): void => {
        stopGestureListeners();
        gestureAbortController = new AbortController();
        const documentRef = dom.getDocument();
        documentRef.addEventListener('touchmove', handleTouchMove, { signal: gestureAbortController.signal, passive: false });
        documentRef.addEventListener('touchend', completeTouchGesture, { signal: gestureAbortController.signal });
        documentRef.addEventListener('touchcancel', cancelTouchGesture, { signal: gestureAbortController.signal });
    };

    const startGesture = (start: ToastNotificationGestureStart): void => {
        gestureState = {
            source: start.source,
            pointerId: start.pointerId,
            touchIdentifier: start.touchIdentifier,
            pointerType: start.pointerType,
            startX: start.clientX,
            startY: start.clientY,
            currentX: start.clientX,
            currentY: start.clientY,
            dragging: false
        };
        lifecycle.pauseAutoDismiss();
        dom.addClass(notification, 'ui-notification--swipe-active');
        if (start.source === 'pointer') {
            startPointerGestureListeners();
            notification.setPointerCapture(start.pointerId);
            return;
        }
        startTouchGestureListeners();
    };

    const handlePointerDown = (event: PointerEvent): void => {
        if (gestureState || !isSupportedNotificationPointerStart(event) || options.isBlockedTarget(event.target)) {
            return;
        }
        const point = measureLayoutPoint(event, notification);
        startGesture({
            source: 'pointer',
            pointerId: event.pointerId,
            touchIdentifier: null,
            pointerType: event.pointerType,
            clientX: point.x,
            clientY: point.y
        });
    };

    const handleTouchStart = (event: TouchEvent): void => {
        if (options.isBlockedTarget(event.target)) {
            return;
        }
        const touch = event.changedTouches.item(0);
        if (!touch) {
            return;
        }
        const existingState = gestureState;
        if (existingState) {
            if (existingState.dragging) {
                return;
            }
            gestureState = null;
            clearGestureTransport(existingState);
        }
        const point = measureLayoutTouchPoint(touch, notification);
        startGesture({
            source: 'touch',
            pointerId: existingState?.pointerId ?? touch.identifier,
            touchIdentifier: touch.identifier,
            pointerType: 'touch',
            clientX: point.x,
            clientY: point.y
        });
    };

    notification.addEventListener('pointerdown', handlePointerDown);
    notification.addEventListener('lostpointercapture', handleLostPointerCapture);
    notification.addEventListener('touchstart', handleTouchStart, { passive: false });
};

export { bindToastNotificationSwipeDismissal };
