/* SoAI - Standardized modal before-close confirmation guard [frontend/assets/ts/core/modals/closeGuard.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { errorHandler } from '@core/errorHandler.ts';
import type { ModalPresenterApi } from '@core/modals/modalPresenter.ts';

type BeforeCloseConfirmationGuardOptions = {
    modal: HTMLElement;
    presenter: ModalPresenterApi;
    modalId: string;
    shouldConfirmClose: () => boolean;
    confirmClose: () => Promise<boolean>;
};

const attachBeforeCloseConfirmationGuard = (options: BeforeCloseConfirmationGuardOptions): (() => void) => {
    let confirmationInFlight = false;

    const handleBeforeClose = (event: Event): void => {
        if (!options.shouldConfirmClose()) {
            return;
        }
        event.preventDefault();
        if (confirmationInFlight) {
            return;
        }
        confirmationInFlight = true;
        terminateHandledPromise(
            (async (): Promise<void> => {
                try {
                    const shouldClose = await options.confirmClose();
                    if (shouldClose) {
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
        options.modal.removeEventListener('core.modal.beforeClose', handleBeforeClose);
    };
};

const attachPendingOperationCloseGuard = (options: { modal: HTMLElement; isPending: () => boolean }): (() => void) => {
    const handleBeforeClose = (event: Event): void => {
        if (options.isPending()) {
            event.preventDefault();
        }
    };
    options.modal.addEventListener('core.modal.beforeClose', handleBeforeClose);
    return (): void => options.modal.removeEventListener('core.modal.beforeClose', handleBeforeClose);
};

export { attachBeforeCloseConfirmationGuard, attachPendingOperationCloseGuard };
