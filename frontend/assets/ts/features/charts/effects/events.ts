/* SoAI - Charts feature effects events [frontend/assets/ts/features/charts/effects/events.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { handlePointerCancel, handlePointerDown, handlePointerLeave, handlePointerMove, handlePointerUp, handleWheelThrottled } from '@features/charts/effects/actions.ts';
import { handleDoubleClickFromCoordinates } from '@features/charts/interaction/actions.ts';
import { handleKeyboardNavigation } from '@features/charts/interaction/keyboard.ts';
import type { ChartInteractionScene } from '@features/charts/interaction/chartInteractionScene.ts';
import { INTERFACE_SCALE_CHANGED_EVENT } from '@core/layout/interfaceScale.ts';
import { measureLayoutPoint } from '@core/layout/elementGeometry.ts';

const setupEventListeners = (chart: ChartInteractionScene, addEventListener: (target: EventTarget, event: string, handler: EventListener, options?: AddEventListenerOptions) => void): void => {
    const canvas = chart.surface.canvasLayers.interaction;
    if (!canvas) {
        throw new Error('Chart requires an interaction canvas to bind pointer events');
    }
    const interactionTarget = chart.surface.element ?? canvas;
    interactionTarget.tabIndex = 0;

    const add = (target: EventTarget, type: string, handler: EventListener, options?: AddEventListenerOptions): void => {
        addEventListener(target, type, handler, options);
    };

    const win = canvas.ownerDocument.defaultView;
    if (!win) {
        throw new Error('Chart requires a Window to bind resize events');
    }

    add(win, 'resize', (): void => {
        chart.surface.resize();
    });
    add(win, INTERFACE_SCALE_CHANGED_EVENT, (): void => {
        chart.surface.resize();
    });

    const passiveFalse = { passive: false };
    const onWheel = (event: Event): void => {
        if (!(event instanceof WheelEvent)) {
            throw new TypeError('Chart wheel listener requires a WheelEvent');
        }
        handleWheelThrottled(chart, event);
    };
    const onPointerDown = (event: Event): void => {
        if (!(event instanceof PointerEvent)) {
            throw new TypeError('Chart pointerdown listener requires a PointerEvent');
        }
        interactionTarget.focus();
        handlePointerDown(chart, event);
    };
    const onPointerMove = (event: Event): void => {
        if (!(event instanceof PointerEvent)) {
            throw new TypeError('Chart pointermove listener requires a PointerEvent');
        }
        handlePointerMove(chart, event);
    };
    const onPointerUp = (event: Event): void => {
        if (!(event instanceof PointerEvent)) {
            throw new TypeError('Chart pointerup listener requires a PointerEvent');
        }
        handlePointerUp(chart, event);
    };
    const onPointerCancel = (event: Event): void => {
        if (!(event instanceof PointerEvent)) {
            throw new TypeError('Chart pointercancel listener requires a PointerEvent');
        }
        handlePointerCancel(chart, event);
    };
    const onPointerLeave = (event: Event): void => {
        if (!(event instanceof PointerEvent)) {
            throw new TypeError('Chart pointerleave listener requires a PointerEvent');
        }
        handlePointerLeave(chart, event);
    };
    const onDoubleClick = (event: Event): void => {
        if (event instanceof MouseEvent) {
            const point = measureLayoutPoint(event, interactionTarget);
            handleDoubleClickFromCoordinates(chart, point.x, point.y, 'mouse');
            return;
        }
        throw new TypeError('Chart double-click listener requires a MouseEvent');
    };
    const onKeyDown = (event: Event): void => {
        if (!(event instanceof KeyboardEvent)) {
            throw new TypeError('Chart keydown listener requires a KeyboardEvent');
        }
        handleKeyboardNavigation(chart, event);
    };

    add(interactionTarget, 'wheel', onWheel, passiveFalse);
    add(interactionTarget, 'pointerdown', onPointerDown, passiveFalse);
    add(interactionTarget, 'pointermove', onPointerMove, passiveFalse);
    add(interactionTarget, 'pointerup', onPointerUp);
    add(interactionTarget, 'pointercancel', onPointerCancel);
    add(interactionTarget, 'pointerleave', onPointerLeave);
    add(interactionTarget, 'dblclick', onDoubleClick);
    add(interactionTarget, 'keydown', onKeyDown);
};

export { setupEventListeners };
