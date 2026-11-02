/* SoAI - Frontend modal focus and stacked dialog isolation [frontend/assets/ts/core/modals/modalhost/focusIsolation.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getMutationObserverCtor, getRequestAnimationFrame } from '@core/environment/public.ts';
import { isModalLayoutCurrent } from '@core/modals/modalhost/layoutGeneration.ts';
import { isPresentationOwnerActive } from '@core/presentationOwner.ts';
import { isAvailableFocusTarget } from '@core/dom/focusTarget.ts';
import { dom } from '@core/dom/dom.ts';
import type { ModalHostState } from '@core/modals/modalhost/contracts.ts';

const FOCUSABLE_SELECTOR = 'a[href], button:not([disabled]), input:not([disabled]):not([type="hidden"]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

const listFocusableElements = (modal: HTMLElement): HTMLElement[] => {
    return dom.resolveAll(FOCUSABLE_SELECTOR, modal).filter((element): element is HTMLElement => element instanceof HTMLElement && isAvailableFocusTarget(element));
};

const focusElement = (element: HTMLElement): void => {
    element.focus({ preventScroll: true });
};

const rememberFocus = (state: ModalHostState, id: string): void => {
    const active = dom.getActiveElement();
    if (active instanceof HTMLElement) state.focusMemory.set(id, active);
    else state.focusMemory.delete(id);
};

const restoreModalFocus = (state: ModalHostState, id: string): void => {
    const target = state.focusMemory.get(id);
    state.focusMemory.delete(id);
    if (target instanceof HTMLElement && target.isConnected && isAvailableFocusTarget(target)) focusElement(target);
};

const focusModalElement = (state: ModalHostState, modalId: string, layoutGeneration: number, target: string | Element, modal: Element): void => {
    const ownership = state.ownership.get(modalId);
    const element = typeof target === 'string' ? dom.resolve(target, modal) : target;
    if (!ownership || !(element instanceof HTMLElement)) return;
    getRequestAnimationFrame()(() => {
        if (!isModalLayoutCurrent(state, modalId, layoutGeneration) || state.ownership.get(modalId) !== ownership || ownership.signal.aborted || modal.contains(dom.getActiveElement())) return;
        if (!isPresentationOwnerActive(ownership.owner) || state.activeStack[state.activeStack.length - 1] !== modalId) return;
        focusElement(element);
    });
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

export { focusModalElement, rememberFocus, restoreModalFocus, handleModalTabNavigation, synchronizeModalStackAccessibility };
