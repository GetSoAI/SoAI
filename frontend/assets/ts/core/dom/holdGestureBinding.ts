/* SoAI - Shared delegated pointer hold gesture binding [frontend/assets/ts/core/dom/holdGestureBinding.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { bindEventGroup } from '@core/dom/eventBindingGroup.ts';
import { resolveDataActionElement } from '@core/dom/dataAction.ts';
import { measureLayoutPoint, type GeometryPoint } from '@core/layout/elementGeometry.ts';

const DEFAULT_HOLD_THRESHOLD_MS = 500;
const DEFAULT_MOVEMENT_TOLERANCE_PX = 10;
const COMPATIBILITY_CLICK_DEADLINE_MS = 1_000;

type HoldGestureCancelReason = 'capture-lost' | 'disposed' | 'escape' | 'ineligible' | 'pointer-cancel' | 'visibility';

interface HoldGesturePointerContext<TAction extends string> {
    action: TAction;
    actionElement: HTMLElement;
    pointerId: number;
    pointerType: string;
    start: GeometryPoint;
    current: GeometryPoint;
}

interface ActiveHoldGesture<TAction extends string> {
    move?(context: HoldGesturePointerContext<TAction>): void;
    release?(context: HoldGesturePointerContext<TAction>): void;
    cancel?(reason: HoldGestureCancelReason, context: HoldGesturePointerContext<TAction>): void;
}

interface HoldGestureAction<TAction extends string> {
    isEligible(): boolean;
    activate(context: HoldGesturePointerContext<TAction>): ActiveHoldGesture<TAction> | null;
}

interface HoldGestureBindingOptions<TAction extends string> {
    root: HTMLElement;
    signal: AbortSignal;
    isAction(value: string | undefined): value is TAction;
    resolveAction(action: TAction, actionElement: HTMLElement): HoldGestureAction<TAction> | null;
    thresholdMs?: number;
    movementTolerancePx?: number;
}

interface PendingHoldGesture<TAction extends string> {
    action: TAction;
    actionElement: HTMLElement;
    pointerId: number;
    pointerType: string;
    start: GeometryPoint;
    current: GeometryPoint;
    thresholdTimer: number;
    activated: ActiveHoldGesture<TAction> | null;
    movementCancelled: boolean;
}

const isPrimaryHoldPointer = (event: PointerEvent): boolean => event.isPrimary && event.button === 0 && (event.pointerType === 'mouse' || event.pointerType === 'touch' || event.pointerType === 'pen');

const pointerDistance = (start: GeometryPoint, current: GeometryPoint): number => Math.hypot(current.x - start.x, current.y - start.y);

const bindHoldGesture = <TAction extends string>(options: HoldGestureBindingOptions<TAction>): (() => void) => {
    const documentRef = options.root.ownerDocument;
    const view = documentRef.defaultView;
    const thresholdMs = options.thresholdMs ?? DEFAULT_HOLD_THRESHOLD_MS;
    const movementTolerancePx = options.movementTolerancePx ?? DEFAULT_MOVEMENT_TOLERANCE_PX;
    let pending: PendingHoldGesture<TAction> | null = null;
    let suppressCompatibilityClickUntil = 0;
    let suppressionTimer: number | null = null;

    const clearSuppression = (): void => {
        suppressCompatibilityClickUntil = 0;
        if (suppressionTimer !== null) {
            view?.clearTimeout(suppressionTimer);
            suppressionTimer = null;
        }
    };

    const armCompatibilityClickSuppression = (): void => {
        clearSuppression();
        suppressCompatibilityClickUntil = performance.now() + COMPATIBILITY_CLICK_DEADLINE_MS;
        suppressionTimer = view?.setTimeout(clearSuppression, COMPATIBILITY_CLICK_DEADLINE_MS) ?? null;
    };

    const pointerContext = (gesture: PendingHoldGesture<TAction>): HoldGesturePointerContext<TAction> => ({
        action: gesture.action,
        actionElement: gesture.actionElement,
        pointerId: gesture.pointerId,
        pointerType: gesture.pointerType,
        start: gesture.start,
        current: gesture.current
    });

    const clearThresholdTimer = (gesture: PendingHoldGesture<TAction>): void => {
        if (gesture.thresholdTimer === 0) return;
        view?.clearTimeout(gesture.thresholdTimer);
        gesture.thresholdTimer = 0;
    };

    const releaseCapture = (gesture: PendingHoldGesture<TAction>): void => {
        if (!gesture.actionElement.hasPointerCapture?.(gesture.pointerId)) return;
        gesture.actionElement.releasePointerCapture(gesture.pointerId);
    };

    const finish = (gesture: PendingHoldGesture<TAction>, suppressClick: boolean): void => {
        clearThresholdTimer(gesture);
        if (pending === gesture) pending = null;
        releaseCapture(gesture);
        if (suppressClick) armCompatibilityClickSuppression();
    };

    const cancel = (reason: HoldGestureCancelReason): void => {
        const gesture = pending;
        if (gesture === null) return;
        gesture.activated?.cancel?.(reason, pointerContext(gesture));
        finish(gesture, true);
    };

    const activate = (gesture: PendingHoldGesture<TAction>): void => {
        if (pending !== gesture || gesture.movementCancelled || options.signal.aborted) return;
        gesture.thresholdTimer = 0;
        const connected = gesture.actionElement.isConnected && options.root.contains(gesture.actionElement);
        const currentAction = gesture.actionElement.dataset.action;
        const resolvedAction = options.isAction(currentAction) && currentAction === gesture.action ? options.resolveAction(gesture.action, gesture.actionElement) : null;
        if (!connected || documentRef.hidden || resolvedAction === null || !resolvedAction.isEligible()) {
            gesture.movementCancelled = true;
            armCompatibilityClickSuppression();
            return;
        }
        let activationCompleted = false;
        try {
            gesture.activated = resolvedAction.activate(pointerContext(gesture));
            activationCompleted = true;
        } finally {
            if (!activationCompleted) {
                gesture.movementCancelled = true;
                finish(gesture, true);
            }
        }
        if (gesture.activated === null) gesture.movementCancelled = true;
        armCompatibilityClickSuppression();
    };

    const handlePointerDown = (event: Event): void => {
        if (!(event instanceof PointerEvent) || !isPrimaryHoldPointer(event)) return;
        if (pending !== null) return;
        clearSuppression();
        const resolved = resolveDataActionElement(event.target, options.root, options.isAction);
        if (resolved === null) return;
        const actionBinding = options.resolveAction(resolved.action, resolved.actionElement);
        if (actionBinding === null || !actionBinding.isEligible()) return;
        const point = measureLayoutPoint(event, options.root);
        const gesture: PendingHoldGesture<TAction> = {
            action: resolved.action,
            actionElement: resolved.actionElement,
            pointerId: event.pointerId,
            pointerType: event.pointerType,
            start: point,
            current: point,
            thresholdTimer: 0,
            activated: null,
            movementCancelled: false
        };
        pending = gesture;
        gesture.thresholdTimer = view?.setTimeout(() => activate(gesture), thresholdMs) ?? 0;
        gesture.actionElement.setPointerCapture?.(event.pointerId);
    };

    const handlePointerMove = (event: Event): void => {
        const gesture = pending;
        if (!(event instanceof PointerEvent) || gesture === null || event.pointerId !== gesture.pointerId) return;
        gesture.current = measureLayoutPoint(event, options.root);
        if (gesture.activated !== null) {
            gesture.activated.move?.(pointerContext(gesture));
            return;
        }
        if (!gesture.movementCancelled && pointerDistance(gesture.start, gesture.current) > movementTolerancePx) {
            gesture.movementCancelled = true;
            clearThresholdTimer(gesture);
        }
    };

    const handlePointerUp = (event: Event): void => {
        const gesture = pending;
        if (!(event instanceof PointerEvent) || gesture === null || event.pointerId !== gesture.pointerId) return;
        gesture.current = measureLayoutPoint(event, options.root);
        gesture.activated?.move?.(pointerContext(gesture));
        gesture.activated?.release?.(pointerContext(gesture));
        finish(gesture, gesture.activated !== null || gesture.movementCancelled);
    };

    const handlePointerCancel = (event: Event): void => {
        if (!(event instanceof PointerEvent) || pending === null || event.pointerId !== pending.pointerId) return;
        cancel('pointer-cancel');
    };

    const handleLostPointerCapture = (event: Event): void => {
        if (!(event instanceof PointerEvent) || pending === null || event.pointerId !== pending.pointerId) return;
        cancel('capture-lost');
    };

    const handleKeydown = (event: Event): void => {
        if (event instanceof KeyboardEvent && event.key === 'Escape') cancel('escape');
    };

    const handleVisibilityChange = (): void => {
        if (documentRef.hidden) cancel('visibility');
    };

    const handleClickCapture = (event: Event): void => {
        if (!(event instanceof MouseEvent) || event.detail === 0 || performance.now() > suppressCompatibilityClickUntil) return;
        event.preventDefault();
        event.stopImmediatePropagation();
        clearSuppression();
    };

    const handleContextMenu = (event: Event): void => {
        if (pending === null || pending.pointerType === 'mouse') return;
        event.preventDefault();
    };

    const cleanupEvents = bindEventGroup(
        [
            { target: options.root, type: 'pointerdown', listener: handlePointerDown, options: { capture: true } },
            { target: documentRef, type: 'pointermove', listener: handlePointerMove, options: { capture: true, passive: true } },
            { target: documentRef, type: 'pointerup', listener: handlePointerUp, options: { capture: true } },
            { target: documentRef, type: 'pointercancel', listener: handlePointerCancel, options: { capture: true } },
            { target: options.root, type: 'lostpointercapture', listener: handleLostPointerCapture, options: { capture: true } },
            { target: documentRef, type: 'keydown', listener: handleKeydown, options: { capture: true } },
            { target: documentRef, type: 'visibilitychange', listener: handleVisibilityChange },
            { target: documentRef, type: 'click', listener: handleClickCapture, options: { capture: true } },
            { target: documentRef, type: 'contextmenu', listener: handleContextMenu, options: { capture: true } }
        ],
        options.signal
    );
    const dispose = (): void => {
        cancel('disposed');
        clearSuppression();
        cleanupEvents();
    };
    options.signal.addEventListener('abort', dispose, { once: true });
    return dispose;
};

export { DEFAULT_HOLD_THRESHOLD_MS, DEFAULT_MOVEMENT_TOLERANCE_PX, bindHoldGesture };
export type { ActiveHoldGesture, HoldGestureAction, HoldGestureBindingOptions, HoldGestureCancelReason, HoldGesturePointerContext };
