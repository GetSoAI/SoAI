/* SoAI - Standardized modal presenter contract [frontend/assets/ts/core/modals/modalPresenter.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ErrorBoundary } from '@core/ErrorBoundary.ts';
import { createDeferred } from '@core/runtime/deferred.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { normalizeModalId, validateModalRootContract } from '@core/modals/guards.ts';
import { createModalHostState, type ModalHostState } from '@core/modals/modalhost/contracts.ts';
import type { ModalStorageApi } from '@core/modals/modalhost/types.ts';
import { disposeModalHost, initializeModalHost } from '@core/modals/modalhost/hostLifecycle.ts';
import { closeModal, closeOpenModals, getModalElement, isOpen, openModal, registerModal, toggleModal } from '@core/modals/modalhost/modalActions.ts';
import { applyBehaviorAttributes } from '@core/modals/render.ts';
import { getServiceContainer } from '@core/serviceContainer.ts';
import type { ModalCloseOptions, ModalCreationOptions, ModalOwnership, ModalHandle, ModalLayoutPreset, ModalOpenOptions, ModalRegisterOptions } from '@core/modals/types.ts';
import { isBoolean, isFunction, isObject } from '@core/typeGuards.ts';
import { getWindow } from '@core/environment/public.ts';
import { getLanguageService } from '@core/languageservice/service.ts';
import { EVENT_CHANGE } from '@core/languageservice/constants.ts';
import { acquireModalOwnership, releaseModalOwnership, hasOpenModalsOutsideOwners } from '@core/modals/modalhost/ownership.ts';
import type { PresentationOwner } from '@core/routing/router/types.ts';
import { prepareModalLocalization } from '@core/modals/localization.ts';
import type { Cleanup } from '@core/lifecycle/cleanup.ts';
import { removeWithPresence, finishPresenceAnimations } from '@core/animations/presence/public.ts';
import { bindModalElement, releaseModalBinding, requireModalBindingSettled, type ModalBinder, type ModalBinding } from '@core/modals/modalhost/bindings.ts';

const MODAL_PRESENTER_SERVICE_ID = 'core.modalPresenter';

interface ModalDefinition {
    id: string;
    presentation?: 'window' | 'viewport';
    layout: ModalLayoutPreset;
    initialFocusSelector: string;
    resizable?: boolean | undefined;
    allowFullscreen?: boolean | undefined;
    createElement: (options: ModalCreationOptions) => HTMLElement;
    bind?: ((modal: HTMLElement) => ModalBinder) | undefined;
    onOpen?: ((modal: HTMLElement, options: ModalOpenOptions) => void) | undefined;
    onClose?: ((modal: HTMLElement, options: ModalCloseOptions) => void) | undefined;
}

interface ModalPresenterApi {
    open: <TOptions extends ModalOpenOptions>(id: string, options: TOptions, ownership?: ModalOwnership) => void;
    close: (id: string, options?: ModalCloseOptions | undefined) => void;
    closeAll: (owner: PresentationOwner, options?: ModalCloseOptions | undefined) => number;
    hasOpenModals: (excludedOwners?: readonly PresentationOwner[]) => boolean;
    dispose: () => Promise<void>;
    acquireOwnership: (id: string, owner: PresentationOwner, disposeSession?: Cleanup) => ModalOwnership;
    releaseOwnership: (ownership: ModalOwnership) => boolean;
    getOwnership: (id: string) => ModalOwnership | null;
    toggle: (id: string, options: ModalOpenOptions, force?: boolean | null | undefined) => void;
    isOpen: (id: string) => boolean;
    requireElement: <TOptions extends ModalCreationOptions>(id: string, options?: TOptions | undefined) => HTMLElement;
}

const isModalPresenterApi = <T>(value: T): value is T & ModalPresenterApi => {
    if (!isObject(value)) {
        return false;
    }
    return 'acquireOwnership' in value && isFunction(value.acquireOwnership) && 'releaseOwnership' in value && isFunction(value.releaseOwnership) && 'getOwnership' in value && isFunction(value.getOwnership) && 'open' in value && isFunction(value.open) && 'close' in value && isFunction(value.close) && 'closeAll' in value && isFunction(value.closeAll) && 'hasOpenModals' in value && isFunction(value.hasOpenModals) && 'dispose' in value && isFunction(value.dispose) && 'toggle' in value && isFunction(value.toggle) && 'isOpen' in value && isFunction(value.isOpen) && 'requireElement' in value && isFunction(value.requireElement);
};

const requireModalPresenter = (): ModalPresenterApi => {
    const candidate = getServiceContainer().get(MODAL_PRESENTER_SERVICE_ID);
    if (!isModalPresenterApi(candidate)) {
        throw new Error(`${MODAL_PRESENTER_SERVICE_ID} service does not match ModalPresenterApi`);
    }
    return candidate;
};

const createModalPresenterService = ({ storage, definitions: definitionList }: { storage: ModalStorageApi; definitions: readonly ModalDefinition[] }): ModalPresenterApi => {
    const boundary = new ErrorBoundary('ModalPresenter');
    let hostState: ModalHostState;
    const definitions: Map<string, ModalDefinition> = new Map();
    const binders: Map<string, ModalBinding> = new Map();
    const handles: Map<string, ModalHandle> = new Map();
    const elements = new Set<HTMLElement>();
    const localization = new WeakMap<HTMLElement, { language: string; options: ModalCreationOptions; apply: (source: HTMLElement) => void }>();
    let disposed = false;
    let disposal: Promise<void> | null = null;

    const localizeElement = (modal: HTMLElement): void => {
        const state = localization.get(modal);
        const language = getLanguageService().getLanguage();
        if (!state || state.language === language) return;
        const definition = requireDefinition(modal.id);
        const source = definition.createElement(state.options);
        ensureInitialized();
        if (source.isConnected || source.id !== modal.id) throw new Error('Modal localization must render a detached root with the same id');
        validateModalRootContract(source, modal.id);
        state.apply(source);
        state.language = language;
        modal.dispatchEvent(new Event('core.modal.localize', { bubbles: true }));
    };

    definitionList.forEach((definition) => {
        const modalId = normalizeModalId(definition.id);
        if (definitions.has(modalId)) {
            throw new Error(`Duplicate modal definition detected: "${modalId}"`);
        }
        definitions.set(modalId, { ...definition, id: modalId });
    });

    const resolveModalElement = (id: string): HTMLElement | null => {
        const resolved = getModalElement(id);
        return resolved instanceof HTMLElement ? resolved : null;
    };

    const ensureInitialized = (): void => {
        if (disposed) throw new Error('Modal presenter is disposed');
        if (!hostState.initialized) {
            hostState.resources.addEventListener(getWindow(), EVENT_CHANGE, () => {
                for (const modalId of definitions.keys()) {
                    const modal = resolveModalElement(modalId);
                    if (!modal) continue;
                    try {
                        localizeElement(modal);
                    } catch (error) {
                        boundary.handleError(ensureError(error), `modal:${modalId}:localize`);
                    }
                }
            });
        }
        initializeModalHost(hostState);
    };

    const requireDefinition = (id: string): ModalDefinition => {
        const modalId = normalizeModalId(id);
        const def = definitions.get(modalId);
        if (!def) {
            throw new Error(`Modal definition is missing for "${modalId}"`);
        }
        return def;
    };

    const ensureRegistered = (id: string): ModalHandle => {
        ensureInitialized();
        const modalId = normalizeModalId(id);
        const cached = handles.get(modalId);
        if (cached) {
            return cached;
        }

        const def = requireDefinition(modalId);
        const registration: ModalRegisterOptions = {
            layout: def.layout,
            ...(def.presentation ? { presentation: def.presentation } : {}),
            initialFocusSelector: def.initialFocusSelector,
            ...(isBoolean(def.resizable) ? { resizable: def.resizable } : {}),
            ...(isBoolean(def.allowFullscreen) ? { allowFullscreen: def.allowFullscreen } : {}),
            onOpen: (modal: Element, options: ModalOpenOptions): void => {
                if (!(modal instanceof HTMLElement)) {
                    throw new Error(`Modal "${modalId}" element must be an HTMLElement`);
                }
                if (isFunction(def.onOpen)) {
                    try {
                        def.onOpen(modal, options);
                    } catch (error) {
                        const runtimeError = ensureError(error);
                        boundary.handleError(runtimeError, `modal:${modalId}:onOpen`);
                        throw runtimeError;
                    }
                }
            },
            onClose: (modal: Element, options: ModalCloseOptions): void => {
                if (!(modal instanceof HTMLElement)) {
                    throw new Error(`Modal "${modalId}" element must be an HTMLElement`);
                }
                if (isFunction(def.onClose)) {
                    try {
                        def.onClose(modal, options);
                    } catch (error) {
                        const runtimeError = ensureError(error);
                        boundary.handleError(runtimeError, `modal:${modalId}:onClose`);
                        throw runtimeError;
                    }
                }
            }
        };

        const handle = registerModal(hostState, modalId, registration);
        handles.set(modalId, handle);
        return handle;
    };

    const discardElement = (modal: HTMLElement): void => {
        elements.delete(modal);
        localization.delete(modal);
        removeWithPresence(modal);
        finishPresenceAnimations(modal);
    };

    const ensureElement = (id: string, options: ModalCreationOptions): HTMLElement => {
        const modalId = normalizeModalId(id);
        const previousBinder = binders.get(modalId) ?? null;
        if (previousBinder) requireModalBindingSettled(previousBinder);
        const existing = getModalElement(modalId);
        if (existing) {
            if (!(existing instanceof HTMLElement)) {
                throw new Error(`Modal "${modalId}" element must be an HTMLElement`);
            }
            validateModalRootContract(existing, modalId);
            localizeElement(existing);
            return existing;
        }

        const def = requireDefinition(modalId);
        if (previousBinder) {
            releaseModalBinding(previousBinder);
            requireModalBindingSettled(previousBinder);
            binders.delete(modalId);
            ensureInitialized();
        }
        const created = def.createElement(options);
        ensureInitialized();
        if (!(created instanceof HTMLElement)) {
            throw new Error(`Modal "${modalId}" createElement() must return an HTMLElement`);
        }
        if (created.id !== modalId) {
            throw new Error(`Modal "${modalId}" createElement() must create element with id="${modalId}" (found id="${created.id}")`);
        }
        validateModalRootContract(created, modalId);
        if (created.isConnected) throw new Error(`Modal "${modalId}" createElement() must return a detached root`);
        localization.set(created, { language: getLanguageService().getLanguage(), options: { ...options }, apply: prepareModalLocalization(created) });
        elements.add(created);
        document.body.appendChild(created);
        applyBehaviorAttributes(created, hostState.registry.getConfig(modalId));
        try {
            ensureInitialized();
            const bindModal = def.bind;
            if (isFunction(bindModal)) bindModalElement(binders, created, bindModal, () => !disposed);
        } catch (error) {
            const binding = binders.get(modalId);
            if (!binding || binding.state.type === 'released') discardElement(created);
            throw error;
        }
        return created;
    };

    hostState = createModalHostState({
        storage,
        resolveModalElement,
        onOwnershipRevoked: (ownership) => {
            if (hostState.ownership.get(ownership.modalId) !== ownership) return;
            if (!isOpen(hostState, ownership.modalId)) {
                releaseModalOwnership(hostState, ownership);
                return;
            }
            const modal = hostState.resolveModalElement(ownership.modalId);
            closeModal(hostState, ownership.modalId, { force: true, restoreFocus: false, reason: 'owner-revoked' });
            if (modal) finishPresenceAnimations(modal);
            releaseModalOwnership(hostState, ownership);
        },
        ensureModalElement: (id: string) => ensureElement(id, {})
    });

    const open = <TOptions extends ModalOpenOptions>(id: string, options: TOptions, ownership?: ModalOwnership): void => {
        const resolvedOptions = options;
        const modalId = normalizeModalId(id);
        ensureRegistered(modalId);
        ensureElement(modalId, resolvedOptions);
        const opened = openModal(hostState, modalId, resolvedOptions, ownership);
        if (opened !== true) {
            throw new Error(`Failed to open modal "${modalId}"`);
        }
    };

    const close = (id: string, options: ModalCloseOptions = {}): void => {
        const modalId = normalizeModalId(id);
        ensureRegistered(modalId);
        closeModal(hostState, modalId, options);
    };

    const closeAll = (owner: PresentationOwner, options: ModalCloseOptions = {}): number => {
        ensureInitialized();
        return closeOpenModals(hostState, options, owner);
    };

    const toggle = (id: string, options: ModalOpenOptions, force: boolean | null = null): void => {
        const modalId = normalizeModalId(id);
        ensureRegistered(modalId);
        const toggled = toggleModal(hostState, modalId, options, force);
        if (toggled !== true) {
            throw new Error(`Failed to toggle modal "${modalId}"`);
        }
    };

    const isModalOpen = (id: string): boolean => {
        const modalId = normalizeModalId(id);
        ensureInitialized();
        return isOpen(hostState, modalId);
    };

    return {
        open,
        close,
        closeAll,
        hasOpenModals: (excludedOwners = []) => hasOpenModalsOutsideOwners(hostState, excludedOwners),
        dispose: (): Promise<void> => {
            if (disposal) return disposal;
            disposed = true;
            const completion = createDeferred<void>();
            disposal = completion.promise;
            void disposeModalHost(hostState, binders, elements, handles, discardElement).then(
                () => completion.resolve(),
                (error) => completion.reject(ensureError(error))
            );
            return completion.promise;
        },
        acquireOwnership: (id, owner, disposeSession) => {
            ensureRegistered(id);
            return acquireModalOwnership(hostState, id, owner, disposeSession);
        },
        releaseOwnership: (ownership) => releaseModalOwnership(hostState, ownership),
        getOwnership: (id) => hostState.ownership.get(normalizeModalId(id)) ?? null,
        toggle,
        isOpen: isModalOpen,
        requireElement: <TOptions extends ModalCreationOptions>(id: string, options?: TOptions | undefined) => {
            const resolvedOptions: ModalCreationOptions = options ?? {};
            const modalId = normalizeModalId(id);
            ensureRegistered(modalId);
            return ensureElement(modalId, resolvedOptions);
        }
    };
};

export { MODAL_PRESENTER_SERVICE_ID, createModalPresenterService, requireModalPresenter };
export type { ModalBinder, ModalDefinition, ModalPresenterApi };
