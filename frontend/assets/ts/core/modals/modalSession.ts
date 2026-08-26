/* SoAI - Standardized modal session helper for Promise-based modal flows [frontend/assets/ts/core/modals/modalSession.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import type { ModalPresenterApi } from '@core/modals/modalPresenter.ts';
import type { ModalCloseOptions, ModalOpenOptions } from '@core/modals/types.ts';

type ModalSessionContext<TResult> = {
    modalId: string;
    modal: HTMLElement;
    signal: AbortSignal;
    setResult: (value: TResult) => void;
    close: (reason: string, options?: Omit<ModalCloseOptions, 'reason'> | undefined) => void;
};

type ModalSessionInitializer<TResult> = (context: ModalSessionContext<TResult>) => { dispose: () => void };

type AlreadyOpenPolicy = 'replace' | 'error';

const runModalSession = async <TResult>(options: { presenter: ModalPresenterApi; modalId: string; openOptions?: ModalOpenOptions | undefined; onAlreadyOpen?: AlreadyOpenPolicy | undefined; initialResult: TResult; initialize: ModalSessionInitializer<TResult> }): Promise<TResult> => {
    const presenter = options.presenter;
    const modalId = options.modalId;
    const openOptions = options.openOptions ?? {};
    const policy = options.onAlreadyOpen ?? 'replace';
    if (presenter.isOpen(modalId)) {
        if (policy === 'error') {
            throw new Error(`Modal session "${modalId}" is already open`);
        }
        presenter.close(modalId, { reason: 'replace', force: true, restoreFocus: false });
    }

    const modal = presenter.requireElement(modalId, openOptions);

    return await new Promise<TResult>((resolve, reject) => {
        const abortController = new AbortController();
        const { signal } = abortController;
        let settled = false;
        let result = options.initialResult;
        let disposer: { dispose: () => void } = { dispose: () => {} };
        const close = (reason: string, closeOptions: Omit<ModalCloseOptions, 'reason'> | undefined): void => {
            if (settled || signal.aborted) {
                return;
            }
            presenter.close(modalId, { ...closeOptions, reason });
        };

        const finalize = (): void => {
            if (settled) {
                return;
            }
            settled = true;
            abortController.abort();
            disposer.dispose();
            resolve(result);
        };

        modal.addEventListener('core.modal.close', finalize, { once: true, signal });

        const context: ModalSessionContext<TResult> = {
            modalId,
            modal,
            signal,
            setResult: (value: TResult): void => {
                if (settled || signal.aborted) {
                    return;
                }
                result = value;
            },
            close: (reason: string, closeOptions: Omit<ModalCloseOptions, 'reason'> | undefined = undefined): void => {
                close(reason, closeOptions);
            }
        };
        try {
            disposer = options.initialize(context);
            presenter.open(modalId, openOptions);
        } catch (error) {
            settled = true;
            abortController.abort();
            try {
                presenter.close(modalId, {
                    force: true,
                    reason: 'init-failed',
                    restoreFocus: false
                });
            } catch (closeError) {
                errorHandler.warn('ModalSession', 'Failed to close modal after initializer failure', ensureError(closeError));
            }
            try {
                disposer.dispose();
            } catch (disposeError) {
                errorHandler.warn('ModalSession', 'Failed to dispose modal session after initializer failure', ensureError(disposeError));
            }
            reject(ensureError(error));
        }
    });
};

export { runModalSession };
export type { AlreadyOpenPolicy, ModalSessionContext, ModalSessionInitializer };
