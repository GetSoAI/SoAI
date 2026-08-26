/* SoAI - Shared modals host lifecycle [frontend/assets/ts/core/modals/modalhost/hostLifecycle.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { handleDragEnd, handleDragMove, handleDragStart } from '@core/modals/modalhost/eventsDrag.ts';
import { handleDoubleClick } from '@core/modals/modalhost/eventsDoubleClick.ts';
import { handleDocumentClick, handleKeyDown } from '@core/modals/modalhost/eventsPointer.ts';
import { handleResizeEnd, handleResizeMove, handleResizeStart } from '@core/modals/modalhost/eventsResize.ts';
import { initializeModalLayoutObservers, setupMobileViewportListener } from '@core/modals/modalhost/layout.ts';
import type { ModalHostState } from '@core/modals/modalhost/contracts.ts';
import { closeModal } from '@core/modals/modalhost/modalActions.ts';

const initializeModalHost = (state: ModalHostState): void => {
    if (state.initialized) {
        return;
    }
    state.initialized = true;

    const doc = dom.getDocument();
    state.resources.addEventListener(doc, 'keydown', (event: Event) => {
        if (!(event instanceof KeyboardEvent)) {
            return;
        }
        handleKeyDown(state, event, (id, options) => closeModal(state, id, options));
    });
    state.resources.addEventListener(doc, 'click', (event: Event) => handleDocumentClick(state, event, (id, options) => closeModal(state, id, options)));
    state.resources.addEventListener(doc, 'dblclick', (event: Event) => {
        if (!(event instanceof MouseEvent)) {
            return;
        }
        handleDoubleClick(state, event);
    });

    const types = ['mousedown', 'mousemove', 'mouseup', 'touchstart', 'touchmove', 'touchend', 'touchcancel'];
    const dragHandlers = [handleDragStart, handleDragMove, handleDragEnd];
    const resizeHandlers = [handleResizeStart, handleResizeMove, handleResizeEnd];

    types.forEach((type, index) => {
        const indexForMouse = index < 3 ? index : index === 3 ? 0 : index === 4 ? 1 : 2;
        const options = type === 'touchstart' || type === 'touchmove' ? { passive: false } : undefined;
        const dragHandler = dragHandlers[indexForMouse];
        const resizeHandler = resizeHandlers[indexForMouse];

        if (dragHandler) {
            state.resources.addEventListener(doc, type, (event: Event) => dragHandler(state, event), options);
        }
        if (resizeHandler) {
            state.resources.addEventListener(doc, type, (event: Event) => resizeHandler(state, event), options);
        }
    });

    setupMobileViewportListener(state);
    initializeModalLayoutObservers(state);
};

export { initializeModalHost };
