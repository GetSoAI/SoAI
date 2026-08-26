/* SoAI - Frontend modal focus and stacked dialog isolation [frontend/assets/ts/core/modals/modalhost/focusIsolation.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import type { ModalHostState } from '@core/modals/modalhost/contracts.ts';

const FOCUSABLE_SELECTOR = 'a[href], button:not([disabled]), input:not([disabled]):not([type="hidden"]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

const isAvailableFocusTarget = (element: HTMLElement): boolean => {
    return !element.hidden && !element.classList.contains('u-hidden') && element.getAttribute('aria-hidden') !== 'true' && element.closest('[inert]') === null;
};

const listFocusableElements = (modal: HTMLElement): HTMLElement[] => {
    return dom.resolveAll(FOCUSABLE_SELECTOR, modal).filter((element): element is HTMLElement => element instanceof HTMLElement && isAvailableFocusTarget(element));
};

const focusElement = (element: HTMLElement): void => {
    element.focus({ preventScroll: true });
};

const focusModalFallback = (modal: HTMLElement): void => {
    const content = dom.resolve('.modal-content', modal);
    focusElement(content instanceof HTMLElement ? content : modal);
};

const handleModalTabNavigation = (state: ModalHostState, event: KeyboardEvent): boolean => {
    if (event.key !== 'Tab') return false;
    const topModalId = state.activeStack[state.activeStack.length - 1];
    if (!topModalId) return false;
    const modal = state.resolveModalElement(topModalId);
    if (!modal) return false;

    const focusableElements = listFocusableElements(modal);
    const activeElement = dom.getActiveElement();
    if (!focusableElements.length) {
        focusModalFallback(modal);
        event.preventDefault();
        event.stopPropagation();
        return true;
    }

    let firstElement = modal;
    let lastElement = modal;
    for (const focusableElement of focusableElements) {
        if (firstElement === modal) firstElement = focusableElement;
        lastElement = focusableElement;
    }
    const activeInsideTopModal = activeElement instanceof Element && modal.contains(activeElement);
    const shouldWrapBackward = event.shiftKey && (!activeInsideTopModal || activeElement === firstElement);
    const shouldWrapForward = !event.shiftKey && (!activeInsideTopModal || activeElement === lastElement);
    if (!shouldWrapBackward && !shouldWrapForward) return false;

    focusElement(shouldWrapBackward ? lastElement : firstElement);
    event.preventDefault();
    event.stopPropagation();
    return true;
};

const synchronizeModalStackAccessibility = (state: ModalHostState): void => {
    const topModalId = state.activeStack[state.activeStack.length - 1] ?? null;
    state.activeStack.forEach((modalId) => {
        const modal = state.resolveModalElement(modalId);
        if (!modal) return;
        const isTopModal = modalId === topModalId;
        modal.setAttribute('aria-hidden', isTopModal ? 'false' : 'true');
        modal.setAttribute('aria-modal', isTopModal ? 'true' : 'false');
        if (isTopModal) {
            modal.removeAttribute('inert');
        } else {
            modal.setAttribute('inert', '');
        }
    });
};

export { handleModalTabNavigation, synchronizeModalStackAccessibility };
