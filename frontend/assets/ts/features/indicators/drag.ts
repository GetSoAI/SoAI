/* SoAI - Indicators feature drag [frontend/assets/ts/features/indicators/drag.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { measureLayoutBox, measureLayoutPoint, measureLayoutViewport } from '@core/layout/elementGeometry.ts';
import { INTERFACE_SCALE_CHANGED_EVENT } from '@core/layout/interfaceScale.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { clampNumber } from '@core/primitives/clampNumber.ts';
import { ResourceTracker } from '@core/resourcetracker/service.ts';
import { isLiveStatusOverlayGenerationCurrent } from '@features/indicators/state.ts';
import type { LiveStatusOverlayDragState, LiveStatusOverlayState } from '@features/indicators/types.ts';

const requireLiveStatusOverlayWindow = (container: HTMLElement): Window => {
    const windowRef = container.ownerDocument.defaultView;
    if (!windowRef) {
        throw new Error('Live status overlay drag requires a document window');
    }
    return windowRef;
};

const applyLiveStatusOverlayPosition = (state: LiveStatusOverlayState, left: number, top: number): void => {
    const container = state.container;
    if (!container) {
        return;
    }

    const bounds = measureLayoutBox(container);
    const viewport = measureLayoutViewport(container);
    const maxLeft = Math.max(0, viewport.width - bounds.width);
    const maxTop = Math.max(0, viewport.height - bounds.height);
    const position = {
        left: clampNumber(left, 0, maxLeft),
        top: clampNumber(top, 0, maxTop)
    };
    state.position = position;
    container.style.setProperty('left', `${position.left}px`);
    container.style.setProperty('top', `${position.top}px`);
    container.style.setProperty('right', 'auto');
    container.style.setProperty('bottom', 'auto');
};

const applyStoredLiveStatusOverlayPosition = (state: LiveStatusOverlayState): void => {
    if (!state.position) {
        return;
    }
    applyLiveStatusOverlayPosition(state, state.position.left, state.position.top);
};

const clearLiveStatusOverlayDrag = (state: LiveStatusOverlayState): void => {
    const dragState = state.dragState;
    if (!dragState) {
        return;
    }
    dragState.disposers.forEach((dispose) => dispose());
    state.dragState = null;
    state.container?.classList.remove('is-dragging');
};

const handleLiveStatusOverlayPointerMove = (state: LiveStatusOverlayState, event: Event): void => {
    if (!(event instanceof PointerEvent) || !state.dragState || event.pointerId !== state.dragState.pointerId) {
        return;
    }
    const container = state.container;
    if (!container) {
        clearLiveStatusOverlayDrag(state);
        return;
    }
    const point = measureLayoutPoint(event, container);
    applyLiveStatusOverlayPosition(state, point.x - state.dragState.offsetX, point.y - state.dragState.offsetY);
    if (event.cancelable) {
        event.preventDefault();
    }
};

const handleLiveStatusOverlayPointerEnd = (state: LiveStatusOverlayState, event: Event): void => {
    if (!(event instanceof PointerEvent) || !state.dragState || event.pointerId !== state.dragState.pointerId) {
        return;
    }
    if (event.cancelable) {
        event.preventDefault();
    }
    clearLiveStatusOverlayDrag(state);
};

const captureLiveStatusOverlayPointer = (container: HTMLElement, pointerId: number): void => {
    if (typeof container.setPointerCapture !== 'function') {
        return;
    }
    try {
        container.setPointerCapture(pointerId);
    } catch (error) {
        errorHandler.debug('LiveStatusOverlay', 'Pointer capture failed; continuing with window tracking', ensureError(error));
    }
};

const startLiveStatusOverlayDrag = (state: LiveStatusOverlayState, timers: ResourceTracker, event: Event): void => {
    if (!(event instanceof PointerEvent) || !event.isPrimary || state.dragState) {
        return;
    }
    if (event.pointerType === 'mouse' && event.button !== 0) {
        return;
    }

    const container = state.container;
    if (!container) {
        return;
    }
    const bounds = measureLayoutBox(container);
    const point = measureLayoutPoint(event, container);
    const left = state.position?.left ?? bounds.left;
    const top = state.position?.top ?? bounds.top;
    applyLiveStatusOverlayPosition(state, left, top);
    if (!state.position) {
        return;
    }

    const dragState: LiveStatusOverlayDragState = {
        pointerId: event.pointerId,
        offsetX: point.x - state.position.left,
        offsetY: point.y - state.position.top,
        disposers: []
    };
    state.dragState = dragState;
    container.classList.add('is-dragging');
    captureLiveStatusOverlayPointer(container, event.pointerId);

    const windowRef = requireLiveStatusOverlayWindow(container);
    dragState.disposers.push(timers.addEventListener(windowRef, 'pointermove', (moveEvent: Event): void => handleLiveStatusOverlayPointerMove(state, moveEvent), { passive: false }));
    dragState.disposers.push(timers.addEventListener(windowRef, 'pointerup', (upEvent: Event): void => handleLiveStatusOverlayPointerEnd(state, upEvent)));
    dragState.disposers.push(timers.addEventListener(windowRef, 'pointercancel', (): void => clearLiveStatusOverlayDrag(state)));
    if (event.cancelable) {
        event.preventDefault();
    }
};

const attachLiveStatusOverlayDrag = (state: LiveStatusOverlayState, timers: ResourceTracker, generation: number): void => {
    const container = state.container;
    if (!container) {
        return;
    }
    const windowRef = requireLiveStatusOverlayWindow(container);

    const pointerDownDisposer = timers.addEventListener(
        container,
        'pointerdown',
        (event: Event): void => {
            if (isLiveStatusOverlayGenerationCurrent(state, generation)) {
                startLiveStatusOverlayDrag(state, timers, event);
            }
        },
        { passive: false }
    );
    const applyPositionAfterViewportChange = (): void => {
        if (isLiveStatusOverlayGenerationCurrent(state, generation) && !state.dragState) {
            applyStoredLiveStatusOverlayPosition(state);
        }
    };
    const resizeDisposer = timers.addEventListener(windowRef, 'resize', applyPositionAfterViewportChange);
    const scaleDisposer = timers.addEventListener(windowRef, INTERFACE_SCALE_CHANGED_EVENT, applyPositionAfterViewportChange);
    state.unsubscribers.push((): void => {
        clearLiveStatusOverlayDrag(state);
        pointerDownDisposer();
        resizeDisposer();
        scaleDisposer();
    });
};

export { applyStoredLiveStatusOverlayPosition, applyLiveStatusOverlayPosition, attachLiveStatusOverlayDrag };
