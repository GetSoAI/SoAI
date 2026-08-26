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
import { isAbortError, raceWithAbortSignal } from '@core/errors/abort.ts';

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

const awaitStageWithTimeout = async (taskFactory: () => Promise<void>, timeoutMs: number, token: symbol, component: string, stage: string, isActiveToken: (token: symbol) => boolean, cancelStage: () => void | Promise<void>): Promise<void> => {
    if (!Number.isFinite(timeoutMs) || timeoutMs <= 0) {
        throw new RangeError('PageOutlet requires a positive stage timeout');
    }
    const stagePromise = taskFactory();
    let timeoutHandle = 0;
    const windowRef = getWindow();
    const timeoutPromise = new Promise<never>((_unusedValue, reject) => {
        timeoutHandle = windowRef.setTimeout(() => {
            const timeoutError = createTimeoutError(component, stage, timeoutMs);
            void Promise.resolve()
                .then(cancelStage)
                .then(() => reject(timeoutError))
                .catch((error) => {
                    reject(new AggregateError([timeoutError, ensureError(error)], `Page ${component} cancellation failed after ${stage} timeout`));
                });
        }, timeoutMs);
    });
    try {
        await Promise.race([stagePromise, timeoutPromise]);
        if (!isActiveToken(token)) {
            return;
        }
    } finally {
        windowRef.clearTimeout(timeoutHandle);
    }
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

export { applyPageOutletErrorState, awaitCommitWindow, awaitStageWithTimeout, runPreNavigationCleanup, resolveErrorState };
