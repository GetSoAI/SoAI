/* SoAI - Standardized modal before-close confirmation guard [frontend/assets/ts/core/modals/closeGuard.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { errorHandler } from '@core/errorHandler.ts';
import type { ModalPresenterApi } from '@core/modals/modalPresenter.ts';
import type { ModalOwnership } from '@core/modals/types.ts';
import { registerDirtyStateGuard } from '@core/navigationGuards.ts';
import { navigationResult } from '@core/navigationMiddleware.ts';

const bindModalNavigationProtection = (modal: HTMLElement, presenter: ModalPresenterApi, hasWork: () => boolean): (() => void) => {
    let ownership: ModalOwnership | null = null;
    let unregister: (() => void) | null = null;
    const release = (): void => {
        const cleanup = unregister;
        unregister = null;
        ownership = null;
        cleanup?.();
    };
    const synchronize = (): void => {
        const current = presenter.getOwnership(modal.id);
        if (!current || !presenter.isOpen(modal.id)) return;
        if (ownership === current) return;
        release();
        ownership = current;
        const protectedWork = (): boolean => presenter.getOwnership(modal.id) === current && presenter.isOpen(modal.id) && hasWork();
        unregister = registerDirtyStateGuard(() => (protectedWork() ? navigationResult.block('modal-work-active') : true), { owner: current.owner, hasUnsavedChanges: protectedWork, isDestructionBlocked: protectedWork, getProtectionRevision: () => Number(protectedWork()) });
    };
    modal.addEventListener('core.modal.open', synchronize);
    modal.addEventListener('core.modal.close', release);
    try {
        synchronize();
    } catch (error) {
        modal.removeEventListener('core.modal.open', synchronize);
        modal.removeEventListener('core.modal.close', release);
        release();
        throw error;
    }
    return () => {
        modal.removeEventListener('core.modal.open', synchronize);
        modal.removeEventListener('core.modal.close', release);
        release();
    };
};

type BeforeCloseConfirmationGuardOptions = {
    modal: HTMLElement;
    presenter: ModalPresenterApi;
    modalId: string;
    shouldConfirmClose: () => boolean;
    confirmClose: () => Promise<boolean>;
    captureCloseValidity?: () => () => boolean;
};

const attachBeforeCloseConfirmationGuard = (options: BeforeCloseConfirmationGuardOptions): (() => void) => {
    let confirmationInFlight = false;
    let attached = true;
    const releaseProtection = bindModalNavigationProtection(options.modal, options.presenter, options.shouldConfirmClose);

    const handleBeforeClose = (event: Event): void => {
        if (!options.shouldConfirmClose()) {
            return;
        }
        event.preventDefault();
        if (confirmationInFlight) {
            return;
        }
        const isStillValid = options.captureCloseValidity?.();
        const ownership = options.presenter.getOwnership(options.modalId);
        confirmationInFlight = true;
        terminateHandledPromise(
            (async (): Promise<void> => {
                try {
                    const shouldClose = await options.confirmClose();
                    if (shouldClose && attached && ownership !== null && !ownership.signal.aborted && options.presenter.getOwnership(options.modalId) === ownership && (isStillValid?.() ?? true)) {
                        options.presenter.close(options.modalId, {
                            force: true,
                            reason: 'discard-confirmed'
                        });
                    }
                } catch (error) {
                    const runtimeError = ensureError(error);
                    errorHandler.error('ModalCloseGuard', 'Before-close confirmation failed', runtimeError);
                } finally {
                    confirmationInFlight = false;
                }
            })()
        );
    };

    options.modal.addEventListener('core.modal.beforeClose', handleBeforeClose);
    return (): void => {
        attached = false;
        options.modal.removeEventListener('core.modal.beforeClose', handleBeforeClose);
        releaseProtection();
    };
};

const attachPendingOperationCloseGuard = (options: { modal: HTMLElement; presenter: ModalPresenterApi; isPending: () => boolean }): (() => void) => {
    const releaseProtection = bindModalNavigationProtection(options.modal, options.presenter, options.isPending);
    const handleBeforeClose = (event: Event): void => {
        if (options.isPending()) {
            event.preventDefault();
        }
    };
    options.modal.addEventListener('core.modal.beforeClose', handleBeforeClose);
    return (): void => {
        options.modal.removeEventListener('core.modal.beforeClose', handleBeforeClose);
        releaseProtection();
    };
};

export { attachBeforeCloseConfirmationGuard, attachPendingOperationCloseGuard };
