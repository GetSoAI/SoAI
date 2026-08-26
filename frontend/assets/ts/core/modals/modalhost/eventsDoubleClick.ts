/* SoAI - Shared modals events double click [frontend/assets/ts/core/modals/modalhost/eventsDoubleClick.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isEditableInteractionTarget } from '@core/dom/editableTargets.ts';
import { MODAL_HEADER_CLOSE_SELECTOR, MODAL_HEADER_FULLSCREEN_SELECTOR } from '@core/modals/headerButtons.ts';
import { resolveClosestModalId } from '@core/modals/modalhost/guards.ts';
import type { ModalHostState } from '@core/modals/modalhost/contracts.ts';
import { toggleFullscreen } from '@core/modals/modalhost/eventsFullscreen.ts';

const getEventElement = (target: EventTarget | null): Element | null => {
    if (!target) {
        return null;
    }
    if (target instanceof Element) {
        return target;
    }
    if (target instanceof Node && target.parentElement) {
        return target.parentElement;
    }
    return null;
};

const resolveHeaderTop = (target: EventTarget | null): Element | null => {
    const element = getEventElement(target);
    if (!element) {
        return null;
    }
    return element.closest('.modal-header-top');
};

const isHeaderControl = (target: EventTarget | null): boolean => {
    const element = getEventElement(target);
    return element !== null && element.closest(`${MODAL_HEADER_CLOSE_SELECTOR}, ${MODAL_HEADER_FULLSCREEN_SELECTOR}`) !== null;
};

const isDragOrResizeActive = (state: ModalHostState, modalId: string): boolean => {
    const dragState = state.dragState.get(modalId);
    if (dragState?.isDragging) {
        return true;
    }

    const resizeState = state.resizeState.get(modalId);
    return Boolean(resizeState?.isResizing);
};

const handleDoubleClick = (state: ModalHostState, event: MouseEvent): void => {
    if (state.isMobileViewportState) {
        return;
    }

    if (event.detail < 2) {
        return;
    }

    const target = event.target;
    if (isEditableInteractionTarget(target)) {
        return;
    }

    const headerTop = resolveHeaderTop(target);
    if (!headerTop || isHeaderControl(target)) {
        return;
    }

    const modalId = resolveClosestModalId(headerTop);
    if (!modalId) {
        return;
    }

    if (isDragOrResizeActive(state, modalId)) {
        return;
    }

    toggleFullscreen(state, modalId);
};

export { handleDoubleClick };
