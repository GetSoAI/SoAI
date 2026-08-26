/* SoAI - Advanced scroll preview pointer interaction runtime [frontend/assets/ts/features/chat/chatuimanager/advancedScrollPreviewDragRuntime.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { measureLayoutBox, measureLayoutPoint } from '@core/layout/elementGeometry.ts';
import { CSS_CLASSES } from '@core/cssConstants.ts';
import { clampNumber } from '@core/primitives/clampNumber.ts';
import { syncAutoScrollLockAttribute } from '@features/chat/chatuimanager/autoScrollLockRuntime.ts';
import { mapAdvancedScrollPreviewClickToScrollTop } from '@features/chat/chatuimanager/advancedScrollPreviewMath.ts';
import type { ChatUIManagerContext } from '@features/chat/chatuimanager/types.ts';

type DragVisibilityState = {
    visible: boolean;
    grooveHeight: number;
    thumbTop: number;
    thumbHeight: number;
    maxScrollTop: number;
    scrollHeight: number;
    clientHeight: number;
};

type DragRuntimeInput = {
    context: ChatUIManagerContext;
    overlay: HTMLElement;
    messagesArea: HTMLElement;
    getVisibilityState: () => DragVisibilityState | null;
    scheduleThumbUpdate: () => void;
    onDragStateChange: (isDragging: boolean) => void;
};

export type AdvancedScrollPreviewDragRuntime = {
    stop: () => void;
    dispose: () => void;
};

export const createAdvancedScrollPreviewDragRuntime = (input: DragRuntimeInput): AdvancedScrollPreviewDragRuntime => {
    const doc = input.context.dependencies.dom.getDocument();
    let isDragging = false;
    let activePointerId: number | null = null;
    let dragOffsetY = 0;
    let dragMoveDisposer: (() => void) | null = null;
    let dragUpDisposer: (() => void) | null = null;
    let dragCancelDisposer: (() => void) | null = null;
    let dragBlurDisposer: (() => void) | null = null;

    const markMinimapScrollIntent = (): void => {
        input.context.state.autoScrollUserIntentActive = true;
        input.context.state.autoScrollEnabled = false;
        syncAutoScrollLockAttribute(input.context, input.messagesArea);
    };

    const clearDocumentDragListeners = (): void => {
        dragMoveDisposer?.();
        dragMoveDisposer = null;
        dragUpDisposer?.();
        dragUpDisposer = null;
        dragCancelDisposer?.();
        dragCancelDisposer = null;
        dragBlurDisposer?.();
        dragBlurDisposer = null;
    };

    const stop = (): void => {
        if (!isDragging) {
            clearDocumentDragListeners();
            return;
        }
        isDragging = false;
        activePointerId = null;
        dragOffsetY = 0;
        input.onDragStateChange(false);
        input.context.dependencies.toggleClassName(input.overlay, CSS_CLASSES.HOVER, false);
        clearDocumentDragListeners();
    };

    const handleDragPointerMove = (event: Event): void => {
        if (!(event instanceof PointerEvent)) {
            return;
        }
        if (!isDragging || activePointerId === null || event.pointerId !== activePointerId) {
            return;
        }
        const state = input.getVisibilityState();
        if (!state || !state.visible || state.grooveHeight <= 0 || state.thumbHeight <= 0) {
            event.preventDefault();
            stop();
            return;
        }
        const overlayRect = measureLayoutBox(input.overlay);
        const point = measureLayoutPoint(event, input.overlay);
        const yCoordinate = clampNumber(point.y - overlayRect.top, 0, state.grooveHeight);
        const trackHeight = Math.max(1, state.grooveHeight - state.thumbHeight);
        const desiredThumbTop = clampNumber(yCoordinate - dragOffsetY, 0, trackHeight);
        const ratio = trackHeight > 0 ? desiredThumbTop / trackHeight : 0;
        const targetScrollTop = clampNumber(ratio * state.maxScrollTop, 0, state.maxScrollTop);
        markMinimapScrollIntent();
        input.messagesArea.scrollTop = targetScrollTop;
        event.preventDefault();
        input.scheduleThumbUpdate();
    };

    const handleDragPointerUp = (event: Event): void => {
        if (!(event instanceof PointerEvent)) {
            return;
        }
        if (activePointerId === null || event.pointerId !== activePointerId) {
            return;
        }
        stop();
        input.scheduleThumbUpdate();
    };

    const handlePointerDown = (event: Event): void => {
        if (!(event instanceof PointerEvent)) {
            return;
        }
        if (event.button !== 0 && event.pointerType === 'mouse') {
            return;
        }
        const state = input.getVisibilityState();
        if (!state) {
            return;
        }
        if (!state.visible || state.grooveHeight <= 0) {
            return;
        }

        const overlayRect = measureLayoutBox(input.overlay);
        const point = measureLayoutPoint(event, input.overlay);
        const yCoordinate = clampNumber(point.y - overlayRect.top, 0, state.grooveHeight);

        stop();
        isDragging = true;
        activePointerId = event.pointerId;
        input.onDragStateChange(true);
        input.context.dependencies.toggleClassName(input.overlay, CSS_CLASSES.HOVER, true);

        const hitThumb = yCoordinate >= state.thumbTop && yCoordinate <= state.thumbTop + state.thumbHeight;
        if (hitThumb) {
            dragOffsetY = yCoordinate - state.thumbTop;
        } else {
            dragOffsetY = state.thumbHeight / 2;
            const targetScrollTop = mapAdvancedScrollPreviewClickToScrollTop({
                clickY: yCoordinate,
                grooveHeight: state.grooveHeight,
                scrollHeight: state.scrollHeight,
                clientHeight: state.clientHeight
            });
            markMinimapScrollIntent();
            input.messagesArea.scrollTop = targetScrollTop;
        }

        dragMoveDisposer = input.context.dependencies.runtime.on(doc, 'pointermove', handleDragPointerMove, { passive: false });
        dragUpDisposer = input.context.dependencies.runtime.on(doc, 'pointerup', handleDragPointerUp);
        dragCancelDisposer = input.context.dependencies.runtime.on(doc, 'pointercancel', handleDragPointerUp);
        dragBlurDisposer = input.context.dependencies.runtime.on(doc.defaultView ?? doc, 'blur', () => stop());
        event.preventDefault();
        input.scheduleThumbUpdate();
    };

    const onPointerDownDisposer = input.context.dependencies.runtime.on(input.overlay, 'pointerdown', handlePointerDown, { passive: false });

    return {
        stop,
        dispose: () => {
            onPointerDownDisposer();
            stop();
        }
    };
};
