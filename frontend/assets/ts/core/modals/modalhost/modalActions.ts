/* SoAI - Shared modals modal actions [frontend/assets/ts/core/modals/modalhost/modalActions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { measureLayoutBox } from '@core/layout/elementGeometry.ts';
import { dom } from '@core/dom/dom.ts';
import { getRequestAnimationFrame } from '@core/environment/public.ts';
import { applyBehaviorAttributes, prepareModalLayoutState, setModalOpenState } from '@core/modals/render.ts';
import { applyPosition, enforceBoundaries } from '@core/modals/modalhost/effects.ts';
import { syncFullscreenButton } from '@core/modals/modalhost/eventsFullscreen.ts';
import { advanceModalLayoutGeneration, isModalLayoutCurrent } from '@core/modals/modalhost/layoutGeneration.ts';
import { resolveCenteredPosition, sanitizeSavedModalState } from '@core/modals/modalhost/layoutPolicy.ts';
import { applySizeConstraints, resetSizeStyles } from '@core/modals/modalhost/sizePolicy.ts';
import { ensureResizeHandles, setupModalTabsScroll } from '@core/modals/modalhost/layout.ts';
import { notifyModalClosed, notifyModalOpened } from '@core/modals/modalhost/pageLock.ts';
import type { ModalHostState } from '@core/modals/modalhost/contracts.ts';
import { normalizeModalId } from '@core/modals/guards.ts';
import type { ModalBeforeCloseDetail, ModalCloseOptions, ModalOpenOptions, ModalRegisterOptions, ModalUserCloseReason } from '@core/modals/types.ts';
import { isFunction, isString } from '@core/typeGuards.ts';
import { synchronizeModalStackAccessibility } from '@core/modals/modalhost/focusIsolation.ts';
import { synchronizeModalFrame } from '@core/modals/modalhost/geometry.ts';

const getModalElement = (id: string): Element | null => {
    const modalId = id ? id.trim() : '';
    return modalId ? dom.resolve(`#${modalId}`) : null;
};

const isOpen = (state: ModalHostState, id: string): boolean => {
    return state.activeStack.includes(id);
};

const rememberFocus = (state: ModalHostState, id: string): void => {
    const active = dom.getActiveElement();
    if (active instanceof HTMLElement && isFunction(active.focus)) {
        state.focusMemory.set(id, active);
    } else {
        state.focusMemory.delete(id);
    }
};

const focusNode = (element: Element | null | undefined): void => {
    if (!(element instanceof HTMLElement)) {
        return;
    }
    if (!isFunction(element.focus)) {
        return;
    }
    element.focus({ preventScroll: true });
};

const restoreModalFocus = (state: ModalHostState, id: string): void => {
    focusNode(state.focusMemory.get(id));
    state.focusMemory.delete(id);
};

const focusModalElement = (state: ModalHostState, modalId: string, layoutGeneration: number, target: string | Element, modal: Element): void => {
    const element = isString(target) ? dom.resolve(target, modal) : target;
    if (element) {
        getRequestAnimationFrame()(() => {
            if (!isModalLayoutCurrent(state, modalId, layoutGeneration)) return;
            focusNode(element);
        });
    }
};

const raiseModalRoot = (modal: Element): void => {
    if (!(modal instanceof HTMLElement)) {
        return;
    }
    const parent = modal.parentElement;
    if (parent instanceof HTMLElement && modal.nextElementSibling !== null) {
        parent.appendChild(modal);
    }
};

const requireModalContent = (modal: Element): HTMLElement => {
    const contentElement = dom.resolve('.modal-content', modal);
    if (!(contentElement instanceof HTMLElement)) {
        throw new Error('Modal content is required for modal layout');
    }
    return contentElement;
};

const isUserInitiatedCloseReason = (reason: string | undefined): reason is ModalUserCloseReason => {
    return reason === 'escape' || reason === 'overlay' || reason === 'trigger';
};

const registerModal = (state: ModalHostState, id: string, options: ModalRegisterOptions): { open: (openOptions?: ModalOpenOptions) => boolean; close: (closeOptions?: ModalCloseOptions) => boolean; toggle: (force?: boolean | null) => boolean; isOpen: () => boolean } => {
    const modalId = normalizeModalId(id);
    const config = state.registry.register(modalId, options);

    const modal = state.resolveModalElement(modalId);
    if (modal) applyBehaviorAttributes(modal, config);

    return {
        open: (openOptions?: ModalOpenOptions) => openModal(state, modalId, openOptions),
        close: (closeOptions?: ModalCloseOptions) => closeModal(state, modalId, closeOptions),
        toggle: (force?: boolean | null) => toggleModal(state, modalId, force),
        isOpen: () => isOpen(state, modalId)
    };
};

const openModal = (state: ModalHostState, id: string, options: ModalOpenOptions = {}): boolean => {
    const modalId = normalizeModalId(id);
    const modal = state.ensureModalElement(modalId);

    const config = state.registry.getConfig(modalId);
    applyBehaviorAttributes(modal, config, options.layoutOverride);
    if (options.layoutOverride) {
        state.layoutOverrides.set(modalId, options.layoutOverride);
    } else {
        state.layoutOverrides.delete(modalId);
    }
    setupModalTabsScroll(state, modal);
    raiseModalRoot(modal);
    if (modal instanceof HTMLElement) {
        syncFullscreenButton(state, modalId, modal);
    }

    const wasOpen = isOpen(state, modalId);
    if (wasOpen) {
        state.activeStack = state.activeStack.filter((value) => value !== modalId);
        state.activeStack.push(modalId);
        synchronizeModalStackAccessibility(state);
        if (options.force !== true) {
            setModalOpenState(modal, true);
            return true;
        }
    }

    rememberFocus(state, modalId);
    const layoutGeneration = advanceModalLayoutGeneration(state);
    const content = requireModalContent(modal);
    synchronizeModalFrame(modal, state.isMobileViewportState);
    prepareModalLayoutState(modal);

    try {
        const savedState = sanitizeSavedModalState(state.storage.getModalState(modalId));
        const sizeResult = applySizeConstraints({
            content,
            config,
            isMobileViewport: state.isMobileViewportState,
            savedState,
            layoutOverride: options.layoutOverride
        });
        const sizeOverride = sizeResult ? { width: sizeResult.width, height: sizeResult.height } : null;
        const centeredPosition = resolveCenteredPosition({
            content,
            isMobileViewport: state.isMobileViewportState,
            sizeOverride
        });
        applyPosition(content, centeredPosition);

        if (config.resizable) {
            dom.addClass(content, 'resizable');
            ensureResizeHandles(content);
        } else {
            dom.removeClass(content, 'resizable');
        }

        enforceBoundaries({
            content,
            isMobileViewport: state.isMobileViewportState,
            sizeOverride
        });

        state.resources.requestAnimationFrame(() => {
            if (!isModalLayoutCurrent(state, modalId, layoutGeneration)) {
                return;
            }
            if (state.fullscreenState.has(modalId)) {
                return;
            }
            const rect = measureLayoutBox(content);
            enforceBoundaries({
                content,
                isMobileViewport: state.isMobileViewportState,
                sizeOverride: rect.width > 0 ? { width: rect.width, height: rect.height } : null
            });
        });
    } catch (error) {
        if (!wasOpen) {
            setModalOpenState(modal, false);
        }
        throw error;
    }

    setModalOpenState(modal, true);
    if (!wasOpen) {
        state.activeStack.push(modalId);
        notifyModalOpened(state);
    }
    synchronizeModalStackAccessibility(state);
    modal.dispatchEvent(new Event('core.modal.open', { bubbles: true }));
    getRequestAnimationFrame()(() => {
        if (!isModalLayoutCurrent(state, modalId, layoutGeneration)) return;
        focusModalElement(state, modalId, layoutGeneration, config.initialFocusSelector, modal);
        if (isFunction(config.onOpen)) {
            config.onOpen(modal, options);
        }
    });

    return true;
};

const closeModal = (state: ModalHostState, id: string, options: ModalCloseOptions = {}): boolean => {
    const modalId = normalizeModalId(id);
    const wasOpen = isOpen(state, modalId);
    if (!wasOpen && options.force !== true) {
        return false;
    }

    const modal = state.resolveModalElement(modalId) ?? state.ensureModalElement(modalId);
    if (options.force !== true && isUserInitiatedCloseReason(options.reason)) {
        const detail: ModalBeforeCloseDetail = {
            modalId,
            reason: options.reason
        };
        const allowed = modal.dispatchEvent(
            new CustomEvent<ModalBeforeCloseDetail>('core.modal.beforeClose', {
                bubbles: true,
                cancelable: true,
                detail
            })
        );
        if (!allowed) {
            return false;
        }
    }
    const config = state.registry.getConfig(modalId);
    advanceModalLayoutGeneration(state);
    state.dragState.delete(modalId);
    state.resizeState.delete(modalId);
    const contentElement = dom.resolve('.modal-content', modal);
    if (contentElement instanceof HTMLElement) {
        dom.removeClass(contentElement, 'is-fullscreen');
        dom.setStyle(contentElement, 'animation', '');
        dom.setStyle(contentElement, 'opacity', '');
        dom.setStyle(contentElement, 'transition', '');
        resetSizeStyles(contentElement);
        applyPosition(contentElement, { x: 0, y: 0 });
    }
    state.fullscreenState.delete(modalId);
    state.layoutOverrides.delete(modalId);
    setModalOpenState(modal, false);
    state.activeStack = state.activeStack.filter((value) => value !== modalId);
    synchronizeModalStackAccessibility(state);
    modal.dispatchEvent(new Event('core.modal.close', { bubbles: true }));

    notifyModalClosed(state);

    if (isFunction(config.onClose)) {
        config.onClose(modal, options);
    }
    const shouldRestore = options.restoreFocus ?? config.restoreFocus;
    if (shouldRestore) {
        restoreModalFocus(state, modalId);
    } else {
        state.focusMemory.delete(modalId);
    }
    return true;
};

const toggleModal = (state: ModalHostState, id: string, force: boolean | null = null): boolean => {
    const modalId = normalizeModalId(id);
    if (force === true) {
        return openModal(state, modalId);
    }
    if (force === false) {
        return closeModal(state, modalId);
    }
    return isOpen(state, modalId) ? closeModal(state, modalId) : openModal(state, modalId);
};

const closeTopModal = (state: ModalHostState, options: ModalCloseOptions = {}): boolean => {
    const top = state.activeStack.length ? state.activeStack[state.activeStack.length - 1] : null;
    if (!top) {
        return false;
    }
    return closeModal(state, top, options);
};

const closeOpenModals = (state: ModalHostState, options: ModalCloseOptions = {}): number => {
    const modalIds = state.activeStack.slice().reverse();
    let closed = 0;
    for (const modalId of modalIds) {
        if (closeModal(state, modalId, options)) {
            closed += 1;
        }
    }
    return closed;
};

export { closeModal, closeOpenModals, closeTopModal, getModalElement, isOpen, openModal, registerModal, rememberFocus, restoreModalFocus, toggleModal };
