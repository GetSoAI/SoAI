/* SoAI - Shared realtime stream manager state [frontend/assets/ts/core/realtime/streammanager/state.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { DeferredReadyOptions } from '@core/realtime/streammanager/types.ts';
import { LifecycleCancellationError } from '@core/errors/lifecycleCancellation.ts';

interface DeferredReadyState {
    promise: Promise<void> | null;
    resolve: (() => void) | null;
    reject: ((reason?: Error) => void) | null;
    settled: boolean;
    timeoutId: number | null;
}

interface DeferredReadyHost {
    shouldDeferInitialization: () => boolean;
    setTimer: (callback: () => void, timeoutMs: number) => number | null;
    clearTimer: (timerId: number) => void;
    onTimeout: () => void;
}

const createDeferredReadyState = (): DeferredReadyState => {
    return {
        promise: null,
        resolve: null,
        reject: null,
        settled: false,
        timeoutId: null
    };
};

const resetDeferredReadyState = (state: DeferredReadyState, clearTimer: (timerId: number) => void, reason: Error = new LifecycleCancellationError('Deferred readiness reset during lifecycle transition', 'deferred-readiness-reset')): void => {
    if (state.timeoutId !== null) {
        clearTimer(state.timeoutId);
        state.timeoutId = null;
    }
    if (state.promise && !state.settled) {
        state.settled = true;
        state.reject?.(reason);
    }
    state.promise = null;
    state.resolve = null;
    state.reject = null;
    state.settled = false;
};

const settleDeferredReadyState = (state: DeferredReadyState, resetState: () => void): void => {
    if (state.settled) {
        return;
    }
    state.settled = true;
    state.resolve?.();
    resetState();
};

const failDeferredReadyState = (state: DeferredReadyState, error: Error, resetState: () => void): void => {
    if (state.settled) {
        return;
    }
    state.settled = true;
    state.reject?.(error);
    resetState();
};

const awaitDeferredReadyState = (state: DeferredReadyState, host: DeferredReadyHost, options: DeferredReadyOptions = {}): Promise<void> | null => {
    if (!host.shouldDeferInitialization()) {
        settleDeferredReadyState(state, () => resetDeferredReadyState(state, host.clearTimer));
        return null;
    }
    if (state.promise && !state.settled) {
        return state.promise;
    }
    if (state.timeoutId !== null) {
        host.clearTimer(state.timeoutId);
        state.timeoutId = null;
    }
    state.settled = false;
    state.promise = new Promise<void>((resolve, reject) => {
        state.resolve = resolve;
        state.reject = reject;
    });
    if (options.deferTimeoutMs && options.deferTimeoutMs > 0) {
        state.timeoutId = host.setTimer(() => {
            if (!state.settled) {
                host.onTimeout();
            }
        }, options.deferTimeoutMs);
    }
    return state.promise;
};

export { awaitDeferredReadyState, createDeferredReadyState, failDeferredReadyState, resetDeferredReadyState, settleDeferredReadyState };
export type { DeferredReadyHost, DeferredReadyState };
