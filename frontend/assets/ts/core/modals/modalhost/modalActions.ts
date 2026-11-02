/* SoAI - Shared modals modal actions [frontend/assets/ts/core/modals/modalhost/modalActions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { runCleanupStepCollectingFailure, throwCollectedCleanupFailures } from '@core/lifecycle/cleanup.ts';
import type { PresentationOwner } from '@core/routing/router/types.ts';
import { acquireModalOwnership, releaseModalOwnership, requireModalOwnership } from '@core/modals/modalhost/ownership.ts';
import { measureLayoutBox } from '@core/layout/elementGeometry.ts';
import { finishPresenceAnimations, isPresenceExiting } from '@core/animations/presence/public.ts';
import { dom } from '@core/dom/dom.ts';
import { getRequestAnimationFrame } from '@core/environment/public.ts';
import { applyBehaviorAttributes, prepareModalLayoutState, setModalOpenState } from '@core/modals/render.ts';
import { applyPosition, enforceBoundaries } from '@core/modals/modalhost/effects.ts';
import { syncFullscreenButton } from '@core/modals/modalhost/eventsFullscreen.ts';
import { advanceModalLayoutGeneration, isModalLayoutCurrent } from '@core/modals/modalhost/layoutGeneration.ts';
import { resolveCenteredPosition, sanitizeSavedModalState } from '@core/modals/modalhost/layoutPolicy.ts';
import { applySizeConstraints, lockModalContentHeight, resetSizeStyles } from '@core/modals/modalhost/sizePolicy.ts';
import { ensureResizeHandles } from '@core/modals/modalhost/layout.ts';
import { notifyModalClosed, notifyModalOpened } from '@core/modals/modalhost/pageLock.ts';
import type { ModalHostState } from '@core/modals/modalhost/contracts.ts';
import { normalizeModalId } from '@core/modals/guards.ts';
import type { ModalBeforeCloseDetail, ModalOwnership, ModalHandle, ModalCloseOptions, ModalOpenOptions, ModalRegisterOptions, ModalUserCloseReason } from '@core/modals/types.ts';
import { isFunction } from '@core/typeGuards.ts';
import { focusModalElement, rememberFocus, restoreModalFocus, synchronizeModalStackAccessibility } from '@core/modals/modalhost/focusIsolation.ts';

const getModalElement = (id: string): Element | null => {
    const modalId = id ? id.trim() : '';
    return modalId ? dom.resolve(`#${modalId}`) : null;
};

const isOpen = (state: ModalHostState, id: string): boolean => {
    return state.activeStack.includes(id);
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

const registerModal = (state: ModalHostState, id: string, options: ModalRegisterOptions): ModalHandle => {
    const modalId = normalizeModalId(id);
    const config = state.registry.register(modalId, options);

    const modal = state.resolveModalElement(modalId);
    if (modal) applyBehaviorAttributes(modal, config);

    return {
        open: (openOptions: ModalOpenOptions) => openModal(state, modalId, openOptions),
        close: (closeOptions?: ModalCloseOptions) => closeModal(state, modalId, closeOptions),
        toggle: (openOptions: ModalOpenOptions, force?: boolean | null) => toggleModal(state, modalId, openOptions, force),
        isOpen: () => isOpen(state, modalId)
    };
};

const openModal = (state: ModalHostState, id: string, options: ModalOpenOptions, reserved?: ModalOwnership): boolean => {
    const modalId = normalizeModalId(id);
    const wasOpen = isOpen(state, modalId);
    const previousOwnership = state.ownership.get(modalId);
    if (previousOwnership && (previousOwnership.owner !== options.owner || (!wasOpen && reserved !== previousOwnership))) throw new Error('Modal is already owned by another presentation');
    const ownership = reserved ?? previousOwnership ?? acquireModalOwnership(state, modalId, options.owner);
    requireModalOwnership(state, ownership);
    let modal: HTMLElement;
    try {
        modal = state.ensureModalElement(modalId);
        requireModalOwnership(state, ownership);
    } catch (error) {
        releaseModalOwnership(state, ownership);
        throw error;
    }
    if (isPresenceExiting(modal)) finishPresenceAnimations(modal);

    const config = state.registry.getConfig(modalId);
    applyBehaviorAttributes(modal, config, options.layoutOverride);
    if (options.layoutOverride) {
        state.layoutOverrides.set(modalId, options.layoutOverride);
    } else {
        state.layoutOverrides.delete(modalId);
    }
    raiseModalRoot(modal);
    if (modal instanceof HTMLElement) {
        syncFullscreenButton(state, modalId, modal);
    }

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
    prepareModalLayoutState(modal);

    try {
        if (config.presentation === 'window') {
            const savedState = sanitizeSavedModalState(state.storage.getModalState(modalId));
            let sizeResult = applySizeConstraints({
                content,
                config,
                isMobileViewport: state.isMobileViewportState,
                savedState,
                layoutOverride: options.layoutOverride,
                desktopOpenHeight: state.desktopOpenHeights.get(modalId)
            });
            if (sizeResult && !state.isMobileViewportState) {
                const locked = lockModalContentHeight(content, sizeResult);
                state.desktopOpenHeights.set(modalId, locked.desktopOpenHeight);
                sizeResult = locked.sizeResult;
            }
            const sizeOverride = sizeResult ? { width: sizeResult.width, height: sizeResult.height } : null;
            const centeredPosition = resolveCenteredPosition({
                content,
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
                    sizeOverride: rect.width > 0 ? { width: rect.width, height: rect.height } : null
                });
            });
        }
    } catch (error) {
        if (!wasOpen) {
            state.desktopOpenHeights.delete(modalId);
            resetSizeStyles(content);
            setModalOpenState(modal, false);
            releaseModalOwnership(state, ownership);
        }
        throw error;
    }

    setModalOpenState(modal, true);
    if (!wasOpen) {
        state.activeStack.push(modalId);
        notifyModalOpened(state);
    }
    synchronizeModalStackAccessibility(state);
    modal.dispatchEvent(new CustomEvent('core.modal.open', { bubbles: true, detail: ownership }));
    getRequestAnimationFrame()(() => {
        if (!isModalLayoutCurrent(state, modalId, layoutGeneration) || state.ownership.get(modalId) !== ownership) return;
        if (ownership.owner.type !== 'global' && !ownership.owner.admission.isActive()) return;
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
    const ownership = state.ownership.get(modalId);
    if (ownership && state.ownershipLifetimes.get(ownership)?.type === 'releasing') return false;
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
        if (!allowed || state.ownership.get(modalId) !== ownership) return false;
    }
    const config = state.registry.getConfig(modalId);
    advanceModalLayoutGeneration(state);
    state.dragState.delete(modalId);
    state.resizeState.delete(modalId);
    const contentElement = dom.resolve('.modal-content', modal);
    state.fullscreenState.delete(modalId);
    state.layoutOverrides.delete(modalId);
    state.desktopOpenHeights.delete(modalId);
    setModalOpenState(modal, false, () => {
        if (contentElement instanceof HTMLElement && config.presentation === 'window') {
            dom.removeClass(contentElement, 'is-fullscreen');
            dom.setStyle(contentElement, 'animation', '');
            dom.setStyle(contentElement, 'opacity', '');
            dom.setStyle(contentElement, 'transition', '');
            resetSizeStyles(contentElement);
            applyPosition(contentElement, { x: 0, y: 0 });
        }
    });
    state.activeStack = state.activeStack.filter((value) => value !== modalId);
    const failures: Error[] = [];
    runCleanupStepCollectingFailure(() => synchronizeModalStackAccessibility(state), failures);
    const replacement = options.replacementFocusTarget;
    if (replacement?.isConnected) {
        for (const [savedModalId, target] of state.focusMemory) {
            if (modal.contains(target)) state.focusMemory.set(savedModalId, replacement);
        }
    }
    runCleanupStepCollectingFailure(() => modal.dispatchEvent(new Event('core.modal.close', { bubbles: true })), failures);

    if (wasOpen) runCleanupStepCollectingFailure(() => notifyModalClosed(state), failures);

    const hasReplacementOwnership = (): boolean => {
        const current = state.ownership.get(modalId);
        return current !== undefined && current !== ownership;
    };
    if (hasReplacementOwnership()) return true;
    if (isFunction(config.onClose)) runCleanupStepCollectingFailure(() => config.onClose?.(modal, options), failures);
    if (hasReplacementOwnership()) return true;
    const shouldRestore = options.restoreFocus ?? config.restoreFocus;
    if (shouldRestore) {
        runCleanupStepCollectingFailure(() => restoreModalFocus(state, modalId), failures);
    } else {
        state.focusMemory.delete(modalId);
    }
    if (ownership) releaseModalOwnership(state, ownership, failures);
    throwCollectedCleanupFailures(failures);
    return true;
};

const toggleModal = (state: ModalHostState, id: string, options: ModalOpenOptions, force: boolean | null = null): boolean => {
    const modalId = normalizeModalId(id);
    if (force === true) {
        return openModal(state, modalId, options);
    }
    if (force === false) {
        return closeModal(state, modalId);
    }
    return isOpen(state, modalId) ? closeModal(state, modalId) : openModal(state, modalId, options);
};

const closeTopModal = (state: ModalHostState, options: ModalCloseOptions = {}): boolean => {
    const top = state.activeStack.length ? state.activeStack[state.activeStack.length - 1] : null;
    if (!top) {
        return false;
    }
    return closeModal(state, top, options);
};

const closeOpenModals = (state: ModalHostState, options: ModalCloseOptions = {}, owner?: PresentationOwner): number => {
    const ownedModals = state.activeStack
        .slice()
        .reverse()
        .map((modalId) => ({ modalId, ownership: state.ownership.get(modalId) }));
    let closed = 0;
    for (const { modalId, ownership } of ownedModals) {
        if ((owner && ownership?.owner !== owner) || state.ownership.get(modalId) !== ownership) continue;
        if (closeModal(state, modalId, options)) {
            closed += 1;
        }
    }
    return closed;
};

export { closeModal, closeOpenModals, closeTopModal, getModalElement, isOpen, openModal, registerModal, toggleModal };
