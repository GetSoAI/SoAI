/* SoAI - Shared modals host lifecycle [frontend/assets/ts/core/modals/modalhost/hostLifecycle.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { TIMEOUTS } from '@core/constants.ts';
import { runAsyncCleanupStepCollectingFailure, runCleanupStepCollectingFailure, throwCollectedCleanupFailures } from '@core/lifecycle/cleanup.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { withTimeout } from '@core/primitives/withTimeout.ts';
import type { ModalHandle } from '@core/modals/types.ts';
import { handleDragEnd, handleDragMove, handleDragStart } from '@core/modals/modalhost/eventsDrag.ts';
import { handleDoubleClick } from '@core/modals/modalhost/eventsDoubleClick.ts';
import { handleDocumentClick, handleKeyDown } from '@core/modals/modalhost/eventsPointer.ts';
import { handleResizeEnd, handleResizeMove, handleResizeStart } from '@core/modals/modalhost/eventsResize.ts';
import { initializeModalLayoutObservers, setupMobileViewportListener } from '@core/modals/modalhost/layout.ts';
import type { ModalHostState } from '@core/modals/modalhost/contracts.ts';
import { closeModal, closeOpenModals } from '@core/modals/modalhost/modalActions.ts';
import { releaseModalOwnership } from '@core/modals/modalhost/ownership.ts';
import { releaseModalBinding, type ModalBinding } from '@core/modals/modalhost/bindings.ts';

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

const disposeModalHost = async (state: ModalHostState, binders: Map<string, ModalBinding>, elements: Set<HTMLElement>, handles: Map<string, ModalHandle>, discardElement: (element: HTMLElement) => void): Promise<void> => {
    state.resources.seal();
    const failures: Error[] = [];
    runCleanupStepCollectingFailure(() => {
        closeOpenModals(state, { force: true, restoreFocus: false, reason: 'dispose' });
    }, failures);
    for (const ownership of [...state.ownership.values()])
        runCleanupStepCollectingFailure(() => {
            releaseModalOwnership(state, ownership);
        }, failures);
    const bindingReleases = [...binders].map(async ([modalId, binding]) => {
        const outcome = await releaseModalBinding(binding);
        if (outcome.type === 'failed') throw outcome.error;
        if (binders.get(modalId) === binding) binders.delete(modalId);
    });
    const discardReleasedRoots = (): void => {
        if (state.ownership.size || binders.size || failures.length) return;
        for (const element of [...elements]) {
            try {
                discardElement(element);
                elements.delete(element);
            } catch (error) {
                failures.push(ensureError(error));
            }
        }
    };
    discardReleasedRoots();
    await runAsyncCleanupStepCollectingFailure(async () => {
        const outcomes = await withTimeout(Promise.allSettled([...bindingReleases, state.resources.dispose()]), { timeoutMs: TIMEOUTS.API_REQUEST, timeoutMessage: 'Modal host release is unconfirmed' });
        for (const outcome of outcomes) if (outcome.status === 'rejected') failures.push(ensureError(outcome.reason));
    }, failures);
    discardReleasedRoots();
    if (!failures.length) handles.clear();
    throwCollectedCleanupFailures(failures);
};

export { initializeModalHost, disposeModalHost };
