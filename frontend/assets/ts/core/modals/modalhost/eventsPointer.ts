/* SoAI - Shared modals events pointer [frontend/assets/ts/core/modals/modalhost/eventsPointer.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { MODAL_HEADER_FULLSCREEN_SELECTOR } from '@core/modals/headerButtons.ts';
import { resolveClosestModalId } from '@core/modals/modalhost/guards.ts';
import { toggleFullscreen } from '@core/modals/modalhost/eventsFullscreen.ts';
import type { ModalHostState } from '@core/modals/modalhost/contracts.ts';
import type { ModalCloseOptions } from '@core/modals/types.ts';
import { handleModalTabNavigation } from '@core/modals/modalhost/focusIsolation.ts';

const resolveCloseTrigger = (targetElement: Element | null): Element | null => targetElement?.closest?.('[data-modal-close]') ?? null;

const resolveOverlayTarget = (targetElement: Element | null): Element | null => targetElement?.closest?.('.modal-overlay') ?? null;

const handleKeyDown = (state: ModalHostState, event: KeyboardEvent, closeModal: (id: string, options: ModalCloseOptions) => boolean): void => {
    if (handleModalTabNavigation(state, event)) {
        return;
    }
    if (event.key !== 'Escape') {
        return;
    }

    const top = state.activeStack[state.activeStack.length - 1];
    if (!top) {
        return;
    }

    const config = state.registry.getConfig(top);
    if (config.closeOnEsc === false) {
        return;
    }

    if (closeModal(top, { reason: 'escape' })) {
        event.stopPropagation();
        event.preventDefault();
    }
};

const consumeModalClick = (event: Event): void => {
    event.preventDefault();
    event.stopPropagation();
};

const handleDocumentClick = (state: ModalHostState, event: Event, closeModal: (id: string, options: ModalCloseOptions) => boolean): void => {
    const targetElement = event.target instanceof Element ? event.target : null;
    const trigger = resolveCloseTrigger(targetElement);
    if (trigger) {
        const dataId = dom.getData(trigger, 'modalClose');
        const resolved = dataId ? dataId : resolveClosestModalId(trigger);
        if (resolved && closeModal(resolved, { reason: 'trigger' })) {
            consumeModalClick(event);
        }
        return;
    }

    const fullscreenToggle = targetElement?.closest?.(MODAL_HEADER_FULLSCREEN_SELECTOR) ?? null;
    if (fullscreenToggle) {
        const modalId = resolveClosestModalId(fullscreenToggle);
        if (modalId) {
            toggleFullscreen(state, modalId);
            consumeModalClick(event);
        }
        return;
    }

    const overlay = resolveOverlayTarget(targetElement);
    if (!overlay) {
        return;
    }
    const modalId = resolveClosestModalId(overlay);
    if (!modalId) {
        return;
    }
    const config = state.registry.getConfig(modalId);
    if (state.activeStack.includes(modalId) && config.closeOnOverlay !== false && closeModal(modalId, { reason: 'overlay' })) {
        consumeModalClick(event);
    }
};

export { handleDocumentClick, handleKeyDown };
