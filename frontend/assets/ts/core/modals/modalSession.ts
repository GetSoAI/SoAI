/* SoAI - Standardized modal session ownership and release completion [frontend/assets/ts/core/modals/modalSession.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { TIMEOUTS } from '@core/constants.ts';
import { OnceGuard } from '@core/concurrency/Once.ts';
import { isAbortError, raceWithAbortSignal } from '@core/errors/abort.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { runAsyncCleanupStepCollectingFailure, runCleanupStepCollectingFailure, throwCollectedCleanupFailures } from '@core/lifecycle/cleanup.ts';
import type { ModalPresenterApi } from '@core/modals/modalPresenter.ts';
import type { ModalCloseOptions, ModalCreationOptions, ModalOpenOptions, ModalOwnership, ModalReleaseOutcome } from '@core/modals/types.ts';
import { isPresentationOwnerActive } from '@core/presentationOwner.ts';
import { withTimeout } from '@core/primitives/withTimeout.ts';
import type { PresentationOwner } from '@core/routing/router/types.ts';
import { createDeferred } from '@core/runtime/deferred.ts';

type ModalSessionContext<TResult> = {
    readonly owner: PresentationOwner;
    modalId: string;
    modal: HTMLElement;
    signal: AbortSignal;
    setResult: (value: TResult) => void;
    close: (reason: string, options?: Omit<ModalCloseOptions, 'reason'> | undefined) => void;
};

type ModalSessionInitializer<TResult> = (context: ModalSessionContext<TResult>) => { dispose: () => void | Promise<void> };
type AlreadyOpenPolicy = 'replace' | 'error';

const runModalSession = async <TResult>(options: { owner: PresentationOwner; presenter: ModalPresenterApi; modalId: string; signal?: AbortSignal | undefined; openOptions?: ModalCreationOptions | undefined; onAlreadyOpen?: AlreadyOpenPolicy | undefined; initialResult: TResult; initialize: ModalSessionInitializer<TResult> }): Promise<TResult> => {
    if (options.signal?.aborted) return options.initialResult;
    const presenter = options.presenter;
    const modalId = options.modalId;
    const owner = options.owner;
    const openOptions: ModalOpenOptions = { ...options.openOptions, owner };
    const previous = presenter.getOwnership(modalId);
    const wasOpen = presenter.isOpen(modalId);
    if (wasOpen || (previous?.owner === owner && previous.signal.aborted)) {
        if (previous?.owner !== owner || options.onAlreadyOpen === 'error') throw new Error(`Modal session "${modalId}" is already open`);
        if (wasOpen) presenter.close(modalId, { reason: 'replace', force: true, restoreFocus: false });
        let outcome: ModalReleaseOutcome;
        try {
            outcome = await withTimeout(options.signal ? raceWithAbortSignal(previous.completion, options.signal) : previous.completion, { timeoutMs: TIMEOUTS.API_REQUEST, timeoutMessage: 'Modal replacement release is unconfirmed' });
        } catch (error) {
            if (options.signal?.aborted && isAbortError(ensureError(error))) return options.initialResult;
            throw ensureError(error);
        }
        if (outcome.type === 'failed') throw outcome.error;
        if (options.signal?.aborted) return options.initialResult;
    }
    const initialized = createDeferred<{ dispose: () => void | Promise<void> }>();
    const disposal = createDeferred<void>();
    const release = new OnceGuard();
    const releaseInitializer = async (): Promise<void> => {
        const resource = await initialized.promise;
        await resource.dispose();
    };
    const disposeSession = (): Promise<void> => {
        release.run(() => {
            void releaseInitializer().then(
                () => disposal.resolve(),
                (error) => disposal.reject(ensureError(error))
            );
        });
        return disposal.promise;
    };
    let ownership: ModalOwnership;
    try {
        ownership = presenter.acquireOwnership(modalId, owner, disposeSession);
    } catch (error) {
        initialized.resolve({ dispose: () => {} });
        await disposeSession();
        throw ensureError(error);
    }

    return await new Promise<TResult>((resolve, reject) => {
        const abortController = new AbortController();
        const { signal } = abortController;
        let initializing = false;
        let finalizationRequested = false;
        let completionStarted = false;
        let result = options.initialResult;
        const failures: Error[] = [];
        const finishRelease = async (): Promise<void> => {
            await runAsyncCleanupStepCollectingFailure(disposeSession, failures);
            if (!presenter.isOpen(modalId) && presenter.getOwnership(modalId) === ownership)
                try {
                    presenter.releaseOwnership(ownership);
                } catch (error) {
                    const failure = ensureError(error);
                    if (!failures.includes(failure)) failures.push(failure);
                }
            throwCollectedCleanupFailures(failures);
            const outcome = await ownership.completion;
            if (outcome.type === 'failed') throw outcome.error;
        };
        const finalize = (): void => {
            finalizationRequested = true;
            if (!signal.aborted) runCleanupStepCollectingFailure(() => abortController.abort(), failures);
            if (initializing || completionStarted) return;
            completionStarted = true;
            runCleanupStepCollectingFailure(() => options.signal?.removeEventListener('abort', handleParentAbort), failures);
            runCleanupStepCollectingFailure(() => ownership.signal.removeEventListener('abort', handleOwnershipAbort), failures);
            void withTimeout(finishRelease(), { timeoutMs: TIMEOUTS.API_REQUEST, timeoutMessage: 'Modal session release is unconfirmed' }).then(
                () => resolve(result),
                (error) => reject(ensureError(error))
            );
        };
        const closeOwned = (reason: string, closeOptions?: Omit<ModalCloseOptions, 'reason'>): void => {
            if (presenter.getOwnership(modalId) !== ownership) return;
            if (presenter.isOpen(modalId)) presenter.close(modalId, { ...closeOptions, reason });
            else {
                finalizationRequested = true;
                if (!signal.aborted) runCleanupStepCollectingFailure(() => abortController.abort(), failures);
                presenter.releaseOwnership(ownership);
            }
            if (!presenter.isOpen(modalId)) finalize();
        };
        const handleParentAbort = (): void => {
            if (finalizationRequested) return;
            result = options.initialResult;
            if (!signal.aborted) runCleanupStepCollectingFailure(() => abortController.abort(), failures);
            runCleanupStepCollectingFailure(() => closeOwned('owner-cancelled', { force: true, restoreFocus: false }), failures);
            finalize();
        };
        const handleOwnershipAbort = (): void => {
            if (!finalizationRequested) result = options.initialResult;
            finalize();
        };
        options.signal?.addEventListener('abort', handleParentAbort, { once: true });
        ownership.signal.addEventListener('abort', handleOwnershipAbort, { once: true });
        try {
            const modal = presenter.requireElement(modalId, openOptions);
            modal.addEventListener('core.modal.close', finalize, { once: true, signal });
            if (options.signal?.aborted || ownership.signal.aborted || signal.aborted || !isPresentationOwnerActive(owner)) {
                initialized.resolve({ dispose: () => {} });
                handleParentAbort();
                finalize();
                return;
            }
            initializing = true;
            try {
                initialized.resolve(
                    options.initialize({
                        owner,
                        modalId,
                        modal,
                        signal,
                        setResult: (value) => {
                            if (!finalizationRequested && !signal.aborted) result = value;
                        },
                        close: (reason, closeOptions) => {
                            if (!finalizationRequested && !signal.aborted) closeOwned(reason, closeOptions);
                        }
                    })
                );
            } finally {
                initializing = false;
            }
            if (finalizationRequested) finalize();
            else presenter.open(modalId, openOptions, ownership);
        } catch (error) {
            failures.push(ensureError(error));
            initialized.resolve({ dispose: () => {} });
            runCleanupStepCollectingFailure(() => closeOwned('init-failed', { force: true, restoreFocus: false }), failures);
            finalize();
        }
    });
};

export { runModalSession };
export type { AlreadyOpenPolicy, ModalSessionContext, ModalSessionInitializer };
