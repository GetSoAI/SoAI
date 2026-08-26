/* SoAI - Shared modals dock hint [frontend/assets/ts/core/modals/modalhost/drag/dockHint.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import type { ModalHostState } from '@core/modals/modalhost/contracts.ts';

const DOCK_TOP_THRESHOLD = 0;
const MODAL_TOP_DOCK_HINT_CLASS = 'modal-top-dock-preview';
const MODAL_TOP_DOCK_HINT_VISIBLE_CLASS = 'is-visible';

const getDockHintElement = (state: ModalHostState, modal: HTMLElement): HTMLElement => {
    if (!state.dockHintElement) {
        const element = dom.create('div', {
            class: MODAL_TOP_DOCK_HINT_CLASS,
            'aria-hidden': 'true'
        });
        state.dockHintElement = element;
    }

    const dockHint = state.dockHintElement;
    if (dockHint.parentElement !== modal) {
        dom.remove(dockHint);
        const modalContent = dom.resolve('.modal-content', modal);
        if (modalContent instanceof HTMLElement) {
            dom.insertBefore(modal, dockHint, modalContent);
            return dockHint;
        }

        const overlay = dom.resolve('.modal-overlay', modal);
        if (overlay) {
            const insertBeforeTarget = overlay.nextElementSibling;
            if (insertBeforeTarget) {
                dom.insertBefore(modal, dockHint, insertBeforeTarget);
                return dockHint;
            }
        }
        dom.appendChild(modal, dockHint);
    }

    return state.dockHintElement;
};

const hideDockHint = (state: ModalHostState): void => {
    if (!state.dockHintVisible && !state.dockHintElement?.classList.contains(MODAL_TOP_DOCK_HINT_VISIBLE_CLASS)) {
        return;
    }
    state.dockHintVisible = false;
    state.dockHintVisibilityToken += 1;
    if (state.dockHintElement) {
        dom.removeClass(state.dockHintElement, MODAL_TOP_DOCK_HINT_VISIBLE_CLASS);
    }
};

const showDockHint = (state: ModalHostState, modal: HTMLElement): void => {
    const hint = getDockHintElement(state, modal);
    if (state.dockHintVisible) {
        return;
    }
    state.dockHintVisible = true;
    state.dockHintVisibilityToken += 1;
    const visibilityToken = state.dockHintVisibilityToken;
    requestAnimationFrame(() => {
        if (!state.dockHintElement || state.dockHintElement !== hint || state.dockHintVisibilityToken !== visibilityToken) {
            return;
        }
        if (!state.dockHintVisible) {
            return;
        }
        if (!hint.isConnected) {
            return;
        }
        dom.addClass(hint, MODAL_TOP_DOCK_HINT_VISIBLE_CLASS);
    });
};

const shouldShowDockHint = (state: ModalHostState, pointerY: number, modalId: string): boolean => {
    if (state.fullscreenState.has(modalId)) {
        return false;
    }
    const isFullscreenAllowed = state.registry.getConfig(modalId).allowFullscreen;
    if (!isFullscreenAllowed) {
        return false;
    }
    return pointerY <= DOCK_TOP_THRESHOLD;
};

export { hideDockHint, shouldShowDockHint, showDockHint };
