/* SoAI - Shared page outlet actions [frontend/assets/ts/core/pageoutlet/actions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { getWindow } from '@core/environment/public.ts';
import { dom } from '@core/dom/dom.ts';
import { i18n } from '@core/i18n/index.ts';
import { getLayoutHeaderOptional } from '@core/layout/runtime.ts';
import { windowIdentity } from '@core/runtime/windowIdentity.ts';
import { isHTMLElement } from '@core/typeGuards.ts';
import { createTimeoutError, isTimeoutError } from '@core/pageoutlet/state.ts';
import type { PageOutletErrorState, PageOutletStateOptions } from '@core/pageoutlet/types.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { createAbortError, isAbortError, raceWithAbortSignal } from '@core/errors/abort.ts';

const closeHeaderDropdowns = (): void => {
    if (windowIdentity.isDetachedContext()) {
        return;
    }

    const header = getLayoutHeaderOptional();
    if (!header) {
        return;
    }
    try {
        header.closeDropdowns();
    } catch (error) {
        const runtimeError = ensureError(error);
        errorHandler.debug('PageOutlet', 'Failed to close header dropdowns during navigation cleanup', runtimeError);
    }
};

const clearSelection = (): void => {
    const windowRef = getWindow();
    const selection = windowRef.getSelection();
    if (selection) {
        selection.removeAllRanges();
    }
};

const blurActiveElement = (): void => {
    const doc = dom.getDocument();
    const active = doc.activeElement;
    if (isHTMLElement(active) && active !== doc.body) {
        active.blur();
    }
};

const runPreNavigationCleanup = (): void => {
    clearSelection();
    blurActiveElement();
    closeHeaderDropdowns();
};

const runPageOutletRenderHook = async (hook: (() => void | Promise<void>) | Promise<void> | null, signal?: AbortSignal): Promise<void> => {
    if (!hook) return;
    const task = typeof hook === 'function' ? Promise.resolve(hook()) : Promise.resolve(hook);
    if (signal) {
        await raceWithAbortSignal(task, signal);
        return;
    }
    await task;
};

const awaitCommitWindow = async (pendingCommit: Promise<void>, signal: AbortSignal | undefined): Promise<boolean> => {
    if (!signal) {
        await pendingCommit;
        return true;
    }
    try {
        await raceWithAbortSignal(pendingCommit, signal);
        return true;
    } catch (error) {
        const runtimeError = ensureError(error);
        if (!isAbortError(runtimeError) || !signal.aborted) throw runtimeError;
        errorHandler.debug('PageOutlet', 'Commit wait cancelled by navigation abort', runtimeError);
        return false;
    }
};

const awaitStageWithTimeout = async (taskFactory: () => Promise<void>, timeoutMs: number, token: symbol, component: string, stage: string, isActiveToken: (token: symbol) => boolean, cancelStage: () => void | Promise<void>, signal?: AbortSignal): Promise<void> => {
    if (!Number.isFinite(timeoutMs) || timeoutMs <= 0) {
        throw new RangeError('PageOutlet requires a positive stage timeout');
    }
    if (signal?.aborted) {
        throw createAbortError();
    }
    const stagePromise = taskFactory();
    const windowRef = getWindow();
    return new Promise<void>((resolve, reject) => {
        let settled = false;
        let timeoutClaimed = false;
        let timeoutHandle: number | null = null;
        const cleanup = (): void => {
            if (timeoutHandle !== null) {
                windowRef.clearTimeout(timeoutHandle);
                timeoutHandle = null;
            }
            signal?.removeEventListener('abort', onAbort);
        };
        const settleSuccess = (): void => {
            if (settled || timeoutClaimed) return;
            settled = true;
            cleanup();
            resolve();
        };
        const settleFailure = <FailureT>(error: FailureT): void => {
            if (settled || timeoutClaimed) return;
            settled = true;
            cleanup();
            reject(error);
        };
        const onAbort = (): void => {
            if (settled) return;
            settled = true;
            cleanup();
            reject(createAbortError());
        };
        const reportLateCancellationFailure = <FailureT>(error: FailureT): void => {
            const runtimeError = ensureError(error);
            if (settled) {
                errorHandler.warn('PageOutlet', `Page ${component} cancellation failed after ${stage} timeout and navigation abort`, runtimeError);
                return;
            }
            settled = true;
            cleanup();
            reject(new AggregateError([createTimeoutError(component, stage, timeoutMs), runtimeError], `Page ${component} cancellation failed after ${stage} timeout`));
        };
        const claimTimeout = (): void => {
            if (settled) return;
            if (!isActiveToken(token)) {
                settled = true;
                cleanup();
                resolve();
                return;
            }
            timeoutClaimed = true;
            if (timeoutHandle !== null) {
                windowRef.clearTimeout(timeoutHandle);
                timeoutHandle = null;
            }
            const timeoutError = createTimeoutError(component, stage, timeoutMs);
            let cancellation: void | Promise<void> = undefined;
            try {
                if (!isActiveToken(token)) {
                    timeoutClaimed = false;
                    settled = true;
                    cleanup();
                    resolve();
                    return;
                }
                cancellation = cancelStage();
            } catch (error) {
                reportLateCancellationFailure(ensureError(error));
            }
            if (!settled) {
                void Promise.resolve(cancellation)
                    .then(() => {
                        if (settled) return;
                        settled = true;
                        cleanup();
                        reject(timeoutError);
                    }, reportLateCancellationFailure)
                    .catch((error) => errorHandler.warn('PageOutlet', `Page ${component} timeout settlement failed`, ensureError(error)));
            }
        };
        signal?.addEventListener('abort', onAbort, { once: true });
        void stagePromise.then(settleSuccess, settleFailure).catch((error) => errorHandler.warn('PageOutlet', `Page ${component} stage settlement failed`, ensureError(error)));
        if (signal?.aborted) {
            onAbort();
            return;
        }
        timeoutHandle = windowRef.setTimeout(claimTimeout, timeoutMs);
    });
};

const resolveErrorState = (error: Error): PageOutletErrorState => {
    if (!isTimeoutError(error)) {
        return {
            label: i18n.t('pageOutlet.errorTitle'),
            detail: i18n.t('common.errors.operationFailed')
        };
    }

    return {
        label: i18n.t('pageOutlet.errorTitle'),
        detail: i18n.t('pageOutlet.loadingDelayError')
    };
};

const applyPageOutletErrorState = (error: Error, setState: (state: string, options?: PageOutletStateOptions) => void): void => {
    const { label, detail } = resolveErrorState(error);
    setState('error', { label, detail });
};

export { applyPageOutletErrorState, awaitCommitWindow, awaitStageWithTimeout, runPageOutletRenderHook, runPreNavigationCleanup, resolveErrorState };
