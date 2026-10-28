/* SoAI - Frontend modal focus and stacked dialog isolation [frontend/assets/ts/core/modals/modalhost/focusIsolation.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getMutationObserverCtor } from '@core/environment/public.ts';
import { dom } from '@core/dom/dom.ts';
import type { ModalHostState } from '@core/modals/modalhost/contracts.ts';

const FOCUSABLE_SELECTOR = 'a[href], button:not([disabled]), input:not([disabled]):not([type="hidden"]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

const isAvailableFocusTarget = (element: HTMLElement): boolean => {
    return !element.matches(':disabled') && element.closest('[hidden], .u-hidden, [aria-hidden="true"], [inert]') === null;
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

const synchronizeViewportIsolation = (state: ModalHostState): void => {
    const viewportOpen = state.activeStack.some((modalId) => state.resolveModalElement(modalId)?.getAttribute('data-modal-presentation') === 'viewport');
    if (!viewportOpen) {
        if (state.viewportBodyObserver !== null) {
            state.viewportBodyObserver.disconnect();
            state.resources.untrack(state.viewportBodyObserver);
            state.viewportBodyObserver = null;
        }
        for (const [element, wasInert] of state.viewportInertSnapshots) element.toggleAttribute('inert', wasInert);
        state.viewportInertSnapshots.clear();
        return;
    }
    if (state.viewportBodyObserver === null) {
        const Observer = getMutationObserverCtor();
        const observer = new Observer(() => synchronizeModalStackAccessibility(state));
        observer.observe(dom.getBody(), { childList: true });
        state.resources.track(observer);
        state.viewportBodyObserver = observer;
    }
    const activeModals = state.activeStack.map((modalId) => state.resolveModalElement(modalId));
    for (const child of dom.getBody().children) {
        if (!(child instanceof HTMLElement) || activeModals.some((modal) => modal !== null && child.contains(modal))) continue;
        if (!state.viewportInertSnapshots.has(child)) state.viewportInertSnapshots.set(child, child.hasAttribute('inert'));
        child.setAttribute('inert', '');
    }
};

const synchronizeModalStackAccessibility = (state: ModalHostState): void => {
    synchronizeViewportIsolation(state);
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

export { isAvailableFocusTarget, handleModalTabNavigation, synchronizeModalStackAccessibility };
